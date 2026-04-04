# 连接池配置规范

## Purpose

描述当前阶段固定在实现内部的 HikariCP 连接池配置边界，明确哪些参数被保留为固定默认值，以及哪些外部配置能力已经被收敛删除。

## Requirements

### Requirement: Java 端连接池配置

Java 守护进程 SHALL 根据固定的实现内默认值配置 HikariCP 连接池，而不是继续暴露外部配置面。

#### Scenario: 使用固定默认值
- **WHEN** Java 守护进程初始化 HikariCP
- **THEN** 应使用实现内约定的默认值：
  - 最小空闲连接数：2
  - 最大连接数：20
  - 连接获取超时：60000 毫秒
- **AND** 这些默认值由运行时内部设置，不通过 `dm_config.json` 暴露

#### Scenario: 应用 HikariCP 配置
- **WHEN** 构建 `HikariConfig` 对象
- **THEN** 应设置以下参数：
  - `setMinimumIdle(2)` 或等价固定值
  - `setMaximumPoolSize(20)` 或等价固定值
  - `setConnectionTimeout(60000)` 或等价固定值
