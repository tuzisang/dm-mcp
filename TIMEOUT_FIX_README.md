# 达梦数据库 MCP 服务器超时问题修复

## 问题描述

之前的版本中，MCP 工具在与达梦数据库交互时可能会出现长达10分钟无响应的情况，这是因为缺少超时和重试机制导致的。

## 修复内容

### 1. 添加超时控制
- **查询超时**: 默认300秒（5分钟），可配置
- **更新超时**: 默认300秒（5分钟），可配置
- **超时处理**: 超时后自动断开连接，避免无限等待

### 2. 添加重试机制
- **重试次数**: 默认3次，可配置
- **重试延迟**: 默认5秒，可配置
- **重连机制**: 每次重试前自动重新建立连接

### 3. 配置参数

新增的配置参数：

```json
{
  "database": {
    "host": "192.168.2.38",
    "port": 5236,
    "user": "SYSDBA",
    "password": "SYSDBA001",
    "schema": "aiops",
    "query_timeout": 300,    // 查询超时时间（秒）
    "retry_attempts": 3,     // 重试次数
    "retry_delay": 5         // 重试延迟（秒）
  }
}
```

## 使用方法

### 1. 自动应用
修复后的代码会自动应用超时和重试机制，无需额外配置。

### 2. 调整超时和重试参数
使用 `dm_update_config()` 工具：

```python
# 调整超时时间为10分钟
dm_update_config(query_timeout=600)

# 调整重试次数为5次
dm_update_config(retry_attempts=5)

# 调整重试延迟为10秒
dm_update_config(retry_delay=10)

# 同时调整多个参数
dm_update_config(
    query_timeout=600,
    retry_attempts=5,
    retry_delay=10
)
```

### 3. 参数范围
- **query_timeout**: 1-3600秒（1秒到1小时）
- **retry_attempts**: 0-10次
- **retry_delay**: 0-60秒

## 测试验证

运行测试脚本验证修复效果：

```bash
python test_timeout_fix.py
```

测试内容包括：
1. 超时功能测试
2. 重试机制测试
3. 正常操作测试

## 修复效果

### 修复前
- 查询可能无限期阻塞
- 网络问题导致工具无响应
- 需要手动重启服务器

### 修复后
- 查询最多等待配置的超时时间
- 网络问题自动重试
- 自动恢复，无需手动干预

## 技术实现

### 1. 超时控制
使用线程和超时机制：
```python
def _execute_query_with_timeout(self, sql: str):
    # 使用线程执行查询
    query_thread = threading.Thread(target=query_worker)
    query_thread.start()
    
    # 等待完成或超时
    query_thread.join(timeout=self.config.query_timeout)
    
    if query_thread.is_alive():
        # 超时处理
        self.disconnect()
        raise Exception(f"查询超时（{self.config.query_timeout}秒）")
```

### 2. 重试机制
```python
def _execute_with_retry(self, func, *args, **kwargs):
    for attempt in range(self.config.retry_attempts + 1):
        try:
            if attempt > 0:
                self.disconnect()  # 重试前断开连接
                time.sleep(self.config.retry_delay)  # 等待延迟
            
            return func(*args, **kwargs)
        except Exception as e:
            if attempt >= self.config.retry_attempts:
                raise e  # 最后一次尝试失败，抛出异常
```

## 建议配置

### 开发环境
```json
{
  "query_timeout": 60,     // 1分钟超时，快速发现问题
  "retry_attempts": 2,     // 2次重试
  "retry_delay": 2         // 2秒延迟
}
```

### 生产环境
```json
{
  "query_timeout": 300,    // 5分钟超时，适应复杂查询
  "retry_attempts": 3,     // 3次重试，处理网络波动
  "retry_delay": 5         // 5秒延迟，给系统恢复时间
}
```

### 高负载环境
```json
{
  "query_timeout": 600,    // 10分钟超时，适应大数据查询
  "retry_attempts": 5,     // 5次重试，提高成功率
  "retry_delay": 10        // 10秒延迟，避免频繁重试
}
```

## 注意事项

1. **超时时间设置**: 根据实际查询复杂度设置合适的超时时间
2. **重试次数**: 过多的重试可能会增加系统负载
3. **重试延迟**: 适当的延迟可以给系统恢复时间
4. **网络环境**: 网络不稳定的环境建议增加重试次数和延迟

## 故障排除

### 1. 仍然超时
- 检查查询复杂度，考虑增加超时时间
- 检查数据库性能，优化查询语句
- 检查网络连接稳定性

### 2. 重试过多
- 检查数据库服务状态
- 检查网络连接质量
- 考虑减少重试次数或增加延迟

### 3. 配置不生效
- 确认配置文件格式正确
- 重启 MCP 服务器
- 检查配置文件权限

## 更新日志

- **v1.1.0**: 添加超时和重试机制
- **v1.0.0**: 初始版本（无超时控制）