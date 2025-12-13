#!/usr/bin/env python3
"""
详细测试超时和重试功能的脚本
"""

import time
from dm_client import DmClient, DmConfig


def test_normal_operations():
    """测试正常的数据库操作"""
    print("=== 测试正常的数据库操作 ===")
    
    # 创建配置
    config = DmConfig.from_config_file()
    
    # 创建数据库客户端
    client = DmClient(config)
    
    # 测试连接
    print("1. 测试数据库连接...")
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
    
    # 测试表列表查询
    print("\n3. 测试表列表查询...")
    tables = client.execute_query("SELECT TABLE_NAME FROM USER_TABLES WHERE ROWNUM <= 5")
    print(f"找到 {len(tables)} 个表")
    if tables:
        print(f"前几个表: {[table['TABLE_NAME'] for table in tables[:3]]}")
    
    # 断开连接
    client.disconnect()
    print("\n✓ 正常操作测试完成")
    return True


def test_retry_mechanism():
    """测试重试机制"""
    print("\n=== 测试重试机制 ===")
    
    # 创建配置，设置较短的重试延迟以便观察
    config = DmConfig(
        host="192.168.2.38",
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=30,
        retry_attempts=2,      # 重试2次
        retry_delay=1          # 1秒延迟
    )
    
    # 创建数据库客户端
    client = DmClient(config)
    
    # 测试连接
    print("1. 测试数据库连接...")
    connection_success = client.connect()
    if not connection_success:
        print("✗ 数据库连接失败")
        return False
    
    print("✓ 数据库连接成功")
    
    # 测试一个会失败的更新操作来触发重试（语法错误的SQL）
    print("\n2. 测试重试机制（故意执行错误的SQL）...")
    result = client.execute_update("INVALID SQL STATEMENT")
    print(f"错误SQL执行结果: {result}")
    
    # 断开连接
    client.disconnect()
    print("\n✓ 重试机制测试完成")
    return True


def test_configuration():
    """测试配置加载"""
    print("\n=== 测试配置加载 ===")
    
    # 从配置文件加载配置
    config = DmConfig.from_config_file()
    
    print("配置信息:")
    print(f"  - 主机: {config.host}")
    print(f"  - 端口: {config.port}")
    print(f"  - 用户: {config.user}")
    print(f"  - 模式: {config.schema}")
    print(f"  - 查询超时: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    # 验证配置值
    assert config.query_timeout == 300, f"期望超时时间为300秒，实际为{config.query_timeout}秒"
    assert config.retry_attempts == 3, f"期望重试次数为3次，实际为{config.retry_attempts}次"
    assert config.retry_delay == 5, f"期望重试延迟为5秒，实际为{config.retry_delay}秒"
    
    print("\n✓ 配置加载测试完成")
    return True


if __name__ == "__main__":
    print("开始测试超时和重试功能...")
    
    # 测试配置加载
    if not test_configuration():
        print("配置测试失败!")
        exit(1)
    
    # 测试正常操作
    if not test_normal_operations():
        print("正常操作测试失败!")
        exit(1)
    
    # 测试重试机制
    if not test_retry_mechanism():
        print("重试机制测试失败!")
        exit(1)
    
    print("\n🎉 所有测试都成功完成!")