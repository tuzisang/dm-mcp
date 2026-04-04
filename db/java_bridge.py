"""
Java 守护进程桥接服务。

保留共享守护进程与连接池复用，只提供最小请求/响应能力。
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_STARTUP_TIMEOUT_SECONDS = 10
DEFAULT_IO_TIMEOUT_SECONDS = 30
DEFAULT_POOL_MIN_CONNECTIONS = 2
DEFAULT_POOL_MAX_CONNECTIONS = 20
DEFAULT_POOL_CONNECTION_TIMEOUT_MS = 60000


class JavaBridgeError(Exception):
    """Java 桥接服务错误。"""


class JavaBridgeClient:
    """通过 stdin/stdout 与 Java 守护进程通信。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._startup_timeout = DEFAULT_STARTUP_TIMEOUT_SECONDS
        self._io_timeout = DEFAULT_IO_TIMEOUT_SECONDS
        self._query_timeout = int(config.get("query_timeout", 120))
        self._start_daemon()

    def _start_daemon(self) -> None:
        java_home = self._find_java()
        java_exe = os.path.join(java_home, "bin", "java")
        if not os.path.exists(java_exe):
            raise JavaBridgeError(f"Java 可执行文件不存在: {java_exe}")

        lib_dir = Path(__file__).parent.parent / "lib"
        classpath = [
            str(lib_dir / "dm-jdbc-1.8.jar"),
            str(lib_dir / "HikariCP-4.0.3.jar"),
            str(lib_dir / "slf4j-api-2.0.12.jar"),
            str(lib_dir / "jackson-core-2.10.4.jar"),
            str(lib_dir / "jackson-databind-2.10.0.jar"),
            str(lib_dir / "jackson-annotations-2.10.0.jar"),
            str(Path(__file__).parent),
        ]

        env = os.environ.copy()
        env["JAVA_HOME"] = java_home
        env["DM_HOST"] = str(self.config["host"])
        env["DM_PORT"] = str(self.config["port"])
        env["DM_USER"] = str(self.config["user"])
        env["DM_PASSWORD"] = str(self.config["password"])
        env["DM_SCHEMA"] = str(self.config.get("schema", ""))
        env["DM_STATEMENT_TIMEOUT"] = str(self._query_timeout)
        env["DM_POOL_MIN"] = str(DEFAULT_POOL_MIN_CONNECTIONS)
        env["DM_POOL_MAX"] = str(DEFAULT_POOL_MAX_CONNECTIONS)
        env["DM_POOL_TIMEOUT"] = str(DEFAULT_POOL_CONNECTION_TIMEOUT_MS)

        try:
            self.process = subprocess.Popen(
                [java_exe, "-cp", ":".join(classpath), "DmJdbcBridge"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise JavaBridgeError(f"启动 Java 守护进程失败: {exc}") from exc

        self._wait_for_ready()

    def _find_java(self) -> str:
        sdkman_path = os.path.expanduser("~/.sdkman/candidates/java/current")
        if os.path.exists(sdkman_path):
            return sdkman_path

        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            return java_home

        try:
            result = subprocess.run(
                ["which", "java"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise JavaBridgeError("找不到 Java 运行时") from exc

        if result.returncode == 0 and result.stdout.strip():
            java_path = result.stdout.strip()
            return os.path.dirname(os.path.dirname(java_path))

        raise JavaBridgeError(
            "找不到 Java 运行时。请确保已安装 Java 8+ 或设置 JAVA_HOME。"
        )

    def _wait_for_ready(self) -> None:
        if self.process is None or self.process.stdout is None:
            raise JavaBridgeError("Java 守护进程未正确启动")

        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise JavaBridgeError(f"Java 守护进程启动失败: {stderr}")

            line = self._read_line_with_timeout(timeout=1)
            if line is None:
                continue

            payload = line.strip()
            if not payload:
                continue

            try:
                response = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if response.get("status") == "ready":
                return

            if response.get("error"):
                raise JavaBridgeError(response.get("message", "Java 守护进程启动失败"))

        raise JavaBridgeError("Java 守护进程启动超时")

    def _read_line_with_timeout(self, timeout: int) -> Optional[str]:
        if self.process is None or self.process.stdout is None:
            return None

        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue()

        def reader() -> None:
            try:
                result_queue.put(("success", self.process.stdout.readline()))
            except Exception as exc:  # pragma: no cover - defensive
                result_queue.put(("error", exc))

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return None

        if result_queue.empty():
            return None

        status, value = result_queue.get()
        if status == "error":
            return None
        return value

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def execute_query(
        self,
        sql: str,
        statement_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if not self.is_alive():
                raise JavaBridgeError("Java 守护进程未运行")

            request: Dict[str, Any] = {"sql": sql}
            if statement_type:
                request["statement_type"] = statement_type

            assert self.process is not None
            assert self.process.stdin is not None

            try:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
            except Exception as exc:
                raise JavaBridgeError(f"发送请求失败: {exc}") from exc

            return self._read_response()

    def _read_response(self) -> Dict[str, Any]:
        if self.process is None:
            raise JavaBridgeError("Java 守护进程未运行")

        deadline = time.time() + self._io_timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                raise JavaBridgeError(f"Java 守护进程意外退出: {stderr}")

            remaining = max(1, int(deadline - time.time()))
            line = self._read_line_with_timeout(timeout=remaining)
            if line is None:
                break

            payload = line.strip()
            if not payload:
                continue

            try:
                response = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise JavaBridgeError(f"解析响应失败: {exc}") from exc

            if response.get("error"):
                raise JavaBridgeError(response.get("message", "Java 执行失败"))

            return response

        raise JavaBridgeError(f"I/O 超时（{self._io_timeout}秒）")

    def shutdown(self) -> None:
        if self.process is None:
            return

        try:
            if self.process.poll() is None and self.process.stdin is not None:
                try:
                    self.process.stdin.write('{"type":"shutdown"}\n')
                    self.process.stdin.flush()
                except OSError:
                    pass

                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        finally:
            self.process = None
