#!/usr/bin/env python3
"""
测试MCP工具超时错误返回
验证MCP工具能正确返回超时错误给调用的AI
"""

import sys
import time
import json
from main import dm_query, dm_connect, dm_list_tables


def test_mcp_timeout_return():
    """测试MCP工具超时错误返回"""
    print("=== 测试MCP工具超时错误返回 ===")
    print("目标：验证MCP工具能正确返回超时错误信息")
    print("当前超时设置：1秒")
    print()
    
    # 测试1: dm_connect 工具
    print("1. 测试 dm_connect() 工具...")
    try:
        result = dm_connect()
        print("dm_connect() 返回结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        if not result.get("success", True):
            print("✓ dm_connect 正确返回了错误信息")
            if "timeout" in result.get("error", "").lower() or "超时" in result.get("error", ""):
                print("✓ 检测到超时错误信息")
        else:
            print("ℹ️ dm_connect 成功执行（连接很快）")
            
    except Exception as e:
        print(f"✗ dm_connect 抛出异常: {e}")
    
    print("\n" + "-" * 50 + "\n")
    
    # 测试2: dm_query 工具 - 简单查询
    print("2. 测试 dm_query() 工具 - 简单查询...")
    try:
        result = dm_query("SELECT 1 FROM DUAL")
        print("dm_query(简单查询) 返回结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        if not result.get("success", True):
            print("✓ dm_query 正确返回了错误信息")
            if "timeout" in result.get("error", "").lower() or "超时" in result.get("error", ""):
                print("✓ 检测到超时错误信息")
        else:
            print("ℹ️ dm_query 简单查询成功执行（查询很快）")
            
    except Exception as e:
        print(f"✗ dm_query 抛出异常: {e}")
    
    print("\n" + "-" * 50 + "\n")
    
    # 测试3: dm_query 工具 - 复杂查询（更可能超时）
    print("3. 测试 dm_query() 工具 - 复杂查询...")
    complex_sql = """
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
    """
    
    try:
        start_time = time.time()
        result = dm_query(complex_sql)
        end_time = time.time()
        
        print(f"dm_query(复杂查询) 执行时间: {end_time - start_time:.2f} 秒")
        print("dm_query(复杂查询) 返回结果:")
        
        # 只打印结果的关键部分，避免输出过多数据
        result_summary = {
            "success": result.get("success"),
            "error": result.get("error"),
            "data_count": len(result.get("data", [])) if result.get("data") else 0,
            "sql": result.get("sql", "")[:100] + "..." if len(result.get("sql", "")) > 100 else result.get("sql", ""),
            "metadata": result.get("metadata", {})
        }
        print(json.dumps(result_summary, indent=2, ensure_ascii=False, default=str))
        
        if not result.get("success", True):
            print("✓ dm_query 正确返回了错误信息")
            error_msg = result.get("error", "")
            if "timeout" in error_msg.lower() or "超时" in error_msg:
                print("✓ 检测到超时错误信息！")
                print(f"✓ 错误类型: {result.get('metadata', {}).get('error_type', 'unknown')}")
                return True  # 成功检测到超时
            else:
                print("⚠️ 不是超时错误，是其他类型的错误")
        else:
            print("ℹ️ dm_query 复杂查询成功执行")
            
    except Exception as e:
        print(f"✗ dm_query 抛出异常: {e}")
    
    print("\n" + "-" * 50 + "\n")
    
    # 测试4: dm_list_tables 工具
    print("4. 测试 dm_list_tables() 工具...")
    try:
        result = dm_list_tables()
        print("dm_list_tables() 返回结果:")
        
        # 只显示摘要信息
        result_summary = {
            "success": result.get("success"),
            "error": result.get("error"),
            "data_count": len(result.get("data", [])) if result.get("data") else 0,
            "metadata": result.get("metadata", {})
        }
        print(json.dumps(result_summary, indent=2, ensure_ascii=False, default=str))
        
        if not result.get("success", True):
            print("✓ dm_list_tables 正确返回了错误信息")
            if "timeout" in result.get("error", "").lower() or "超时" in result.get("error", ""):
                print("✓ 检测到超时错误信息")
        else:
            print("ℹ️ dm_list_tables 成功执行")
            
    except Exception as e:
        print(f"✗ dm_list_tables 抛出异常: {e}")
    
    return False


def test_extreme_timeout_scenario():
    """测试极端超时场景"""
    print("\n=== 测试极端超时场景 ===")
    print("使用大笛卡尔积查询来强制触发超时")
    
    # 一个几乎肯定会超时的查询
    extreme_sql = """
        SELECT COUNT(*)
        FROM USER_OBJECTS o1, USER_OBJECTS o2, USER_OBJECTS o3
        WHERE o1.OBJECT_ID < 50
        AND o2.OBJECT_ID < 50  
        AND o3.OBJECT_ID < 50
        AND o1.OBJECT_ID != o2.OBJECT_ID
        AND o2.OBJECT_ID != o3.OBJECT_ID
        AND o1.OBJECT_ID != o3.OBJECT_ID
    """
    
    try:
        print("执行极端复杂查询...")
        start_time = time.time()
        result = dm_query(extreme_sql)
        end_time = time.time()
        
        print(f"查询执行时间: {end_time - start_time:.2f} 秒")
        print("查询结果:")
        
        result_summary = {
            "success": result.get("success"),
            "error": result.get("error"),
            "metadata": result.get("metadata", {})
        }
        print(json.dumps(result_summary, indent=2, ensure_ascii=False, default=str))
        
        if not result.get("success", True):
            print("✓ 极端查询正确返回了错误信息")
            error_msg = result.get("error", "")
            if "timeout" in error_msg.lower() or "超时" in error_msg:
                print("✓ 成功检测到超时错误！")
                print("✓ MCP工具能正确返回超时信息给调用的AI")
                return True
            else:
                print("⚠️ 不是超时错误")
        else:
            print("✗ 极端查询意外成功")
            
    except Exception as e:
        print(f"✗ 查询抛出异常: {e}")
    
    return False


def main():
    """主测试函数"""
    print("MCP工具超时错误返回测试")
    print("=" * 60)
    print("目标：验证MCP工具能正确返回超时错误给调用的AI")
    print("当前配置：1秒超时，2次重试，1秒延迟")
    print("=" * 60)
    
    timeout_detected = False
    
    # 基础测试
    if test_mcp_timeout_return():
        timeout_detected = True
    
    # 极端测试
    if test_extreme_timeout_scenario():
        timeout_detected = True
    
    print("\n" + "=" * 60)
    print("测试总结:")
    
    if timeout_detected:
        print("✅ 成功！MCP工具能正确返回超时错误信息")
        print("✅ 调用MCP的AI将能收到详细的超时错误信息")
        print("✅ 错误信息包含：")
        print("   - success: false")
        print("   - error: 包含'超时'或'timeout'的详细描述")
        print("   - metadata.error_type: 'timeout_error'")
    else:
        print("⚠️ 未检测到超时错误，可能的原因：")
        print("   1. 数据库响应非常快，1秒内完成所有查询")
        print("   2. 需要更复杂的查询来触发超时")
        print("   3. 超时机制工作正常，但查询优化得很好")
    
    print("\n重要说明：")
    print("1. 当前1秒超时仅用于测试，生产环境建议使用更长的超时时间")
    print("2. MCP工具的错误返回格式已经标准化，AI可以正确解析")
    print("3. 超时错误会包含详细的诊断信息和执行时间")
    print("4. 可以通过 dm_update_config(query_timeout=300) 调整超时时间")


if __name__ == "__main__":
    main()