#!/usr/bin/env python3
"""
测试短超时功能
使用10秒超时来快速验证超时机制是否工作
"""

import sys
import time
from dm_client import DmClient, DmConfig


def test_short_timeout():
    """测试短超时功能"""
    print("=== 测试短超时功能（10秒超时）===")
    
    # 创建一个短超时的配置
    config = DmConfig.from_config_file()
    
    print(f"当前配置:")
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
            
            # 测试快速查询（应该在超时前完成）
            print("\n2. 测试快速查询...")
            start_time = time.time()
            try:
                result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
                end_time = time.time()
                
                if result:
                    print(f"✓ 快速查询成功，耗时: {end_time - start_time:.2f} 秒")
                    print(f"  结果: {result}")
                else:
                    print("✗ 快速查询失败")
                    
            except Exception as e:
                end_time = time.time()
                print(f"✗ 快速查询异常，耗时: {end_time - start_time:.2f} 秒")
                print(f"  错误: {e}")
            
            # 测试可能慢的查询
            print("\n3. 测试可能较慢的查询...")
            start_time = time.time()
            try:
                # 这个查询可能会比较慢，用来测试超时
                result = client.execute_query("""
                    SELECT COUNT(*) as total_objects, 
                           MAX(CREATED) as latest_created,
                           MIN(CREATED) as earliest_created
                    FROM USER_OBJECTS 
                    WHERE OBJECT_TYPE IN ('TABLE', 'VIEW', 'INDEX', 'SEQUENCE')
                """)
                end_time = time.time()
                
                print(f"✓ 复杂查询完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  结果: {result}")
                    
            except Exception as e:
                end_time = time.time()
                print(f"✗ 复杂查询失败，耗时: {end_time - start_time:.2f} 秒")
                print(f"  错误: {e}")
                
                # 检查是否是超时错误
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 这是一个超时错误，说明超时机制正在工作！")
                else:
                    print("  ⚠️ 这不是超时错误，可能是其他问题")
            
            # 测试一个故意设计的慢查询（如果数据库支持）
            print("\n4. 测试故意的慢查询（用于验证超时）...")
            start_time = time.time()
            try:
                # 使用一个可能会慢的查询来测试超时
                # 这个查询会做大量的计算，可能触发超时
                result = client.execute_query("""
                    SELECT 
                        o1.OBJECT_NAME,
                        o1.OBJECT_TYPE,
                        o1.CREATED,
                        (SELECT COUNT(*) FROM USER_OBJECTS o2 WHERE o2.CREATED <= o1.CREATED) as rank_by_date
                    FROM USER_OBJECTS o1
                    ORDER BY o1.CREATED DESC
                """)
                end_time = time.time()
                
                print(f"✓ 慢查询完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  返回了 {len(result)} 行结果")
                    
            except Exception as e:
                end_time = time.time()
                print(f"✗ 慢查询失败，耗时: {end_time - start_time:.2f} 秒")
                print(f"  错误: {e}")
                
                # 检查是否是超时错误
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                else:
                    print("  ⚠️ 这不是超时错误")
                    
        else:
            print("✗ 连接失败")
            
    except Exception as e:
        print(f"✗ 测试过程中发生异常: {e}")
    
    finally:
        client.close()
    
    print("\n=== 短超时功能测试完成 ===")


def test_timeout_with_sleep_simulation():
    """使用模拟延迟测试超时功能"""
    print("\n=== 模拟延迟测试超时功能 ===")
    
    config = DmConfig.from_config_file()
    client = DmClient(config)
    
    try:
        if client.connect():
            print("✓ 连接成功")
            
            # 测试一个包含延迟的查询（如果数据库支持SLEEP或类似函数）
            print(f"\n测试模拟延迟查询（超时设置: {config.query_timeout}秒）...")
            start_time = time.time()
            
            try:
                # 尝试使用达梦数据库的延迟函数（如果支持）
                # 注意：不同数据库的延迟函数不同，这里尝试几种可能的语法
                result = client.execute_query("SELECT SLEEP(15) FROM DUAL")  # 15秒延迟，应该超时
                end_time = time.time()
                
                print(f"✗ 延迟查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                print("  这可能意味着数据库不支持SLEEP函数或超时未生效")
                
            except Exception as e:
                end_time = time.time()
                print(f"延迟查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 超时机制正常工作！")
                elif "SLEEP" in str(e) or "function" in str(e).lower():
                    print("  ℹ️ 数据库不支持SLEEP函数，这是正常的")
                else:
                    print("  ⚠️ 其他类型的错误")
                    
    except Exception as e:
        print(f"✗ 测试异常: {e}")
    
    finally:
        client.close()
    
    print("\n=== 模拟延迟测试完成 ===")


def main():
    """主测试函数"""
    print("达梦数据库短超时功能测试")
    print("=" * 50)
    print("目标：验证10秒超时机制是否正常工作")
    print("=" * 50)
    
    # 测试短超时功能
    test_short_timeout()
    
    # 测试模拟延迟
    test_timeout_with_sleep_simulation()
    
    print("\n" + "=" * 50)
    print("测试总结:")
    print("1. 如果看到'超时机制工作正常'，说明超时功能已生效")
    print("2. 如果查询都能快速完成，说明数据库响应很快，可以尝试更复杂的查询")
    print("3. 如果没有看到超时，可能需要进一步优化超时实现")
    print("4. 当前超时设置为10秒，可以通过dm_update_config调整")


if __name__ == "__main__":
    main()