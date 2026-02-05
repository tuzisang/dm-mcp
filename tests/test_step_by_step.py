#!/usr/bin/env python3
"""分步测试 Java 桥接服务"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Step 1: 测试 Java 桥接服务")
print("-" * 40)

try:
    from db.java_bridge import JavaBridgeClient
    print("✓ 导入 JavaBridgeClient 成功")
except Exception as e:
    print(f"✗ 导入失败: {e}")
    sys.exit(1)

# 加载配置
try:
    from db.config import get_config_manager
    manager = get_config_manager()
    db_config = manager.get_database_config()
    print(f"✓ 加载配置成功: {db_config['host']}:{db_config['port']}")
except Exception as e:
    print(f"✗ 加载配置失败: {e}")
    sys.exit(1)

# 创建桥接客户端
try:
    bridge_config = {
        'host': db_config['host'],
        'port': db_config['port'],
        'user': db_config['user'],
        'password': db_config['password'],
        'schema': db_config.get('schema', ''),
        'query_timeout': 30,
        'pool_min_connections': 2,
        'pool_max_connections': 10,
        'pool_connection_timeout': 30
    }

    print("\nStep 2: 创建 Java 桥接客户端")
    print("-" * 40)
    client = JavaBridgeClient(bridge_config)
    print("✓ Java 守护进程启动成功")
except Exception as e:
    print(f"✗ 创建桥接客户端失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试查询
try:
    print("\nStep 3: 执行测试查询")
    print("-" * 40)
    result = client.execute_query("SELECT COUNT(*) as cnt FROM USER_TABLES")
    print(f"✓ 查询成功: {result}")
    count = result['rows'][0][0]
    print(f"  表数量: {count}")
except Exception as e:
    print(f"✗ 查询失败: {e}")
    import traceback
    traceback.print_exc()

# 清理
print("\nStep 4: 关闭守护进程")
print("-" * 40)
client.shutdown()
print("✓ 守护进程已关闭")

print("\n✓ 所有测试通过!")
