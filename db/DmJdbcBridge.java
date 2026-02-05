import com.fasterxml.jackson.databind.ObjectMapper;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import com.zaxxer.hikari.HikariPoolMXBean;
import dm.jdbc.driver.DmDriver;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.sql.*;
import java.util.*;
import java.util.Base64;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * DmJdbcBridge - 达梦数据库 JDBC 桥接服务（守护进程模式）
 *
 * 功能：
 * - 通过 stdin/stdout 与 Python 通信（JSON 格式）
 * - 使用 HikariCP 管理连接池
 * - 支持查询和更新操作
 * - 定时发送心跳消息
 * - 优雅关闭连接池
 * - 连接泄漏检测
 * - 智能类型转换（BLOB→Base64, CLOB→String, TIMESTAMP→ISO 8601）
 * - 大对象大小限制保护（BLOB 10MB, CLOB 1MB）
 * - 类型转换失败优雅降级
 *
 * 环境变量：
 * - DM_HOST: 数据库主机
 * - DM_PORT: 数据库端口
 * - DM_USER: 用户名
 * - DM_PASSWORD: 密码
 * - DM_SCHEMA: 默认 schema
 * - DM_POOL_MIN: 最小连接数（默认 2）
 * - DM_POOL_MAX: 最大连接数（默认 20）
 * - DM_POOL_TIMEOUT: 连接超时（毫秒，默认 60000）
 * - DM_STATEMENT_TIMEOUT: 查询超时（秒，默认 120）
 */
public class DmJdbcBridge {
    private HikariDataSource dataSource;
    private BufferedReader reader;
    private ObjectMapper objectMapper;
    private ScheduledExecutorService heartbeatExecutor;
    private volatile boolean running = true;

    // 大对象大小限制常量
    private static final int BLOB_MAX_SIZE = 10 * 1024 * 1024;  // 10MB
    private static final int CLOB_MAX_SIZE = 1 * 1024 * 1024;   // 1MB

    public static void main(String[] args) {
        try {
            DmJdbcBridge bridge = new DmJdbcBridge();

            // 注册 JVM 关闭钩子
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                System.out.println("[INFO] Shutdown hook triggered");
                bridge.shutdown();
            }));

            bridge.run();
        } catch (Exception e) {
            System.err.println("{\"error\": \"FATAL\", \"message\": \"" + escapeJson(e.getMessage()) + "\"}");
            System.exit(1);
        }
    }

    public DmJdbcBridge() {
        this.reader = new BufferedReader(new InputStreamReader(System.in));
        this.objectMapper = new ObjectMapper();
    }

    public void run() throws Exception {
        // 初始化数据库连接池
        initDataSource();

        // 启动心跳定时器
        startHeartbeat();

        // 输出启动成功消息
        System.out.println("{\"status\": \"ready\", \"message\": \"DmJdbcBridge daemon started\"}");
        System.out.flush();

        // 主循环：从 stdin 读取请求并处理
        String line;
        while (running && (line = reader.readLine()) != null) {
            if (line.trim().isEmpty()) continue;

            try {
                // 处理请求
                String response = processRequest(line);
                if (response != null) {
                    System.out.println(response);
                    System.out.flush();
                }
            } catch (Exception e) {
                // 返回错误，但继续运行
                System.out.println("{\"error\": \"true\", \"message\": \"" + escapeJson(e.getMessage()) + "\"}");
                System.out.flush();
            }
        }

        // 清理资源
        shutdown();
    }

    /**
     * 启动心跳定时器
     */
    private void startHeartbeat() {
        heartbeatExecutor = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "heartbeat-thread");
            t.setDaemon(true);
            return t;
        });

        heartbeatExecutor.scheduleAtFixedRate(() -> {
            try {
                Map<String, Object> heartbeat = new HashMap<>();
                heartbeat.put("type", "heartbeat");
                heartbeat.put("timestamp", System.currentTimeMillis());

                String json = objectMapper.writeValueAsString(heartbeat);
                synchronized (System.out) {
                    System.out.println(json);
                    System.out.flush();
                }
            } catch (Exception e) {
                // 心跳失败，记录错误但不中断
                System.err.println("[ERROR] Heartbeat failed: " + e.getMessage());
            }
        }, 15, 15, TimeUnit.SECONDS); // 每 15 秒发送一次心跳
    }

    private void initDataSource() {
        String host = System.getenv("DM_HOST");
        String port = System.getenv("DM_PORT");
        String user = System.getenv("DM_USER");
        String password = System.getenv("DM_PASSWORD");

        if (host == null || port == null || user == null || password == null) {
            throw new RuntimeException("Missing required environment variables (DM_HOST, DM_PORT, DM_USER, DM_PASSWORD)");
        }

        HikariConfig config = new HikariConfig();
        config.setDriverClassName("dm.jdbc.driver.DmDriver");
        config.setJdbcUrl("jdbc:dm://" + host + ":" + port);
        config.setUsername(user);
        config.setPassword(password);

        // 连接池配置（使用新的默认值）
        String poolMin = System.getenv("DM_POOL_MIN");
        String poolMax = System.getenv("DM_POOL_MAX");
        String timeout = System.getenv("DM_POOL_TIMEOUT");
        String statementTimeout = System.getenv("DM_STATEMENT_TIMEOUT");

        config.setMinimumIdle(poolMin != null ? Integer.parseInt(poolMin) : 2);
        config.setMaximumPoolSize(poolMax != null ? Integer.parseInt(poolMax) : 20);
        config.setConnectionTimeout(timeout != null ? Long.parseLong(timeout) : 60000); // 默认 60 秒
        config.setIdleTimeout(300000); // 5 分钟
        config.setMaxLifetime(1800000); // 30 分钟

        // 连接泄漏检测（60 秒）
        config.setLeakDetectionThreshold(60000);

        this.dataSource = new HikariDataSource(config);

        System.out.println("[INFO] HikariCP pool initialized: min=" + config.getMinimumIdle() +
                          ", max=" + config.getMaximumPoolSize() +
                          ", timeout=" + config.getConnectionTimeout());
    }

    @SuppressWarnings("unchecked")
    private String processRequest(String jsonRequest) throws Exception {
        // 使用 Jackson 解析 JSON
        Map<String, Object> request = objectMapper.readValue(jsonRequest, Map.class);
        String type = (String) request.get("type");

        // 处理 shutdown 消息
        if ("shutdown".equals(type)) {
            System.out.println("[INFO] Received shutdown message");
            running = false;
            return "{\"status\": \"shutting_down\"}";
        }

        // 处理 pool_status 查询
        if ("pool_status".equals(type)) {
            return getPoolStatus();
        }

        String sql = (String) request.get("sql");
        List<String> params = (List<String>) request.get("params");

        if (sql == null) {
            return "{\"error\": \"true\", \"message\": \"Missing 'sql' field in request\"}";
        }

        // 使用 try-with-resources 确保连接自动关闭
        try (Connection conn = dataSource.getConnection()) {
            // 设置默认 schema（使用引号避免大小写问题）
            String schema = System.getenv("DM_SCHEMA");
            if (schema != null && !schema.isEmpty()) {
                try (Statement stmt = conn.createStatement()) {
                    stmt.execute("SET SCHEMA \"" + schema + "\"");
                }
            }

            if (sql.toUpperCase().trim().startsWith("SELECT")) {
                return executeQuery(conn, sql, params);
            } else {
                return executeUpdate(conn, sql, params);
            }
        }
    }

    /**
     * 获取连接池状态
     */
    private String getPoolStatus() {
        try {
            HikariPoolMXBean poolProxy = dataSource.getHikariPoolMXBean();

            Map<String, Object> status = new HashMap<>();
            status.put("success", true);
            status.put("active_connections", poolProxy.getActiveConnections());
            status.put("idle_connections", poolProxy.getIdleConnections());
            status.put("total_connections", poolProxy.getTotalConnections());
            status.put("threads_awaiting_connection", poolProxy.getThreadsAwaitingConnection());
            status.put("pool_size", dataSource.getMaximumPoolSize());

            return objectMapper.writeValueAsString(status);
        } catch (Exception e) {
            return "{\"error\": \"true\", \"message\": \"" + escapeJson(e.getMessage()) + "\"}";
        }
    }

    private String executeQuery(Connection conn, String sql, List<String> params) throws Exception {
        // 使用 try-with-resources 自动关闭 PreparedStatement
        try (PreparedStatement stmt = prepareStatement(conn, sql, params)) {

            // 设置查询超时（防止长时间占用连接）
            String statementTimeout = System.getenv("DM_STATEMENT_TIMEOUT");
            if (statementTimeout != null) {
                stmt.setQueryTimeout(Integer.parseInt(statementTimeout));
            } else {
                stmt.setQueryTimeout(120); // 默认 120 秒
            }

            // 使用 try-with-resources 自动关闭 ResultSet
            try (ResultSet rs = stmt.executeQuery()) {
                ResultSetMetaData metaData = rs.getMetaData();
                int columnCount = metaData.getColumnCount();

                // 使用 Jackson 构建 JSON 结果
                Map<String, Object> result = new HashMap<>();
                result.put("success", true);

                // 列名
                List<String> columns = new ArrayList<>();
                for (int i = 1; i <= columnCount; i++) {
                    columns.add(metaData.getColumnName(i));
                }
                result.put("columns", columns);

                // 列类型（JDBC 类型名称）
                List<String> columnTypes = new ArrayList<>();
                for (int i = 1; i <= columnCount; i++) {
                    columnTypes.add(metaData.getColumnTypeName(i));
                }
                result.put("columnTypes", columnTypes);

                // 数据行（使用类型感知的值转换）
                List<List<Object>> rows = new ArrayList<>();
                while (rs.next()) {
                    List<Object> row = new ArrayList<>();
                    for (int i = 1; i <= columnCount; i++) {
                        Object value = getColumnValue(rs, i, metaData);
                        row.add(value);
                    }
                    rows.add(row);
                }
                result.put("rows", rows);
                result.put("rowCount", -1);

                return objectMapper.writeValueAsString(result);
            }
            // rs 和 stmt 都会自动关闭
        }
    }

    private String executeUpdate(Connection conn, String sql, List<String> params) throws Exception {
        // 使用 try-with-resources 自动关闭 PreparedStatement
        try (PreparedStatement stmt = prepareStatement(conn, sql, params)) {
            // 设置查询超时
            String statementTimeout = System.getenv("DM_STATEMENT_TIMEOUT");
            if (statementTimeout != null) {
                stmt.setQueryTimeout(Integer.parseInt(statementTimeout));
            } else {
                stmt.setQueryTimeout(120);
            }

            int affectedRows = stmt.executeUpdate();
            Map<String, Object> result = new HashMap<>();
            result.put("success", true);
            result.put("affectedRows", affectedRows);
            return objectMapper.writeValueAsString(result);
        }
        // stmt 会自动关闭
    }

    /**
     * 类型感知的列值读取
     *
     * 根据 JDBC 类型选择合适的读取方法，确保返回的对象能被 Jackson 序列化为 JSON。
     *
     * @param rs ResultSet
     * @param column 列索引（从 1 开始）
     * @param meta ResultSetMetaData
     * @return 可序列化的对象（String、Number、Boolean、null）
     */
    private Object getColumnValue(ResultSet rs, int column, ResultSetMetaData meta) {
        try {
            int columnType = meta.getColumnType(column);
            String columnTypeName = meta.getColumnTypeName(column);
            String columnName = meta.getColumnName(column);

            // BLOB 类型 → Base64 字符串
            if (columnType == Types.BLOB) {
                try {
                    byte[] bytes = rs.getBytes(column);
                    if (bytes == null || rs.wasNull()) {
                        return null;
                    }

                    // 检查大小限制
                    if (bytes.length > BLOB_MAX_SIZE) {
                        double originalSizeMB = bytes.length / (1024.0 * 1024.0);
                        System.err.println("[WARN] BLOB column '" + columnName + "' size " +
                                String.format("%.2f", originalSizeMB) + "MB exceeds limit " +
                                (BLOB_MAX_SIZE / (1024 * 1024)) + "MB, truncating");

                        // 截断前 10MB
                        byte[] truncatedBytes = Arrays.copyOf(bytes, BLOB_MAX_SIZE);
                        String base64 = Base64.getEncoder().encodeToString(truncatedBytes);
                        return base64 + " (truncated from " + String.format("%.2f", originalSizeMB) + "MB)";
                    }

                    // Base64 编码
                    return Base64.getEncoder().encodeToString(bytes);
                } catch (Exception e) {
                    String error = "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                    System.err.println("[WARN] Failed to convert BLOB column '" + columnName + "': " + e.getMessage());
                    return error;
                }
            }

            // CLOB、LONGVARCHAR、LONG、LONG VARCHAR、TEXT 类型 → 字符串
            if (columnType == Types.CLOB || columnType == Types.LONGVARCHAR ||
                    "LONG".equalsIgnoreCase(columnTypeName) ||
                    "LONG VARCHAR".equalsIgnoreCase(columnTypeName) ||
                    "TEXT".equalsIgnoreCase(columnTypeName)) {

                try {
                    String text = rs.getString(column);
                    if (text == null || rs.wasNull()) {
                        return null;
                    }

                    // 检查长度限制
                    if (text.length() > CLOB_MAX_SIZE) {
                        double originalSizeMB = text.length() / (1024.0 * 1024.0);
                        System.err.println("[WARN] CLOB column '" + columnName + "' length " +
                                String.format("%.2f", originalSizeMB) + "MB exceeds limit " +
                                (CLOB_MAX_SIZE / (1024 * 1024)) + "MB, truncating");

                        // 截断前 1MB 并添加警告后缀
                        return text.substring(0, CLOB_MAX_SIZE) + " (truncated)";
                    }

                    return text;
                } catch (Exception e) {
                    String error = "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                    System.err.println("[WARN] Failed to convert CLOB column '" + columnName + "': " + e.getMessage());
                    return error;
                }
            }

            // TIMESTAMP、DATE 类型 → ISO 8601 字符串
            if (columnType == Types.TIMESTAMP || columnType == Types.DATE || columnType == Types.TIME) {
                try {
                    // 使用 getString() 获取，JDBC 驱动会返回标准格式
                    String value = rs.getString(column);
                    if (value == null || rs.wasNull()) {
                        return null;
                    }
                    return value;
                } catch (Exception e) {
                    String error = "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                    System.err.println("[WARN] Failed to convert TIMESTAMP column '" + columnName + "': " + e.getMessage());
                    return error;
                }
            }

            // DECIMAL、NUMERIC 类型 → BigDecimal（Jackson 序列化为数字）
            if (columnType == Types.DECIMAL || columnType == Types.NUMERIC) {
                try {
                    Object value = rs.getObject(column);
                    if (value == null || rs.wasNull()) {
                        return null;
                    }
                    // getBigDecimal() 会返回 BigDecimal，Jackson 会正确序列化
                    return rs.getBigDecimal(column);
                } catch (Exception e) {
                    String error = "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                    System.err.println("[WARN] Failed to convert DECIMAL column '" + columnName + "': " + e.getMessage());
                    return error;
                }
            }

            // 其他类型使用默认处理（getObject）
            Object value = rs.getObject(column);
            if (value == null || rs.wasNull()) {
                return null;
            }

            // 检查返回值是否可序列化（常见的可序列化类型）
            if (value instanceof String || value instanceof Number ||
                value instanceof Boolean || value instanceof Map || value instanceof List) {
                return value;
            }

            // 未知类型，尝试转换为字符串
            try {
                return value.toString();
            } catch (Exception e) {
                String error = "<类型转换失败: 无法序列化类型 " + value.getClass().getName() + ">";
                System.err.println("[WARN] Cannot serialize column '" + columnName + "' of type " +
                        value.getClass().getName() + ", converting to error string");
                return error;
            }

        } catch (SQLException e) {
            String error = "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
            System.err.println("[WARN] SQLException while reading column value: " + e.getMessage());
            return error;
        }
    }

    /**
     * 准备带参数的 PreparedStatement
     */
    private PreparedStatement prepareStatement(Connection conn, String sql, List<String> params) throws Exception {
        PreparedStatement stmt;
        if (params != null && !params.isEmpty()) {
            stmt = conn.prepareStatement(sql);
            for (int i = 0; i < params.size(); i++) {
                stmt.setString(i + 1, params.get(i));
            }
        } else {
            stmt = conn.prepareStatement(sql);
        }
        return stmt;
    }

    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    /**
     * 优雅关闭资源
     */
    private void shutdown() {
        System.out.println("[INFO] Shutting down DmJdbcBridge...");

        // 停止心跳定时器
        if (heartbeatExecutor != null && !heartbeatExecutor.isShutdown()) {
            heartbeatExecutor.shutdownNow();
            System.out.println("[INFO] Heartbeat executor stopped");
        }

        // 关闭连接池
        if (dataSource != null && !dataSource.isClosed()) {
            System.out.println("[INFO] HikariCP pool is shutting down, active connections: " +
                            dataSource.getHikariPoolMXBean().getActiveConnections());
            dataSource.close();
            System.out.println("[INFO] HikariCP pool closed");
        }

        System.out.println("[INFO] DmJdbcBridge shutdown complete");
    }
}
