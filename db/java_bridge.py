"""
Java 守护进程桥接服务。

保留共享守护进程与连接池复用，只提供最小请求/响应能力。
"""

from __future__ import annotations

import json
import os
import queue
import shutil
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

BRIDGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BRIDGE_DIR.parent
LIB_DIR = PROJECT_ROOT / "lib"
BRIDGE_SOURCE_FILE = BRIDGE_DIR / "DmJdbcBridge.java"
BRIDGE_CLASS_FILE = BRIDGE_DIR / "DmJdbcBridge.class"

_BRIDGE_COMPILE_LOCK = threading.Lock()


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

        self._ensure_bridge_class_ready(java_home)
        classpath = os.pathsep.join([str(LIB_DIR / "*"), str(BRIDGE_DIR)])

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
                [java_exe, "-cp", classpath, "DmJdbcBridge"],
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

        java_path = shutil.which("java")
        if java_path:
            return os.path.dirname(os.path.dirname(java_path))

        raise JavaBridgeError(
            "找不到 Java 运行时。请确保已安装 Java 8+ 或设置 JAVA_HOME。"
        )

    def _ensure_bridge_class_ready(self, java_home: str) -> None:
        if not BRIDGE_SOURCE_FILE.exists():
            raise JavaBridgeError(f"Java 桥接源码不存在: {BRIDGE_SOURCE_FILE}")

        if not self._bridge_class_needs_compile():
            return

        with _BRIDGE_COMPILE_LOCK:
            if not self._bridge_class_needs_compile():
                return

            javac_exe = self._find_javac(java_home)
            classpath = os.pathsep.join([str(LIB_DIR / "*"), str(BRIDGE_DIR)])

            try:
                result = subprocess.run(
                    [javac_exe, "-cp", classpath, str(BRIDGE_SOURCE_FILE)],
                    capture_output=True,
                    text=True,
                    check=False,
                    env={**os.environ, "JAVA_HOME": java_home},
                )
            except OSError as exc:
                raise JavaBridgeError(f"启动 javac 失败: {exc}") from exc

            if result.returncode != 0:
                detail = self._format_process_output(result.stdout, result.stderr)
                if detail:
                    raise JavaBridgeError(f"编译 DmJdbcBridge.java 失败: {detail}")
                raise JavaBridgeError(
                    f"编译 DmJdbcBridge.java 失败: javac 退出码 {result.returncode}"
                )

            if not BRIDGE_CLASS_FILE.exists():
                raise JavaBridgeError(
                    f"编译 DmJdbcBridge.java 失败: 未生成 {BRIDGE_CLASS_FILE.name}"
                )

    def _bridge_class_needs_compile(self) -> bool:
        if not BRIDGE_CLASS_FILE.exists():
            return True

        try:
            return BRIDGE_SOURCE_FILE.stat().st_mtime > BRIDGE_CLASS_FILE.stat().st_mtime
        except OSError:
            return True

    def _find_javac(self, java_home: str) -> str:
        javac_in_java_home = os.path.join(java_home, "bin", "javac")
        if os.path.exists(javac_in_java_home):
            return javac_in_java_home

        javac_path = shutil.which("javac")
        if javac_path:
            return javac_path

        raise JavaBridgeError(
            "找不到 javac。首次启动或 Java 桥接源码更新时需要可用的 JDK。"
        )

    def _format_process_output(
        self,
        stdout: Optional[str],
        stderr: Optional[str],
    ) -> str:
        parts = [text.strip() for text in (stderr, stdout) if text and text.strip()]
        return "\n".join(parts)

    def _wait_for_ready(self) -> None:
        if self.process is None or self.process.stdout is None:
            raise JavaBridgeError("Java 守护进程未正确启动")

        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                stderr = self.process.stderr.read() if self.process.stderr else ""
                detail = self._format_process_output(None, stderr)
                if detail:
                    raise JavaBridgeError(f"Java 守护进程启动失败: {detail}")
                raise JavaBridgeError("Java 守护进程启动失败")

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
