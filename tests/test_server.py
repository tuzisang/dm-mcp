"""
MCP 服务器基础测试
"""

import subprocess
import sys
import time


def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    try:
        from main import mcp
        from db import DmClient, DmConfig, PoolConfig
        from core.cache import mcp_cache
        from core.validators import validate_sql_query
        print("✓ 所有模块导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_server_startup():
    """测试服务器能正常启动"""
    print("测试服务器启动...")
    try:
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2)
        
        if process.poll() is None:
            print("✓ 服务器启动成功")
            process.terminate()
            process.wait()
            return True
        else:
            _, stderr = process.communicate()
            print(f"✗ 服务器启动失败: {stderr}")
            return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


if __name__ == "__main__":
    results = [test_imports(), test_server_startup()]
    print(f"\n结果: {sum(results)}/{len(results)} 通过")
    sys.exit(0 if all(results) else 1)
