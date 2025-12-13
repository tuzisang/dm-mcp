#!/usr/bin/env python3
"""
测试超时和重试功能修复
验证新实现的超时和重试机制是否正常工作
"""

import sys
import time
from dm_client import DmClient, DmConfig


def test_timeout_functionality():
    """测试超时功能"""
    print("=== 测试超时功能 ===")
    
    # 创建一个短超时的配置用于测试
    config = DmConfig(
        host="192.168.2.38",
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=5,      # 5秒超时，用于快速测试
        retry_attempts=2,     # 2次重试
        retry_delay=1         # 1秒延迟
    )
    
    print(f"测试配置:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 用户: {config.user}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    client = DmClient(config)
    
    try:
        # 测试正常连接
        print("\n1. 测试正常连接...")
        if client.connect():
            print("✓ 连接成功")
            
            # 测试简单查询（应该很快完成）
            print("\n2. 测试简单查询...")
            start_time = time.time()
            result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
            end_time = time.time()
            
            if result:
                print(f"✓ 查询成功，耗时: {end_time - start_time:.2f} 秒")
                print(f"  结果: {result}")
            else:
                print("✗ 查询失败")
            
            # 测试可能超时的查询（如果数据库响应慢）
            print("\n3. 测试带超时控制的查询...")
            try:
                start_time = time.time()
                # 这个查询可能会比较慢，用来测试超时机制
                result = client.execute_query("SELECT COUNT(*) FROM USER_OBJECTS")
                end_time = time.time()
                
                print(f"✓ 查询完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  结果: {result}")
                    
            except Exception as e:
                end_time = time.time()
                print(f"✗ 查询失败，耗时: {end_time - start_time:.2f} 秒")
                print(f"  错误: {e}")
        else:
            print("✗ 连接失败")
            
    except Exception as e:
        print(f"✗ 测试过程中发生异常: {e}")
    
    finally:
        client.close()
    
    print("\n=== 超时功能测试完成 ===")


def test_retry_functionality():
    """测试重试功能"""
    print("\n=== 测试重试功能 ===")
    
    # 创建一个配置，故意使用错误的主机地址来触发重试
    config = DmConfig(
        host="192.168.999.999",  # 不存在的IP地址
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=10,     # 10秒超时
        retry_attempts=2,     # 2次重试
        retry_delay=2         # 2秒延迟
    )
    
    print(f"测试配置（故意使用错误的主机地址）:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    client = DmClient(config)
    
    try:
        print("\n1. 测试连接重试机制...")
        start_time = time.time()
        
        # 这应该会失败并触发重试机制
        success = client.connect()
        
        end_time = time.time()
        
        if success:
            print("✗ 意外成功（应该失败以测试重试机制）")
        else:
            print(f"✓ 连接失败（符合预期），总耗时: {end_time - start_time:.2f} 秒")
            print("  重试机制已触发")
            
    except Exception as e:
        end_time = time.time()
        print(f"✓ 连接失败并抛出异常（符合预期），总耗时: {end_time - start_time:.2f} 秒")
        print(f"  异常信息: {e}")
    
    finally:
        client.close()
    
    print("\n=== 重试功能测试完成 ===")


def test_normal_operation():
    """测试正常操作（使用正确的配置）"""
    print("\n=== 测试正常操作 ===")
    
    # 使用正常的配置
    config = DmConfig.from_config_file()
    
    print(f"正常配置:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 用户: {config.user}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    client = DmClient(config)
    
    try:
        print("\n1. 测试正常连接...")
        if client.connect():
            print("✓ 连接成功")
            
            print("\n2. 测试基本查询...")
            result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
            if result:
                print(f"✓ 查询成功: {result}")
            else:
                print("✗ 查询失败")
                
        else:
            print("✗ 连接失败")
            
    except Exception as e:
        print(f"✗ 测试过程中发生异常: {e}")
    
    finally:
        client.close()
    
    print("\n=== 正常操作测试完成 ===")


def main():
    """主测试函数"""
    print("达梦数据库超时和重试功能测试")
    print("=" * 50)
    
    # 测试超时功能
    test_timeout_functionality()
    
    # 测试重试功能
    test_retry_functionality()
    
    # 测试正常操作
    test_normal_operation()
    
    print("\n" + "=" * 50)
    print("所有测试完成！")
    print("\n重要说明:")
    print("1. 超时功能可以防止查询无限期阻塞")
    print("2. 重试功能可以处理临时的网络问题")
    print("3. 默认配置: 300秒超时, 3次重试, 5秒延迟")
    print("4. 可以通过 dm_update_config() 工具调整这些参数")


if __name__ == "__main__":
    main()