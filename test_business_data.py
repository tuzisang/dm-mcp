#!/usr/bin/env python3
"""
测试业务数据查询功能
"""

from main import dm_query, dm_list_tables, dm_describe_table

def test_business_data():
    """测试业务数据查询"""
    print("=== 测试业务数据查询功能 ===")
    
    # 1. 测试列出表
    print("1. 测试列出aiops模式的表...")
    result = dm_list_tables("aiops")
    if result.get("success"):
        tables = result.get("data", [])
        print(f"✓ 找到 {len(tables)} 个表")
        if tables:
            print("前10个表:")
            for i, table in enumerate(tables[:10]):
                print(f"  {i+1}. {table.get('TABLE_NAME', table.get('OBJECT_NAME', 'Unknown'))}")
        else:
            print("⚠️ aiops模式中没有找到表")
    else:
        print(f"✗ 列表查询失败: {result.get('error')}")
    
    # 2. 测试查询用户表（不指定模式）
    print(f"\n2. 测试查询当前用户的表...")
    result = dm_list_tables()
    if result.get("success"):
        tables = result.get("data", [])
        print(f"✓ 当前用户有 {len(tables)} 个表")
        if tables:
            print("前5个表:")
            for i, table in enumerate(tables[:5]):
                table_name = table.get('TABLE_NAME', table.get('OBJECT_NAME', 'Unknown'))
                print(f"  {i+1}. {table_name}")
                
                # 尝试查询第一个表的结构
                if i == 0:
                    print(f"\n3. 测试查询表 '{table_name}' 的结构...")
                    desc_result = dm_describe_table(table_name)
                    if desc_result.get("success"):
                        columns = desc_result.get("data", [])
                        print(f"✓ 表 '{table_name}' 有 {len(columns)} 个列")
                        if columns:
                            print("前3个列:")
                            for j, col in enumerate(columns[:3]):
                                col_name = col.get('COLUMN_NAME', 'Unknown')
                                col_type = col.get('DATA_TYPE', 'Unknown')
                                nullable = col.get('NULLABLE', 'Unknown')
                                print(f"    {j+1}. {col_name} ({col_type}) - 可空: {nullable}")
                    else:
                        print(f"✗ 查询表结构失败: {desc_result.get('error')}")
                    
                    # 尝试查询表数据
                    print(f"\n4. 测试查询表 '{table_name}' 的数据...")
                    query_result = dm_query(f"SELECT * FROM {table_name} WHERE ROWNUM <= 3")
                    if query_result.get("success"):
                        data = query_result.get("data", [])
                        print(f"✓ 查询成功，返回 {len(data)} 行数据")
                        if data:
                            print("数据示例:")
                            for k, row in enumerate(data):
                                print(f"    行{k+1}: {dict(list(row.items())[:3])}...")  # 只显示前3个字段
                        else:
                            print("  表中没有数据")
                    else:
                        print(f"✗ 查询数据失败: {query_result.get('error')}")
                    break
        else:
            print("⚠️ 当前用户没有表")
    else:
        print(f"✗ 查询用户表失败: {result.get('error')}")
    
    # 5. 测试查询系统信息
    print(f"\n5. 测试查询系统信息...")
    result = dm_query("SELECT USER AS current_user, SYSDATE AS current_time FROM DUAL")
    if result.get("success"):
        data = result.get("data", [])
        if data:
            print(f"✓ 当前用户: {data[0].get('CURRENT_USER')}")
            print(f"✓ 当前时间: {data[0].get('CURRENT_TIME')}")
    else:
        print(f"✗ 查询系统信息失败: {result.get('error')}")

if __name__ == "__main__":
    test_business_data()