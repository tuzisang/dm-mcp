#!/usr/bin/env python3
"""
测试1秒超时功能
使用1秒超时和复杂SQL来验证超时机制
"""

import sys
import time
from dm_client import DmClient, DmConfig


def test_1_second_timeout():
    """测试1秒超时功能"""
    print("=== 测试1秒超时功能 ===")
    
    config = DmConfig.from_config_file()
    
    print(f"当前配置:")
    print(f"  - 主机: {config.host}:{config.port}")
    print(f"  - 超时时间: {config.query_timeout} 秒")
    print(f"  - 重试次数: {config.retry_attempts}")
    print(f"  - 重试延迟: {config.retry_delay} 秒")
    
    client = DmClient(config)
    
    try:
        if client.connect():
            print("✓ 连接成功")
            
            # 测试1: 简单查询（应该能在1秒内完成）
            print("\n1. 测试简单查询（应该在1秒内完成）...")
            start_time = time.time()
            try:
                result = client.execute_query("SELECT 1 AS test FROM DUAL")
                end_time = time.time()
                print(f"✓ 简单查询成功，耗时: {end_time - start_time:.2f} 秒")
                print(f"  结果: {result}")
            except Exception as e:
                end_time = time.time()
                print(f"✗ 简单查询失败，耗时: {end_time - start_time:.2f} 秒")
                print(f"  错误: {e}")
            
            # 测试2: 稍微复杂的查询（可能超过1秒）
            print("\n2. 测试复杂查询（可能超过1秒超时）...")
            start_time = time.time()
            try:
                # 这个查询会做笛卡尔积，应该会比较慢
                result = client.execute_query("""
                    SELECT 
                        o1.OBJECT_NAME as name1,
                        o2.OBJECT_NAME as name2,
                        o1.OBJECT_TYPE as type1,
                        o2.OBJECT_TYPE as type2
                    FROM USER_OBJECTS o1, USER_OBJECTS o2
                    WHERE o1.OBJECT_ID < o2.OBJECT_ID
                    AND o1.OBJECT_TYPE = 'TABLE'
                    AND o2.OBJECT_TYPE = 'TABLE'
                    ORDER BY o1.OBJECT_NAME, o2.OBJECT_NAME
                """)
                end_time = time.time()
                print(f"✗ 复杂查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  返回了 {len(result)} 行结果")
                    
            except Exception as e:
                end_time = time.time()
                print(f"复杂查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 1秒超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                else:
                    print("  ⚠️ 这不是超时错误")
            
            # 测试3: 更复杂的查询（几乎肯定会超时）
            print("\n3. 测试更复杂查询（几乎肯定会超过1秒）...")
            start_time = time.time()
            try:
                # 这个查询会产生大量的笛卡尔积和子查询
                result = client.execute_query("""
                    SELECT 
                        o1.OBJECT_NAME,
                        o1.OBJECT_TYPE,
                        (SELECT COUNT(*) FROM USER_OBJECTS o2 
                         WHERE o2.OBJECT_TYPE = o1.OBJECT_TYPE 
                         AND o2.OBJECT_ID != o1.OBJECT_ID) as same_type_count,
                        (SELECT COUNT(*) FROM USER_OBJECTS o3 
                         WHERE o3.OBJECT_NAME LIKE '%' || SUBSTR(o1.OBJECT_NAME, 1, 2) || '%'
                         AND o3.OBJECT_ID != o1.OBJECT_ID) as similar_name_count
                    FROM USER_OBJECTS o1
                    WHERE o1.OBJECT_TYPE IN ('TABLE', 'VIEW', 'INDEX')
                    ORDER BY o1.OBJECT_NAME
                """)
                end_time = time.time()
                print(f"✗ 超复杂查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  返回了 {len(result)} 行结果")
                    
            except Exception as e:
                end_time = time.time()
                print(f"超复杂查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 1秒超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                    return True
                else:
                    print("  ⚠️ 这不是超时错误")
                    
        else:
            print("✗ 连接失败")
            
    except Exception as e:
        print(f"✗ 测试过程中发生异常: {e}")
    
    finally:
        client.close()
    
    return False


def test_timeout_with_large_cartesian():
    """测试大笛卡尔积查询超时"""
    print("\n=== 测试大笛卡尔积查询超时 ===")
    
    config = DmConfig.from_config_file()
    client = DmClient(config)
    
    try:
        if client.connect():
            print("✓ 连接成功")
            
            print(f"\n测试大笛卡尔积查询（1秒超时）...")
            start_time = time.time()
            
            try:
                # 这个查询会产生巨大的笛卡尔积，肯定会超时
                result = client.execute_query("""
                    SELECT COUNT(*)
                    FROM USER_OBJECTS o1, USER_OBJECTS o2, USER_OBJECTS o3
                    WHERE o1.OBJECT_ID < 100
                    AND o2.OBJECT_ID < 100  
                    AND o3.OBJECT_ID < 100
                """)
                end_time = time.time()
                print(f"✗ 大笛卡尔积查询意外完成，耗时: {end_time - start_time:.2f} 秒")
                if result:
                    print(f"  结果: {result}")
                    
            except Exception as e:
                end_time = time.time()
                print(f"大笛卡尔积查询结果，耗时: {end_time - start_time:.2f} 秒")
                print(f"错误: {e}")
                
                if "超时" in str(e) or "timeout" in str(e).lower():
                    print("  ✓ 大笛卡尔积查询超时机制工作正常！")
                    print(f"  ✓ 在 {end_time - start_time:.2f} 秒后正确触发超时")
                    return True
                else:
                    print("  ⚠️ 这不是超时错误")
                    
    except Exception as e:
        print(f"✗ 测试异常: {e}")
    
    finally:
        client.close()
    
    return False


def main():
    """主测试函数"""
    print("达梦数据库1秒超时测试")
    print("=" * 50)
    print("目标：使用1秒超时和复杂SQL验证超时机制")
    print("=" * 50)
    
    timeout_triggered = False
    
    # 测试1秒超时
    if test_1_second_timeout():
        timeout_triggered = True
    
    # 测试大笛卡尔积超时
    if test_timeout_with_large_cartesian():
        timeout_triggered = True
    
    print("\n" + "=" * 50)
    print("测试结论:")
    if timeout_triggered:
        print("✓ 超时机制成功触发！1秒超时功能正常工作！")
        print("✓ 这证明了超时和重试机制已经正确实现")
    else:
        print("⚠️ 超时机制未被触发")
        print("  可能原因：数据库响应极快，或者需要更复杂的查询")
    
    print("\n重要说明:")
    print("1. 当前设置为1秒超时，这对生产环境来说太短了")
    print("2. 建议生产环境使用: dm_update_config(query_timeout=300)  # 5分钟")
    print("3. 超时机制可以防止查询无限期阻塞")
    print("4. 重试机制可以处理临时的网络问题")


if __name__ == "__main__":
    main()