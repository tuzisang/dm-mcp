# DM 查询假死问题故障排查指南

## 问题概述

**症状**: `dm_query` 工具在某些情况下会永久阻塞（假死），导致查询无法返回结果。

**根本原因**: Java 桥接进程在特定条件下无响应，但 Python 端使用阻塞式 I/O 无法检测。

## 解决方案概述

本项目已实现以下关键修复：

1. **非阻塞 I/O**: 使用线程 + 队列机制实现超时读取（30秒）
2. **心跳检测**: Java 端每 15 秒发送心跳，Python 端监控健康状态
3. **自动恢复**: 检测到假死后自动重启 Java 进程并重试查询
4. **连接资源管理**: 确保异常场景下数据库连接被正确释放

## 故障排查步骤

### 1. 检查 Java 进程状态

```bash
# 查找 Java 进程
ps aux | grep DmJdbcBridge

# 检查进程 CPU 使用率（假死时通常为 0%）
top -p <PID>
```

**预期结果**: Java 进程应该存在，CPU 使用率在执行查询时 > 0%

### 2. 检查日志输出

```bash
# 查看最近的错误日志
grep -i "error\|warning\|timeout" logs/mcp.log | tail -50

# 查看重启事件
grep "restart" logs/mcp.log | tail -20

# 查看心跳事件
grep "heartbeat" logs/mcp.log | tail -20
```

**关键日志**:
- `stdout read timeout`: I/O 读取超时
- `Heartbeat missing`: 心跳缺失
- `Java bridge is unhealthy, attempting restart`: 触发自动重启
- `too many restarts`: 达到重启限制（需要手动干预）

### 3. 测试心跳机制

```python
from db.client import create_client

client = create_client()
bridge = client._get_bridge()

# 查看健康状态
status = bridge.get_health_status()
print(status)

# 预期输出:
# {
#   "is_healthy": true,
#   "is_alive": true,
#   "last_heartbeat": 1234567890.123,
#   "time_since_heartbeat": 1.234,
#   "uptime": 123.456,
#   "restart_count": 0
# }
```

### 4. 检查连接池状态

```python
# 手动发送 pool_status 查询
import json
from db.java_bridge import JavaBridgeClient

config = {
    'host': '192.168.2.38',
    'port': 5236,
    'user': 'SYSDBA',
    'password': 'SYSDBA001'
}

with JavaBridgeClient(config) as bridge:
    request = {"type": "pool_status"}
    bridge.process.stdin.write(json.dumps(request) + '\n')
    bridge.process.stdin.flush()
    
    response = bridge.process.stdout.readline()
    print(response)
    
# 预期输出:
# {"success":true,"active_connections":0,"idle_connections":2,...}
```

**关注指标**:
- `active_connections`: 应该 < `pool_max_connections` (20)
- `threads_awaiting_connection`: 应该 = 0（无等待线程）
- `total_connections`: 应该 ≤ `pool_max_connections`

### 5. 模拟假死场景（仅测试环境）

**警告**: 仅在测试环境中执行，生产环境禁止模拟假死！

```bash
# 方法 1: 暂停 Java 进程（发送 SIGSTOP）
kill -STOP <Java_PID>

# 等待 30 秒观察超时和自动恢复
sleep 35

# 恢复进程
kill -CONT <Java_PID>

# 方法 2: 杀死 Java 进程
kill <Java_PID>

# 观察自动重启
```

**预期行为**:
- Python 端在 30 秒后检测到超时
- 自动重启 Java 进程
- 重试当前查询一次
- 如果成功，查询正常返回

## 常见问题

### Q1: 查询超时后没有自动重启

**可能原因**:
1. 达到重启限制（5分钟内已重启3次）
2. 重启失败（Java 进程启动失败）

**排查方法**:
```python
# 检查重启计数
client = create_client()
bridge = client._get_bridge()
status = bridge.get_health_status()
print(f"Restart count: {status['restart_count']}")
```

**解决方案**:
- 等待 5 分钟让重启计数器重置
- 检查 Java 环境是否正常（JAVA_HOME、classpath）
- 手动重启 MCP 服务器

### Q2: 连接池耗尽

**症状**: 日志中出现 "Connection pool exhausted" 或查询等待超时

**可能原因**:
1. 连接泄漏（查询超时后连接未释放）
2. 并发查询过多超过最大连接数
3. 查询执行时间过长

**排查方法**:
```sql
-- 在达梦数据库中查询当前连接数
SELECT COUNT(*) FROM V$SESSIONS;
```

**解决方案**:
- 增大 `pool_max_connections` 配置（默认 20）
- 检查是否有长时间运行的查询
- 重启 Java 进程清理连接池

### Q3: 心跳持续缺失

**症状**: 日志中频繁出现 "Heartbeat missing"

**可能原因**:
1. Java 进程崩溃或假死
2. stdout 管道阻塞
3. 系统资源不足（CPU/内存）

**排查方法**:
```bash
# 检查 Java 进程是否存在
ps aux | grep DmJdbcBridge

# 检查系统资源
vmstat 1 5

# 检查管道缓冲区
lsof -p <Java_PID> | grep PIPE
```

**解决方案**:
- 手动重启 Java 进程
- 增加系统资源
- 检查是否有死锁

### Q4: 频繁重启（重启循环）

**症状**: 5 分钟内重启 3 次后停止自动重启

**可能原因**:
1. 数据库连接问题
2. 查询超时配置过短
3. 系统资源不足

**排查方法**:
```python
# 检查配置
from db.config import get_config_manager
config = get_config_manager().get_database_config()
print(f"io_timeout: {config.get('io_timeout')}")
print(f"query_timeout: {config.get('query_timeout')}")
```

**解决方案**:
- 增大 `io_timeout` 配置（默认 30 秒）
- 增大 `query_timeout` 配置（默认 120 秒）
- 检查数据库服务器状态
- 查看应用日志中的具体错误信息

## 性能监控

### 关键指标

1. **查询超时率**: 应 < 1%
2. **Java 进程重启次数**: 应 < 1次/小时
3. **平均查询耗时**: 应 < 5 秒
4. **连接池活跃连接数**: 应 < 最大连接数的 80%

### 监控脚本

```python
import time
from db.client import create_client

def monitor_bridge(interval=60):
    """监控 Java 桥接状态"""
    client = create_client()
    bridge = client._get_bridge()
    
    while True:
        status = bridge.get_health_status()
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"  Healthy: {status['is_healthy']}")
        print(f"  Alive: {status['is_alive']}")
        print(f"  Heartbeat age: {status['time_since_heartbeat']:.1f}s")
        print(f"  Uptime: {status['uptime']:.1f}s")
        print(f"  Restarts (5min): {status['restart_count']}")
        
        if not status['is_healthy']:
            print("  ⚠️  WARNING: Bridge is unhealthy!")
        
        time.sleep(interval)

if __name__ == '__main__':
    monitor_bridge()
```

## 预防措施

1. **定期重启 Java 进程**: 每天自动重启一次，清理资源
2. **监控告警**: 配置监控告警（重启次数、超时率）
3. **压力测试**: 定期执行并发查询测试，验证连接池容量
4. **日志分析**: 定期分析日志，发现潜在问题

## 联系支持

如果问题持续存在，请收集以下信息：

1. 完整的日志文件（logs/mcp.log）
2. 配置文件（dm_config.json）
3. Java 进程状态（`ps aux | grep DmJdbcBridge`）
4. 系统资源使用情况（`vmstat 1 10`）
5. 具体的查询 SQL 和参数
