# JDBC 连接规范

## ADDED Requirements

### Requirement: 通过 JDBC 驱动连接达梦数据库

系统 SHALL 使用达梦数据库 JDBC 驱动（dm-jdbc-1.8.jar）通过 jaydebeapi 建立数据库连接。

#### Scenario: 成功建立连接
- **WHEN** 提供有效的主机、端口、用户名和密码
- **THEN** 系统应成功建立数据库连接
- **AND** 返回可用的连接对象

#### Scenario: 连接失败处理
- **WHEN** 提供无效的连接参数（如错误的主机、端口或凭据）
- **THEN** 系统应抛出 `ConnectionError` 异常
- **AND** 异常信息应包含失败原因

### Requirement: 支持连接参数配置

系统 SHALL 支持通过配置文件（dm_config.json）配置数据库连接参数。

#### Scenario: 从配置文件读取参数
- **WHEN** 配置文件包含 host、port、user、password 等字段
- **THEN** 系统应读取并使用这些参数建立连接

#### Scenario: 配置参数验证
- **WHEN** 配置参数无效（如端口超出范围 1-65535）
- **THEN** 系统应在建立连接前拒绝并报错

### Requirement: 连接超时控制

系统 SHALL 支持连接超时配置，防止长时间等待无响应的数据库。

#### Scenario: 连接超时
- **WHEN** 数据库在配置的超时时间内未响应
- **THEN** 系统应中止连接尝试
- **AND** 抛出 `TimeoutError` 异常

### Requirement: Schema 支持

系统 SHALL 支持指定默认 schema，并在查询中自动使用。

#### Scenario: 使用默认 Schema
- **WHEN** 配置文件指定了 schema 字段
- **THEN** 系统应将该 schema 作为默认查询上下文

## MODIFIED Requirements

无修改项（这是新功能）

## REMOVED Requirements

无移除项
