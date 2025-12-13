#!/usr/bin/env python3
"""
验证2分钟超时配置
"""

from dm_client import DmConfig
from main import dm_connect, dm_query

def test_2min_config():
    """测试2分钟超时配置"""
    print("=== 验证2分钟超时配置 ===")
    
    # 检查配置
    config = DmConfig.from_config_file()
    print(f"✓ 查询超时时间: {config.query_timeout}秒 ({config.query_timeout/60:.1f}分钟)")
    print(f"✓ 重试次数: {config.retry_attempts}次")
    print(f"✓ 重试延迟: {config.retry_delay}秒")
    
    # 测试连接
    print(f"\n测试数据库连接...")
    result = dm_connect()
    if result.get("success"):
        print("✓ 数据库连接成功")
        print(f"✓ 连接耗时: {result.get('metadata', {}).get('execution_time_seconds', 0):.2f}秒")
    else:
        print("✗ 数据库连接失败")
        print(f"  错误: {result.get('error')}")
    
    # 测试简单查询
    print(f"\n测试简单查询...")
    result = dm_query("SELECT 1 AS test, SYSDATE AS current_time FROM DUAL")
    if result.get("success"):
        print("✓ 查询成功")
        print(f"✓ 查询耗时: {result.get('metadata', {}).get('execution_time_seconds', 0):.2f}秒")
        print(f"✓ 返回数据: {result.get('data')}")
    else:
        print("✗ 查询失败")
        print(f"  错误: {result.get('error')}")

if __name__ == "__main__":
    test_2min_config()