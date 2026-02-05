# 跨平台兼容性规范

## ADDED Requirements

### Requirement: 支持 macOS ARM64 (Apple Silicon)

系统 SHALL 在 macOS ARM64 平台上正常运行。

#### Scenario: Apple Silicon Mac 运行
- **WHEN** 系统在 Apple Silicon Mac 上运行
- **THEN** 应能成功连接达梦数据库
- **AND** 所有 MCP 工具功能正常

### Requirement: 支持主流操作系统

系统 SHALL 支持 macOS（Intel 和 ARM64）、Linux、Windows 操作系统。

#### Scenario: Linux 平台运行
- **WHEN** 系统在 Linux 上运行
- **THEN** 应能正常连接数据库并执行查询

#### Scenario: Windows 平台运行
- **WHEN** 系统在 Windows 上运行
- **THEN** 应能正常连接数据库并执行查询

### Requirement: 自动检测 Java 环境

系统 SHALL 自动检测系统中的 Java 运行时环境。

#### Scenario: 检测 SDKMAN Java
- **WHEN** 用户通过 SDKMAN 安装了 Java
- **THEN** 系统应自动检测并使用 ~/.sdkman/candidates/java/current

#### Scenario: 检测 JAVA_HOME
- **WHEN** JAVA_HOME 环境变量已设置
- **THEN** 系统应使用该路径作为 Java 安装目录

#### Scenario: Java 未安装
- **WHEN** 系统未找到 Java 运行时
- **THEN** 应抛出明确的错误提示
- **AND** 提供安装 Java 的指导

### Requirement: 平台特定路径处理

系统 SHALL 正确处理不同操作系统的路径分隔符。

#### Scenario: 路径拼接
- **WHEN** 构建文件路径
- **THEN** 应使用 os.path.join() 确保跨平台兼容
- **AND** 自动处理 Unix (/) 和 Windows (\) 路径分隔符
