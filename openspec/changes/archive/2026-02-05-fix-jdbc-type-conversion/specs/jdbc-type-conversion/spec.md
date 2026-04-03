# JDBC 类型转换规范

## ADDED Requirements

### Requirement: 数据库类型到 JSON 类型的智能转换

系统 SHALL 正确处理达梦数据库的所有 JDBC 类型，并将其转换为可序列化为 JSON 的格式。

#### Scenario: 基本类型转换
- **WHEN** 查询结果包含基本类型（INTEGER、VARCHAR、NUMERIC、DATE 等）
- **THEN** 系统应使用 `rs.getObject()` 直接获取值
- **AND** 值应能被 Jackson 正确序列化为 JSON

#### Scenario: BLOB 类型转换
- **WHEN** 查询结果包含 BLOB 类型字段
- **THEN** 系统应使用 `rs.getBytes()` 读取二进制数据
- **AND** 将二进制数据编码为 Base64 字符串
- **AND** 在 JSON 中以字符串形式返回

#### Scenario: CLOB 类型转换
- **WHEN** 查询结果包含 CLOB 类型字段
- **THEN** 系统应使用 `rs.getString()` 读取文本数据
- **AND** 如果 CLOB 数据超过 1MB，应截断并添加警告后缀 `(truncated)`

#### Scenario: LONG/LONG VARCHAR 类型转换
- **WHEN** 查询结果包含 LONG 或 LONG VARCHAR 类型字段（达梦特有类型）
- **THEN** 系统应使用 `rs.getString()` 读取文本数据
- **AND** 应能够处理视图定义等 LONG 类型字段

#### Scenario: TIMESTAMP 类型转换
- **WHEN** 查询结果包含 TIMESTAMP 或 DATE 类型字段
- **THEN** 系统应使用 `rs.getString()` 或 `rs.getTimestamp()` 读取
- **AND** 返回 ISO 8601 格式的字符串（如 `2024-01-15T10:30:00`）

#### Scenario: DECIMAL/NUMBER 类型转换
- **WHEN** 查询结果包含 DECIMAL 或 NUMBER 类型字段
- **THEN** 系统应返回 Java 的 BigDecimal 对象
- **AND** Jackson 应将其序列化为数字（保留精度）

### Requirement: 类型转换错误处理

系统 SHALL 在类型转换失败时优雅降级，而非抛出异常导致整个查询失败。

#### Scenario: 类型转换失败时的降级处理
- **WHEN** 某个字段的类型转换抛出异常
- **THEN** 系统应捕获异常并记录警告日志
- **AND** 返回该字段的字符串表示：`"<类型转换失败: <错误信息>>"`
- **AND** 继续处理其他字段，不中断整个查询

#### Scenario: 类型转换日志记录
- **WHEN** 类型转换失败或使用降级处理
- **THEN** 系统应记录警告级别日志
- **AND** 日志应包含：表名、列名、JDBC 类型、错误原因

### Requirement: 大对象大小限制

系统 SHALL 限制大对象的读取大小，防止内存溢出。

#### Scenario: BLOB 大小限制
- **WHEN** BLOB 字段数据超过 10MB
- **THEN** 系统应截断数据并只读取前 10MB
- **AND** 返回的 Base64 字符串应添加警告后缀 `(truncated from <original_size>MB)`

#### Scenario: CLOB/LONG 文本长度限制
- **WHEN** CLOB 或 LONG 文本字段超过 1MB
- **THEN** 系统应只读取前 1MB 字符
- **AND** 返回的字符串应添加警告后缀 `(truncated from <original_size>MB)`

### Requirement: NULL 值处理

系统 SHALL 正确处理数据库 NULL 值，在 JSON 中表示为 `null`。

#### Scenario: NULL 基本类型字段
- **WHEN** 字段值为 NULL
- **THEN** `rs.wasNull()` 应返回 true
- **AND** JSON 中该字段应为 `null`

#### Scenario: NULL 大对象字段
- **WHEN** BLOB/CLOB 字段值为 NULL
- **THEN** 系统应跳过读取操作
- **AND** JSON 中该字段应为 `null`

### Requirement: 类型感知的列元数据

系统应在 JSON 响应中包含每列的 JDBC 类型信息，便于客户端理解数据类型。

#### Scenario: 返回类型元数据
- **WHEN** 查询成功执行
- **THEN** JSON 响应应包含 `columnTypes` 数组
- **AND** 每个元素应为 JDBC 类型名称（如 `VARCHAR2`, `BLOB`, `TIMESTAMP`）

#### Scenario: 兼容现有格式
- **WHEN** 客户端不使用 `columnTypes` 信息
- **THEN** 查询应正常工作（向后兼容）
