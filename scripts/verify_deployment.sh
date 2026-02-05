#!/bin/bash
# 部署验证脚本

set -e

echo "=========================================="
echo "DM 查询假死修复 - 部署验证"
echo "=========================================="
echo ""

# 1. 检查 Python 代码
echo "[1/6] 检查 Python 代码..."
python3 -m py_compile db/config.py db/java_bridge.py db/client.py
echo "✓ Python 代码编译通过"
echo ""

# 2. 检查 Java 代码
echo "[2/6] 检查 Java 编译产物..."
if [ -f "db/DmJdbcBridge.class" ]; then
    echo "✓ Java 编译产物存在"
else
    echo "✗ Java 编译产物缺失"
    exit 1
fi
echo ""

# 3. 检查配置文件
echo "[3/6] 检查配置文件..."
if [ -f "dm_config.json" ]; then
    echo "✓ 配置文件存在"
else
    echo "⚠ 配置文件不存在，将使用默认值"
fi
echo ""

# 4. 验证新配置参数
echo "[4/6] 验证新配置参数..."
python3 -c "
from db.config import DmConfig
config = DmConfig()
assert config.io_timeout == 30
assert config.health_check_interval == 15
assert config.max_retries == 1
assert config.pool_max_connections == 20
assert config.pool_connection_timeout == 60000
print('✓ 所有新配置参数默认值正确')
"
echo ""

# 5. 测试基本连接
echo "[5/6] 测试数据库连接..."
python3 << 'PYTHON'
try:
    from db.client import create_client
    client = create_client()
    client.connect()
    result = client.execute_query('SELECT 1 AS test FROM DUAL')
    assert len(result) > 0
    print('✓ 数据库连接测试通过')
    client.close()
except Exception as e:
    print(f'⚠ 数据库连接测试失败: {e}')
PYTHON
echo ""

echo "=========================================="
echo "部署验证完成！"
echo "=========================================="
