#!/usr/bin/env python3
"""
完整测试新的 DmClient 实现（Java 守护进程版本）
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.config import get_config_manager, DmConfig
from db.client import DmClient, DmClientError


def test_client():
    """测试数据库客户端"""
    print("=" * 60)
    print("测试 DmClient (Java 守护进程版本)")
    print("=" * 60)

    # 加载配置
    manager = get_config_manager()
    db_config = manager.get_database_config()

    print(f"\n配置:")
    print(f"  主机: {db_config['host']}:{db_config['port']}")
    print(f"  用户: {db_config['user']}")
    print(f"  Schema: {db_config.get('schema', 'N/A')}")

    # 创建 DmConfig 对象
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
        # 创建客户端
        print("\n[1] 创建客户端...")
        client = DmClient(config)
        print("✓ 客户端创建成功")

        # 测试连接
        print("\n[2] 测试连接...")
        if client.connect():
            print("✓ 连接成功")
        else:
            print("✗ 连接失败")
            return False

        # 测试查询
        print("\n[3] 测试查询...")
        result = client.execute_query("SELECT COUNT(*) as cnt FROM USER_TABLES")
        print(f"✓ 查询成功: 发现 {result[0]['CNT']} 张表")

        # 测试 list_tables
        print("\n[4] 测试 list_tables...")
        tables = client.list_tables()
        print(f"✓ 找到 {len(tables)} 张表")
        if tables:
            print(f"  前 5 张表:")
            for table in tables[:5]:
                table_name = table.get('TABLE_NAME', table.get('OBJECT_NAME', 'N/A'))
                print(f"    - {table_name}")

        # 测试 list_views
        print("\n[5] 测试 list_views...")
        views = client.list_views()
        print(f"✓ 找到 {len(views)} 个视图")

        # 测试 describe_table
        print("\n[6] 测试 describe_table...")
        if tables:
            first_table = tables[0].get('TABLE_NAME', tables[0].get('OBJECT_NAME', ''))
            if first_table:
                columns = client.describe_table(first_table)
                print(f"✓ 表 {first_table} 有 {len(columns)} 列")

        # 测试上下文管理器
        print("\n[7] 测试上下文管理器...")
        with DmClient(config) as ctx:
            result = ctx.execute_query("SELECT 1 as test FROM DUAL")
            print(f"✓ 上下文管理器测试通过: {result[0]['TEST']}")

        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)
        return True

    except DmClientError as e:
        print(f"\n✗ 客户端错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if client:
            try:
                client.close()
            except:
                pass


if __name__ == "__main__":
    success = test_client()
    sys.exit(0 if success else 1)
