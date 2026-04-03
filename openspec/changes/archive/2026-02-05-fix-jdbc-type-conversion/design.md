# JDBC 类型转换修复 - 技术设计

## Context

### 当前状态

**现有实现**：
- `DmJdbcBridge.java` 的 `executeQuery()` 方法使用 `rs.getObject(i)` 读取所有类型的字段
- `getObject()` 返回的对象类型由 JDBC 驱动决定，可能是 `Blob`, `Clob`, `Struct` 等复杂类型
- 这些复杂类型无法被 Jackson ObjectMapper 正确序列化为 JSON
- 当查询结果包含 BLOB、CLOB、LONG、TEXT 等字段时，序列化失败导致整个查询失败

**技术约束**：
- 必须保持 JSON 响应格式不变（向后兼容）
- 不能引入新的外部依赖（仅使用 Java 标准库）
- 需要在 Java 端完成所有转换，Python 端无需修改
- 必须处理达梦数据库特有的类型（LONG、LONG VARCHAR、TEXT 等）

### 利益相关者

- **最终用户**：需要能够查询包含大对象的表和获取视图定义
- **MCP Server**：需要稳定的查询结果格式，避免类型转换错误
- **数据库管理员**：需要监控日志了解类型转换降级情况

## Goals / Non-Goals

**Goals:**

1. 实现类型感知的列值读取，支持所有达梦数据库 JDBC 类型
2. 将不可序列化的类型转换为 JSON 兼容格式（BLOB → Base64 字符串）
3. 提供优雅的降级机制，单个字段转换失败不影响整个查询
4. 添加大小限制防止内存溢出（BLOB 10MB，CLOB 1MB）
5. 在响应中包含类型元数据（`columnTypes` 数组）

**Non-Goals:**

1. 不实现完全动态的类型推断（基于 JDBC 类型常量判断）
2. 不支持用户自定义转换策略（固定转换逻辑）
3. 不修改 Python 端代码（保持 JSON 接口稳定）
4. 不实现流式读取大对象（完整加载到内存，但有大小限制）
5. 不支持 BLOB/CLOB 写入操作（仅读取）

## Decisions

### 决策 1: 使用 `ResultSetMetaData` 获取 JDBC 类型

**选择**：在读取每列之前调用 `rs metaData.getColumnType(i)` 获取 JDBC 类型常量，根据类型选择合适的 `getXXX()` 方法。

**理由**：
- `getColumnType()` 返回 `Types.*` 常量（如 `Types.BLOB`, `Types.CLOB`），类型判断准确可靠
- 避免了 `instanceof` 类型检查的局限性（某些驱动可能返回自定义实现类）
- 符合 JDBC 最佳实践，跨数据库兼容性好

**替代方案**：
- ❌ **方案 A**：使用 `getObject()` 后检查返回类型并转换
  - 缺点：某些类型（如 BLOB）在 `getObject()` 后可能已经无法正确读取
  - 缺点：需要两次类型检查（一次获取对象，一次判断类型）

### 决策 2: 类型映射策略

**选择**：实现 `getColumnValue()` 方法，使用 `switch-case` 基于 JDBC 类型常量分发到不同的读取逻辑。

| JDBC 类型 | 读取方法 | 转换逻辑 |
|-----------|---------|---------|
| `Types.BLOB` | `rs.getBytes()` | Base64 编码为字符串 |
| `Types.CLOB`, `Types.LONGVARCHAR` | `rs.getString()` | 直接返回字符串，超过 1MB 截断 |
| `Types.TIMESTAMP`, `Types.DATE` | `rs.getString()` | 返回 ISO 8601 格式字符串 |
| `Types.DECIMAL`, `Types.NUMERIC` | `rs.getBigDecimal()` | 返回 BigDecimal，Jackson 序列化为数字 |
| 其他类型 | `rs.getObject()` | 默认处理 |

**理由**：
- **BLOB 使用 `getBytes()`**：返回 `byte[]`，可以直接用 `java.util.Base64` 编码
- **CLOB 使用 `getString()`**：JDBC 驱动自动处理字符编码，避免手动读取流
- **TIMESTAMP 使用 `getString()`**：JDBC 返回 `yyyy-MM-DD HH:MM:SS` 格式，符合 ISO 8601 标准
- **DECIMAL 使用 `getBigDecimal()`**：保留精度，Jackson 正确序列化为数字（非字符串）

**替代方案**：
- ❌ **方案 A**：所有类型都使用 `getString()`
  - 缺点：BLOB 会被转换为十六进制字符串，效率低且不直观
  - 缺点：数值类型会变成字符串，丢失类型信息

### 决策 3: 错误处理策略

**选择**：为每个字段调用包装在 `try-catch` 块中，转换失败时返回错误字符串 `"<类型转换失败: <错误信息>>"` 并记录警告日志。

**理由**：
- **部分失败容忍**：单个字段转换失败不应导致整个查询失败
- **可观测性**：日志记录包含表名、列名、JDBC 类型、错误原因
- **用户友好**：错误字符串明确告知问题，用户可以针对该字段进行处理

**替代方案**：
- ❌ **方案 A**：任何转换失败都抛出异常，中止整个查询
  - 缺点：用户体验差，一个字段问题导致整个查询无法执行
- ❌ **方案 B**：返回 `null` 表示转换失败
  - 缺点：无法区分真正的 NULL 值和转换失败

### 决策 4: 大对象大小限制

**选择**：
- **BLOB 限制**：10MB，超过则读取前 10MB 并添加后缀 `(truncated from <original_size>MB)`
- **CLOB 限制**：1MB，超过则读取前 1MB 并添加后缀 `(truncated)`

**理由**：
- **防止 OOM**：加载超大对象可能导致 Java 进程内存溢出
- **实用平衡**：10MB Base64 编码后约 13MB，1MB 文本对大多数场景足够
- **可配置性**：虽然当前使用硬编码常量，但可以在配置类中定义常量便于未来调整

**替代方案**：
- ❌ **方案 A**：无限制读取
  - 风险：恶意或意外的大对象（如 1GB BLOB）会导致 OOM
- ❌ **方案 B**：完全跳过超大对象
  - 缺点：用户无法获取任何数据，体验差

### 决策 5: JSON 响应格式

**选择**：在现有 JSON 响应中添加 `columnTypes` 数组，保持 `columns` 和 `rows` 格式不变。

```json
{
  "success": true,
  "columns": ["ID", "NAME", "DATA"],
  "columnTypes": ["INTEGER", "VARCHAR2", "BLOB"],
  "rows": [
    [1, "Test", "base64data..."]
  ]
}
```

**理由**：
- **向后兼容**：不使用 `columnTypes` 的旧客户端仍可正常工作
- **类型感知**：新客户端可以根据 `columnTypes` 正确解析字段（如区分 Base64 字符串和普通字符串）

**替代方案**：
- ❌ **方案 A**：将 `rows` 改为对象数组 `{"col1": value, "col2": value}`
  - 缺点：破坏现有 API，Python 端需要修改
  - 缺点：数组格式更紧凑，序列化性能更好

## Risks / Trade-offs

### Risk 1: Base64 编码性能开销

**风险**：大 BLOB（如 10MB）的 Base64 编码可能耗时较长（几百毫秒），影响查询响应时间。

**缓解措施**：
- 记录警告日志，提示用户有大对象被编码
- 在文档中建议避免查询包含大 BLOB 的表，或使用子查询只选择需要的列
- 未来可考虑添加配置项让用户选择是否跳过 BLOB 字段

### Risk 2: 类型兼容性盲点

**风险**：某些罕见的 JDBC 类型可能未在 `getColumnValue()` 中处理，导致降级到 `getObject()` 并可能失败。

**缓解措施**：
- 使用 `default` 分支处理未知类型，记录警告日志
- 在降级逻辑中也使用 `try-catch`，确保不会因未知类型导致查询失败
- 部署后监控日志，收集未知类型出现频率，逐步完善类型映射

### Risk 3: 达梦特有类型支持

**风险**：达梦数据库的特有类型（如 `LONG`, `LONG VARCHAR`, `TEXT`）可能映射到非标准 JDBC 类型常量。

**缓解措施**：
- 在 `getColumnValue()` 中同时检查 JDBC 类型常量和类型名称（`getColumnTypeName()`）
- 例如：`if (type == Types.LONGVARCHAR || "LONG".equals(typeName))`
- 单元测试覆盖达梦特有类型场景

### Risk 4: 截断后的数据丢失

**风险**：超过大小限制的对象被截断，用户可能不知道数据不完整。

**缓解措施**：
- 在截断的值末尾添加明确的警告后缀：`(truncated from <original_size>MB)` 或 `(truncated)`
- 在文档中说明大小限制，建议用户对大对象使用专门的导出工具
- 未来可考虑添加配置项调整大小限制

### Trade-off 1: 内存 vs 完整性

**权衡**：大小限制保护内存，但牺牲了数据完整性。

**决策**：选择内存安全优先，因为：
1. OOM 会导致整个 Java 进程崩溃，影响所有查询
2. 数据截断有明确警告，用户可以感知
3. 对于真正的超大对象，应使用专用工具（如 `dm_dump`）而非 SQL 查询

### Trade-off 2: 复杂性 vs 灵活性

**权衡**：固定转换逻辑简单，但不支持用户自定义。

**决策**：选择固定逻辑，因为：
1. MCP Server 场景下用户不需要高度定制化
2. 固定逻辑易于测试和维护
3. 未来如有需求，可通过配置文件暴露转换策略

## Migration Plan

### 部署步骤

1. **编译 Java 代码**
   ```bash
   javac -cp 'lib/*' db/DmJdbcBridge.java
   ```

2. **更新类文件**
   - 替换 `db/DmJdbcBridge.class`（无需修改 Python 端）

3. **验证部署**
   ```bash
   # 测试基本查询
   python -c "from db.client import create_client; client = create_client(); print(client.execute_query('SELECT 1 FROM DUAL'))"

   # 测试视图定义获取（LONG 类型）
   python -c "from db.client import create_client; client = create_client(); print(client.get_view_definition('SOME_VIEW'))"

   # 测试 BLOB 字段查询
   python -c "from db.client import create_client; client = create_client(); print(client.execute_query('SELECT id, blob_column FROM some_table LIMIT 1'))"
   ```

4. **监控日志**
   - 观察是否有类型转换警告日志
   - 检查是否有未知类型出现

### 回滚策略

**无需回滚**：新实现向后兼容，不会破坏现有功能。如果出现严重问题：

1. **快速修复**：修改代码中的硬编码常量（如大小限制）重新编译
2. **回退代码**：使用 Git 恢复到旧版本并重新编译

### 数据库变更

**无数据库变更**：此修改仅影响 Java 代码层，不涉及数据库结构或配置。

## Open Questions

### Q1: 是否需要支持流式读取大对象？

**背景**：当前设计完整加载大对象到内存，可能导致高内存使用。

**选项**：
- A. 保持当前设计（完整加载，有大小限制）
- B. 实现流式读取（分块返回，增加 API 复杂度）

**建议**：暂缓，先收集生产环境数据。如果大多数 BLOB < 1MB，当前设计足够。

### Q2: 是否需要配置化大小限制？

**背景**：当前 10MB/1MB 限制是硬编码的。

**选项**：
- A. 保持硬编码（简单）
- B. 添加配置项（灵活）

**建议**：暂缓。先使用硬编码值，监控日志中截断事件的频率，再决定是否需要配置化。

### Q3: TIMESTAMP 时区如何处理？

**背景**：达梦数据库的 TIMESTAMP 可能存储时区信息，`getString()` 返回的格式取决于数据库和 JDBC 驱动。

**选项**：
- A. 使用 `getString()`（当前方案，依赖驱动）
- B. 使用 `getTimestamp()` 并手动格式化为 ISO 8601 with timezone

**建议**：先使用方案 A，测试实际输出格式。如果格式不标准，再切换到方案 B。

---

**最后更新**: 2026-02-05
