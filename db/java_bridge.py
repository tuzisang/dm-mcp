"""
Java 守护进程桥接服务

管理 DmJdbcBridge Java 守护进程的生命周期，并通过 stdin/stdout 进行通信。
"""

import json
import os
import subprocess
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Optional, List, Any, Dict

logger = logging.getLogger(__name__)


class JavaBridgeError(Exception):
    """Java 桥接服务错误"""
    pass


class JavaBridgeClient:
    """Java 守护进程桥接客户端"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 Java 守护进程

        Args:
            config: 数据库配置字典
        """
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._startup_timeout = 10  # 秒
        self._query_timeout = config.get('query_timeout', 120)  # 秒
        self._io_timeout = config.get('io_timeout', 30)  # 秒
        self._health_check_interval = config.get('health_check_interval', 15)  # 秒

        # 心跳检测
        self.last_heartbeat: float = time.time()
        self._start_time: float = time.time()

        # 重启控制
        self._restart_history: List[float] = []  # 重启时间戳历史
        self._max_restarts_in_window = 3  # 时间窗口内最大重启次数
        self._restart_window = 300  # 重启时间窗口（秒）= 5分钟

        # 启动守护进程
        self._start_daemon()

    def _start_daemon(self):
        """启动 Java 守护进程"""
        # 检测 Java 环境
        java_home = self._find_java()
        java_exe = os.path.join(java_home, 'bin', 'java')

        if not os.path.exists(java_exe):
            raise JavaBridgeError(f"Java 可执行文件不存在: {java_exe}")

        # 构建 classpath
        lib_dir = Path(__file__).parent.parent / 'lib'
        classpath = [
            str(lib_dir / 'dm-jdbc-1.8.jar'),
            str(lib_dir / 'HikariCP-4.0.3.jar'),
            str(lib_dir / 'slf4j-api-2.0.12.jar'),
            str(lib_dir / 'jackson-core-2.10.4.jar'),
            str(lib_dir / 'jackson-databind-2.10.0.jar'),
            str(lib_dir / 'jackson-annotations-2.10.0.jar'),
            str(Path(__file__).parent)  # db 目录（包含 DmJdbcBridge.class）
        ]

        # 设置环境变量
        env = os.environ.copy()
        env['JAVA_HOME'] = java_home
        env['DM_HOST'] = self.config['host']
        env['DM_PORT'] = str(self.config['port'])
        env['DM_USER'] = self.config['user']
        env['DM_PASSWORD'] = self.config['password']
        env['DM_SCHEMA'] = self.config.get('schema', '')

        # 连接池配置（使用新的默认值）
        env['DM_POOL_MIN'] = str(self.config.get('pool_min_connections', 2))
        env['DM_POOL_MAX'] = str(self.config.get('pool_max_connections', 20))
        env['DM_POOL_TIMEOUT'] = str(self.config.get('pool_connection_timeout', 60000))  # 毫秒

        # 启动 Java 进程
        try:
            self.process = subprocess.Popen(
                [java_exe, '-cp', ':'.join(classpath), 'DmJdbcBridge'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1  # 行缓冲
            )

            # 等待启动完成
            self._wait_for_ready()
            self.last_heartbeat = time.time()  # 重置心跳时间
            logger.info("Java bridge started successfully")

        except Exception as e:
            raise JavaBridgeError(f"启动 Java 守护进程失败: {e}")

    def _find_java(self) -> str:
        """查找 Java 安装目录"""
        # 1. 检查 SDKMAN
        sdkman_path = os.path.expanduser("~/.sdkman/candidates/java/current")
        if os.path.exists(sdkman_path):
            return sdkman_path

        # 2. 检查 JAVA_HOME 环境变量
        if 'JAVA_HOME' in os.environ:
            return os.environ['JAVA_HOME']

        # 3. 尝试使用 java 命令查找
        try:
            result = subprocess.run(['which', 'java'], capture_output=True, text=True)
            if result.returncode == 0:
                java_path = result.stdout.strip()
                # 通常 java 在 bin/java，我们需要 JAVA_HOME
                java_home = os.path.dirname(os.path.dirname(java_path))
                if java_home:
                    return java_home
        except:
            pass

        raise JavaBridgeError(
            "找不到 Java 运行时。请确保已安装 Java 8+，"
            "或通过 SDKMAN 安装，或设置 JAVA_HOME 环境变量"
        )

    def _wait_for_ready(self):
        """等待守护进程就绪"""
        start_time = time.time()

        while time.time() - start_time < self._startup_timeout:
            # 检查进程是否崩溃
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                raise JavaBridgeError(f"Java 守护进程启动失败: {stderr}")

            # 尝试读取一行输出
            try:
                line = self.process.stdout.readline()
                if line:
                    try:
                        data = json.loads(line.strip())
                        if data.get('status') == 'ready':
                            return
                        elif 'error' in data:
                            raise JavaBridgeError(f"守护进程错误: {data.get('message')}")
                    except json.JSONDecodeError:
                        # JSON解析失败 - 可能是Java桥接版本不匹配
                        pass  # 忽略非 JSON 输出
            except:
                pass

            time.sleep(0.1)

        # 启动超时 - 提供详细的诊断信息
        raise JavaBridgeError(
            "Java 守护进程启动超时或响应格式错误。\n\n"
            "可能原因：\n"
            "1. Java桥接版本过旧（期望JSON协议通信）\n"
            "2. CLASSPATH配置错误\n"
            "3. DmJdbcBridge.class未正确编译\n"
            "4. 缺少必需的JAR依赖包\n\n"
            "诊断步骤：\n"
            "1. 检查Java源码版本：db/DmJdbcBridge.java\n"
            "2. 检查编译文件：db/DmJdbcBridge.class\n"
            "3. 检查JAR依赖：lib/目录下应包含dm-jdbc-1.8.jar等文件\n\n"
            "重新编译Java桥接（如需）：\n"
            "  cd /Users/apple/.claude/mcp/dm-mcp\n"
            "  javac -cp 'lib/*' db/DmJdbcBridge.java\n\n"
            f"配置信息：\n"
            f"- Java Home: {os.environ.get('JAVA_HOME', '未设置')}\n"
            f"- Host: {self.config.get('host')}\n"
            f"- Port: {self.config.get('port')}\n"
            f"- Schema: {self.config.get('schema', '')}\n"
        )

    def _read_line_with_timeout(self, timeout: int) -> Optional[str]:
        """
        从 stdout 读取一行，支持超时（使用线程+队列机制）

        Args:
            timeout: 超时时间（秒）

        Returns:
            读取到的行，超时返回 None
        """
        result_queue = queue.Queue()

        def reader():
            try:
                line = self.process.stdout.readline()
                result_queue.put(("success", line))
            except Exception as e:
                result_queue.put(("error", e))

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # 超时：线程仍在运行
            logger.warning(f"stdout read timeout after {timeout}s, process may be unresponsive")
            return None
        else:
            # 线程结束，获取结果
            if not result_queue.empty():
                status, value = result_queue.get()
                if status == "success":
                    return value
                else:
                    logger.error(f"stdout read error: {value}")
                    return None
        return None

    def _is_unhealthy(self) -> bool:
        """
        判断 Java 进程是否不健康

        Returns:
            True 如果进程不健康，False 如果健康
        """
        # 检查进程是否退出
        if self.process is None or self.process.poll() is not None:
            logger.warning("Java process has exited")
            return True

        # 检查心跳缺失
        time_since_heartbeat = time.time() - self.last_heartbeat
        heartbeat_threshold = self._health_check_interval * 2
        if time_since_heartbeat > heartbeat_threshold:
            logger.warning(
                f"Heartbeat missing: {time_since_heartbeat:.1f}s since last heartbeat "
                f"(threshold: {heartbeat_threshold}s)"
            )
            return True

        return False

    def _record_restart(self):
        """记录重启事件"""
        timestamp = time.time()
        self._restart_history.append(timestamp)

        # 清理旧的重启记录（超过时间窗口的）
        self._restart_history = [
            ts for ts in self._restart_history
            if timestamp - ts < self._restart_window
        ]

        restart_count = len(self._restart_history)
        logger.info(
            f"Java bridge restart recorded. "
            f"Restarts in last {self._restart_window}s: {restart_count}"
        )

    def _check_restart_limit(self) -> bool:
        """
        检查是否超过重启限制

        Returns:
            True 如果可以重启，False 如果超过限制
        """
        # 清理旧记录
        current_time = time.time()
        self._restart_history = [
            ts for ts in self._restart_history
            if current_time - ts < self._restart_window
        ]

        restart_count = len(self._restart_history)
        if restart_count >= self._max_restarts_in_window:
            logger.error(
                f"Restart limit reached: {restart_count} restarts in last "
                f"{self._restart_window}s. Giving up auto-restart."
            )
            return False

        return True

    def _restart_and_retry(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        重启 Java 进程并重试查询

        Args:
            sql: SQL 查询
            params: 查询参数

        Returns:
            查询结果字典

        Raises:
            JavaBridgeError: 重启失败或重试失败
        """
        # 检查重启限制
        if not self._check_restart_limit():
            raise JavaBridgeError(
                f"Too many restarts in the last {self._restart_window}s. "
                "Please investigate the issue manually."
            )

        logger.warning("Attempting to restart Java bridge...")

        # 1. 关闭现有进程
        self.shutdown()

        # 2. 等待一段时间
        time.sleep(1)

        # 3. 重新启动
        try:
            self._start_daemon()
            self._record_restart()
        except Exception as e:
            logger.error(f"Failed to restart Java bridge: {e}")
            raise JavaBridgeError(f"Restart failed: {e}")

        # 4. 重试查询一次
        logger.info("Retrying query after restart...")
        try:
            return self._execute_query_internal(sql, params)
        except Exception as e:
            logger.error(f"Query retry after restart failed: {e}")
            raise JavaBridgeError(f"Query failed after restart: {e}")

    def is_alive(self) -> bool:
        """检查守护进程是否存活"""
        return self.process is not None and self.process.poll() is None

    def is_healthy(self) -> bool:
        """
        检查守护进程是否健康

        Returns:
            True 如果健康（进程存活且心跳正常），False 否则
        """
        if not self.is_alive():
            return False

        time_since_heartbeat = time.time() - self.last_heartbeat
        heartbeat_threshold = self._health_check_interval * 2

        return time_since_heartbeat < heartbeat_threshold

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取详细的健康状态信息

        Returns:
            包含健康状态的字典
        """
        uptime = time.time() - self._start_time if self._start_time else 0
        restart_count = len([
            ts for ts in self._restart_history
            if time.time() - ts < self._restart_window
        ])

        return {
            "is_healthy": self.is_healthy(),
            "is_alive": self.is_alive(),
            "last_heartbeat": self.last_heartbeat,
            "time_since_heartbeat": time.time() - self.last_heartbeat,
            "uptime": uptime,
            "restart_count": restart_count,
            "restart_limit": self._max_restarts_in_window
        }

    def _execute_query_internal(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        内部查询执行方法（不包含自动重启逻辑）

        Args:
            sql: SQL 查询语句
            params: 查询参数列表

        Returns:
            包含查询结果的字典
        """
        if not self.is_alive():
            raise JavaBridgeError("Java 守护进程未运行")

        # 构建请求
        request = {"sql": sql}
        if params:
            request["params"] = params

        # 发送请求
        try:
            self.process.stdin.write(json.dumps(request) + '\n')
            self.process.stdin.flush()
        except Exception as e:
            raise JavaBridgeError(f"发送请求失败: {e}")

        # 读取响应
        response = self._read_response()
        return response

    def execute_query(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行查询（包含自动重启和重试逻辑）

        Args:
            sql: SQL 查询语句
            params: 查询参数列表

        Returns:
            包含查询结果的字典
        """
        with self._lock:
            # 检查健康状态
            if self._is_unhealthy():
                logger.warning("Java bridge is unhealthy, attempting restart...")
                return self._restart_and_retry(sql, params)

            try:
                # 尝试执行查询
                result = self._execute_query_internal(sql, params)
                return result
            except JavaBridgeError as e:
                # 查询失败，检查是否是不健康导致的
                if "timeout" in str(e).lower() or "unresponsive" in str(e).lower():
                    logger.warning(f"Query failed with timeout: {e}")
                    if self._is_unhealthy():
                        return self._restart_and_retry(sql, params)
                raise

    def execute_update(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行更新（INSERT/UPDATE/DELETE）

        Args:
            sql: SQL 更新语句
            params: 更新参数列表

        Returns:
            包含影响行数的字典
        """
        return self.execute_query(sql, params)

    def _read_response(self) -> Dict[str, Any]:
        """读取响应（使用超时机制）"""
        start_time = time.time()
        last_activity = start_time

        # 使用 I/O 超时，而不是查询超时
        io_deadline = start_time + self._io_timeout

        while time.time() < io_deadline:
            # 检查进程状态
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                raise JavaBridgeError(f"Java 守护进程意外退出: {stderr}")

            try:
                # 使用超时读取
                line = self._read_line_with_timeout(timeout=max(1, int(io_deadline - time.time())))
                if line:
                    try:
                        response = json.loads(line.strip())

                        # 检查是否是心跳消息
                        if response.get('type') == 'heartbeat':
                            self.last_heartbeat = time.time()
                            logger.debug("Heartbeat received from Java bridge")
                            continue  # 继续读取真正的响应

                        # 正常响应
                        if 'error' in response and response['error']:
                            raise JavaBridgeError(response.get('message', '未知错误'))
                        return response

                    except json.JSONDecodeError as e:
                        raise JavaBridgeError(f"解析响应失败: {e}")
                else:
                    # 超时返回 None
                    elapsed = time.time() - start_time
                    logger.warning(f"No response after {elapsed:.1f}s")
                    raise JavaBridgeError(
                        f"I/O 超时（{self._io_timeout}秒）: "
                        f"Java 守护进程无响应，可能假死"
                    )

            except JavaBridgeError:
                raise
            except Exception as e:
                logger.debug(f"Read error (will retry): {e}")
                time.sleep(0.01)

        raise JavaBridgeError(f"查询超时（{self._io_timeout}秒）")

    def shutdown(self):
        """
        关闭守护进程（改进版：先发送 shutdown 消息）
        """
        if self.process:
            try:
                # 1. 先尝试优雅关闭（发送 shutdown 消息）
                if self.process.poll() is None:  # 进程还在运行
                    try:
                        shutdown_msg = '{"type": "shutdown"}\n'
                        self.process.stdin.write(shutdown_msg)
                        self.process.stdin.flush()
                        logger.info("Sent shutdown message to Java bridge")

                        # 等待进程优雅退出（最多 5 秒）
                        try:
                            self.process.wait(timeout=5)
                            logger.info("Java bridge shutdown gracefully")
                        except subprocess.TimeoutExpired:
                            logger.warning("Java bridge did not exit gracefully, force killing")
                            raise
                    except (BrokenPipeError, OSError):
                        # stdin 已关闭，进程可能已退出
                        pass

                # 2. 如果优雅关闭失败，强制终止
                if self.process.poll() is None:
                    logger.warning("Force killing Java bridge process")
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass  # 已经尽力了

                # 3. 验证进程已退出
                if self.process.poll() is not None:
                    logger.info("Java bridge process confirmed terminated")
                else:
                    logger.error("Failed to terminate Java bridge process")

            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
                try:
                    # 最后的手段：强制 kill
                    if self.process.poll() is None:
                        self.process.kill()
                except:
                    pass
            finally:
                self.process = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


def test_java_bridge():
    """测试 Java 桥接服务"""
    # 加载配置
    import json as json_module
    config_path = Path(__file__).parent.parent / 'dm_config.json'
    with open(config_path) as f:
        config = json_module.load(f)['database']

    print("=" * 50)
    print("测试 Java 桥接服务")
    print("=" * 50)

    try:
        with JavaBridgeClient(config) as client:
            print("✓ Java 守护进程启动成功")

            # 测试健康检查
            health = client.get_health_status()
            print(f"✓ 健康状态: {health}")

            # 测试查询
            result = client.execute_query("SELECT COUNT(*) as cnt FROM USER_TABLES")
            print(f"✓ 查询成功: 发现 {result['rows'][0][0]} 张表")

            # 测试带参数查询
            result = client.execute_query(
                "SELECT TABLE_NAME FROM USER_TABLES WHERE ROWNUM <= ?",
                ["5"]
            )
            print(f"✓ 参数查询成功: 前 5 张表")
            for row in result['rows']:
                print(f"  - {row[0]}")

            print("\n✓ 所有测试通过!")
            return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_java_bridge()
