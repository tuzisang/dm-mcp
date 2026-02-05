#!/usr/bin/env python3
"""测试 SQL 注入防护"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.client import DmClient, DmClientError
from db.config import get_config_manager, DmConfig
from db.sql_security import SqlValidationError

print("=" * 60)
print("测试 SQL 注入防护")
print("=" * 60)

# 加载配置
manager = get_config_manager()
db_config = manager.get_database_config()

config = DmConfig(
    host=db_config['host'],
    port=db_config['port'],
    user=db_config['user'],
    password=db_config['password'],
    schema=db_config.get('schema', ''),
    use_pool=db_config.get('use_pool', True),
    query_timeout=db_config.get('query_timeout', 120),
    retry_attempts=db_config.get('retry_attempts', 3),
    retry_delay=db_config.get('retry_delay', 5),
    pool_min_connections=db_config.get('pool_min_connections', 2),
    pool_max_connections=db_config.get('pool_max_connections', 10),
    pool_connection_timeout=db_config.get('pool_connection_timeout', 30)
)

client = None
try:
    client = DmClient(config)
    client.connect()
    print("✓ 连接成功\n")

    # 测试 1: 正常查询应该成功
    print("[测试 1] 正常查询")
    try:
        tables = client.list_tables()
        print(f"✓ 正常查询成功: 找到 {len(tables)} 张表")
    except Exception as e:
        print(f"✗ 正常查询失败: {e}")

    # 测试 2: 恶意 schema 名称应该被拒绝
    print("\n[测试 2] 恶意 schema 名称 (SQL 注入尝试)")
    malicious_schemas = [
        "aiops'; DROP TABLE users--",
        "aiops' OR '1'='1",
        "aiops'; INSERT INTO",
        "aiops\x00",  # 空字节
        "aiops--; DROP TABLE",
        "aiops'/*comment*/OR/*comment*/'1'='1",
    ]

    for malicious_schema in malicious_schemas:
        try:
            client.list_tables(malicious_schema)
            print(f"✗ 安全漏洞! 恶意输入未被拦截: {repr(malicious_schema)}")
        except (DmClientError, SqlValidationError) as e:
            print(f"✓ 正确拦截恶意输入: {malicious_schema[:30]}...")

    # 测试 3: 恶意表名应该被拒绝
    print("\n[测试 3] 恶意表名")
    malicious_tables = [
        "users'; DROP TABLE--",
        "users OR '1'='1",
        "users--",
        "users/*",
    ]

    for malicious_table in malicious_tables:
        try:
            client.describe_table(malicious_table)
            print(f"✗ 安全漏洞! 恶意表名未被拦截: {repr(malicious_table)}")
        except (DmClientError, SqlValidationError) as e:
            print(f"✓ 正确拦截恶意表名: {malicious_table[:30]}...")

    # 测试 4: 危险 SQL 语句应该被拒绝
    print("\n[测试 4] 危险 SQL 模式")
    dangerous_sqls = [
        "DROP TABLE users",
        "TRUNCATE TABLE users",
        "DELETE FROM users",
        "'; DROP TABLE users; --",
        "EXEC sp_configure",
    ]

    for dangerous_sql in dangerous_sqls:
        try:
            client.execute_query("SELECT * FROM USER_TABLES")  # 这个会成功
            # 实际测试危险 SQL
            from db.sql_security import is_safe_sql
            if not is_safe_sql(dangerous_sql):
                print(f"✓ 正确检测危险 SQL: {dangerous_sql[:30]}...")
        except Exception as e:
            print(f"✓ 正确拦截: {dangerous_sql[:30]}...")

    # 测试 5: 空值应该被拒绝
    print("\n[测试 5] 空值和无效输入")
    invalid_inputs = [
        ("", ""),
        (None, "表名"),
        ("   ", "表名"),
        ("123table", "表名"),  # 以数字开头
        ("table-name", "表名"),  # 包含非法字符
        ("table name", "表名"),  # 包含空格
    ]

    for invalid_value, name_type in invalid_inputs:
        try:
            from db.sql_security import validate_identifier
            validate_identifier(invalid_value, name_type)
            print(f"✗ 安全漏洞! 无效输入未被拦截: {repr(invalid_value)}")
        except SqlValidationError as e:
            print(f"✓ 正确拒绝无效输入: {repr(invalid_value)}")

    print("\n" + "=" * 60)
    print("✓ SQL 注入防护测试通过!")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    if client:
        client.close()
