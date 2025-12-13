#!/usr/bin/env python3
"""
测试超时和重试功能的脚本
"""

import time
from dm_client import DmClient, DmConfig


def test_timeout_retry_functionality():
    """测试超时和重试功能"""
    print("测试超时和重试功能...")
    
    # 创建带有短超时和多次重试的配置
    config = DmConfig(
        host="192.168.2.38",
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=30,      # 30秒超时
        retry_attempts=2,      # 重试2次
        retry_delay=2          # 2秒延迟
    )
    
    # 创建数据库客户端
    client = DmClient(config)
    
    # 显示配置信息
    print(f"配置信息:")
    print(f"  - 主机: {config.host}")
    print(f"  - 端口: {config.port}")
    print(f"  - 用户: {config.user}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    # 测试连接
    print("\n1. 测试数据库连接...")
    connection_success = client.connect()
    if not connection_success:
        print("✗ 数据库连接失败")
        return False
    
    print("✓ 数据库连接成功")
    
    # 测试简单查询
    print("\n2. 测试简单查询...")
    result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
    if result:
        print(f"✓ 查询成功，返回结果: {result}")
    else:
        print("✗ 查询失败")
        return False
    
    # 测试更新操作
    print("\n3. 测试更新操作...")
    # 注意：这里我们不执行实际的更新操作，只是测试机制
    affected_rows = client.execute_update("SELECT 1 FROM DUAL")  # 这会失败，触发重试
    print(f"更新操作结果: {affected_rows}")
    
    # 断开连接
    client.disconnect()
    print("\n✓ 测试完成")
    return True


if __name__ == "__main__":
    test_timeout_retry_functionality()