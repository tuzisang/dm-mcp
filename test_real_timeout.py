#!/usr/bin/env python3
"""
测试真实超时场景
创建一个真正会超时的查询来验证超时机制
"""

import sys
import time
from dm_client import DmClient, DmConfig


def test_real_timeout_scenario():
    """测试真实的超时场景"""
    print("=== 测试真实超时场景 ===")
    
    # 使用更短的超时时间来更容易触发超时
    config = DmConfig(
        host="192.168.2.38",
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=3,      # 3秒超时，更容易触发
        retry_attempts=1,     # 1次重试
        retry_delay=1         # 1秒延迟
    )
    
    print(f"测试配置（极短超时）:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    
    client = DmClient(config)
    
    try:
        if client.connect():
            print("✓ 连接成功")
            
            # 测试1: 正常快速查询
            print("\n1. 测试正常快速查询...")
            start_time = time.time()
            try:
                result = client.execute_query("SELECT 1 FROM DUAL")
                end_time = time.time()
                print(f"✓ 快速查询成功，耗时: {end_time - start_time:.2f} 秒")
            except Exception as e:
                end_time = time.time()
                print(f"✗ 快速查询失败，耗时: {end_time - start_time:.2f} 秒，错误: {e}")
            
            # 测试2: 尝试一个可能很慢的笛卡尔积查询
            print(f"\n2. 测试可能超时的复杂查询（{config.query_timeout}秒超时）...")
            start_time = time.time()
            try:
                # 这个查询会产生大量的笛卡尔积，可能会很慢
                result = client.execute_query("""
                    SELECT COUNT(*) 
                    FROM USER_OBJECTS o1, USER_OBJECTS o2, USER_OBJECTS o3
                    WHERE o1.OBJECT_ID < o2.OBJECT_ID 
                    AND o2.OBJECT_ID < o3.OBJECT_ID
                    AND ROWNUM <= 1000000
                """)
                end_time = time.time()
                print(f"✗ 复杂查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  结果: {result}")
                    
            except Exception as e:
                end_time = time.time()
                print(f"复杂查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                    return True  # 成功触发超时
                else:
                    print("  ⚠️ 这不是超时错误，可能是其他问题")
            
            # 测试3: 尝试一个更复杂的递归查询（如果支持）
            print(f"\n3. 测试递归查询（{config.query_timeout}秒超时）...")
            start_time = time.time()
            try:
                # 尝试一个可能会很慢的递归或复杂计算查询
                result = client.execute_query("""
                    SELECT 
                        o1.OBJECT_NAME,
                        (SELECT COUNT(*) FROM USER_OBJECTS o2 
                         WHERE o2.OBJECT_NAME LIKE '%' || SUBSTR(o1.OBJECT_NAME, 1, 1) || '%'
                         AND o2.OBJECT_ID != o1.OBJECT_ID) as similar_count,
                        (SELECT COUNT(*) FROM USER_OBJECTS o3 
                         WHERE o3.CREATED BETWEEN o1.CREATED - 1 AND o1.CREATED + 1
                         AND o3.OBJECT_ID != o1.OBJECT_ID) as same_day_count
                    FROM USER_OBJECTS o1
                    ORDER BY o1.OBJECT_NAME
                """)
                end_time = time.time()
                print(f"✗ 递归查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  返回了 {len(result)} 行结果")
                    
            except Exception as e:
                end_time = time.time()
                print(f"递归查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                    return True  # 成功触发超时
                else:
                    print("  ⚠️ 这不是超时错误")
                    
        else:
            print("✗ 连接失败")
            
    except Exception as e:
        print(f"✗ 测试过程中发生异常: {e}")
    
    finally:
        client.close()
    
    return False  # 没有成功触发超时


def test_connection_timeout():
    """测试连接超时（使用不存在的主机）"""
    print("\n=== 测试连接超时 ===")
    
    # 使用一个不存在的IP地址来测试连接超时
    config = DmConfig(
        host="192.168.999.999",  # 不存在的IP
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops",
        query_timeout=5,      # 5秒超时
        retry_attempts=1,     # 1次重试
        retry_delay=1         # 1秒延迟
    )
    
    print(f"测试连接超时（使用不存在的主机）:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    
    client = DmClient(config)
    
    start_time = time.time()
    try:
        # 这应该会因为网络超时而失败
        success = client.connect()
        end_time = time.time()
        
        if success:
            print(f"✗ 连接意外成功，耗时: {end_time - start_time:.2f} 秒")
        else:
            print(f"✓ 连接失败（符合预期），耗时: {end_time - start_time:.2f} 秒")
            
    except Exception as e:
        end_time = time.time()
        print(f"✓ 连接异常（符合预期），耗时: {end_time - start_time:.2f} 秒")
        print(f"  错误: {e}")
    
    finally:
        client.close()


def test_manual_timeout_simulation():
    """手动模拟超时情况"""
    print("\n=== 手动模拟超时测试 ===")
    
    config = DmConfig.from_config_file()
    
    # 临时修改超时时间为1秒（极短）
    config.query_timeout = 1
    config.retry_attempts = 0  # 不重试，直接看超时效果
    
    print(f"手动设置极短超时: {config.query_timeout} 秒")
    
    client = DmClient(config)
    
    try:
        if client.connect():
            print("✓ 连接成功")
            
            print(f"\n测试1秒超时的查询...")
            start_time = time.time()
            
            try:
                # 即使是简单查询，1秒超时也可能触发（取决于网络延迟）
                result = client.execute_query("""
                    SELECT o1.OBJECT_NAME, o2.OBJECT_NAME
                    FROM USER_OBJECTS o1, USER_OBJECTS o2
                    WHERE o1.OBJECT_ID < o2.OBJECT_ID
                    ORDER BY o1.OBJECT_NAME, o2.OBJECT_NAME
                """)
                end_time = time.time()
                print(f"✗ 查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                
            except Exception as e:
                end_time = time.time()
                print(f"查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 1秒超时机制工作正常！")
                    return True
                else:
                    print("  ⚠️ 不是超时错误")
                    
    except Exception as e:
        print(f"✗ 测试异常: {e}")
    
    finally:
        client.close()
    
    return False


def main():
    """主测试函数"""
    print("达梦数据库真实超时测试")
    print("=" * 60)
    print("目标：创建真正会超时的场景来验证超时机制")
    print("=" * 60)
    
    timeout_triggered = False
    
    # 测试1: 真实超时场景
    if test_real_timeout_scenario():
        timeout_triggered = True
    
    # 测试2: 连接超时
    test_connection_timeout()
    
    # 测试3: 手动模拟超时
    if test_manual_timeout_simulation():
        timeout_triggered = True
    
    print("\n" + "=" * 60)
    print("测试结论:")
    if timeout_triggered:
        print("✓ 超时机制已经成功触发，功能正常工作！")
    else:
        print("⚠️ 超时机制未被触发，可能的原因：")
        print("  1. 数据库响应非常快，查询都在超时前完成")
        print("  2. 超时实现可能需要进一步优化")
        print("  3. 需要更复杂的查询来触发超时")
    
    print("\n建议：")
    print("1. 如果在实际使用中遇到长时间无响应，可以调用 dm_update_config(query_timeout=30)")
    print("2. 当前的重试机制已经实现，可以处理网络问题")
    print("3. 超时时间可以根据实际查询复杂度调整")


if __name__ == "__main__":
    main()