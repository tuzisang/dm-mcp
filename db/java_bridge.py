"""
Java 守护进程桥接服务

管理 DmJdbcBridge Java 守护进程的生命周期，并通过 stdin/stdout 进行通信。
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, List, Any, Dict


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

        # 连接池配置
        env['DM_POOL_MIN'] = str(self.config.get('pool_min_connections', 2))
        env['DM_POOL_MAX'] = str(self.config.get('pool_max_connections', 10))
        env['DM_POOL_TIMEOUT'] = str(self.config.get('pool_connection_timeout', 30) * 1000)

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
                        pass  # 忽略非 JSON 输出
            except:
                pass

            time.sleep(0.1)

        raise JavaBridgeError("Java 守护进程启动超时")

    def is_alive(self) -> bool:
        """检查守护进程是否存活"""
        return self.process is not None and self.process.poll() is None

    def execute_query(self, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """
        执行查询

        Args:
            sql: SQL 查询语句
            params: 查询参数列表

        Returns:
            包含查询结果的字典
        """
        with self._lock:
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
        """读取响应"""
        start_time = time.time()

        while time.time() - start_time < self._query_timeout:
            # 检查进程状态
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                raise JavaBridgeError(f"Java 守护进程意外退出: {stderr}")

            try:
                # 设置非阻塞读取
                line = self.process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line.strip())
                        if 'error' in response and response['error']:
                            raise JavaBridgeError(response.get('message', '未知错误'))
                        return response
                    except json.JSONDecodeError as e:
                        raise JavaBridgeError(f"解析响应失败: {e}")
            except:
                pass

            time.sleep(0.01)

        raise JavaBridgeError(f"查询超时（{self._query_timeout}秒）")

    def shutdown(self):
        """关闭守护进程"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass
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
