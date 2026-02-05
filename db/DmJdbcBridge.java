import com.fasterxml.jackson.databind.ObjectMapper;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dm.jdbc.driver.DmDriver;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.sql.*;
import java.util.*;

/**
 * DmJdbcBridge - 达梦数据库 JDBC 桥接服务（守护进程模式）
 *
 * 功能：
 * - 通过 stdin/stdout 与 Python 通信（JSON 格式）
 * - 使用 HikariCP 管理连接池
 * - 支持查询和更新操作
 * - 长期运行，不退出
 *
 * 环境变量：
 * - DM_HOST: 数据库主机
 * - DM_PORT: 数据库端口
 * - DM_USER: 用户名
 * - DM_PASSWORD: 密码
 * - DM_SCHEMA: 默认 schema
 */
public class DmJdbcBridge {
    private HikariDataSource dataSource;
    private BufferedReader reader;
    private ObjectMapper objectMapper;

    public static void main(String[] args) {
        try {
            DmJdbcBridge bridge = new DmJdbcBridge();
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

        // 输出启动成功消息
        System.out.println("{\"status\": \"ready\", \"message\": \"DmJdbcBridge daemon started\"}");
        System.out.flush();

        // 主循环：从 stdin 读取请求并处理
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.trim().isEmpty()) continue;

            try {
                // 处理请求
                String response = processRequest(line);
                System.out.println(response);
                System.out.flush();
            } catch (Exception e) {
                // 返回错误，但继续运行
                System.out.println("{\"error\": \"true\", \"message\": \"" + escapeJson(e.getMessage()) + "\"}");
                System.out.flush();
            }
        }

        // 清理资源
        shutdown();
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

        // 连接池配置
        String poolMin = System.getenv("DM_POOL_MIN");
        String poolMax = System.getenv("DM_POOL_MAX");
        String timeout = System.getenv("DM_POOL_TIMEOUT");

        config.setMinimumIdle(poolMin != null ? Integer.parseInt(poolMin) : 2);
        config.setMaximumPoolSize(poolMax != null ? Integer.parseInt(poolMax) : 10);
        config.setConnectionTimeout(timeout != null ? Long.parseLong(timeout) : 30000);
        config.setIdleTimeout(300000); // 5 分钟
        config.setMaxLifetime(1800000); // 30 分钟

        this.dataSource = new HikariDataSource(config);
    }

    @SuppressWarnings("unchecked")
    private String processRequest(String jsonRequest) throws Exception {
        // 使用 Jackson 解析 JSON
        Map<String, Object> request = objectMapper.readValue(jsonRequest, Map.class);
        String sql = (String) request.get("sql");
        List<String> params = (List<String>) request.get("params");

        if (sql == null) {
            return "{\"error\": \"true\", \"message\": \"Missing 'sql' field in request\"}";
        }

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

    private String executeQuery(Connection conn, String sql, List<String> params) throws Exception {
        PreparedStatement stmt = prepareStatement(conn, sql, params);

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

            // 数据行
            List<List<Object>> rows = new ArrayList<>();
            while (rs.next()) {
                List<Object> row = new ArrayList<>();
                for (int i = 1; i <= columnCount; i++) {
                    Object value = rs.getObject(i);
                    row.add(value);
                }
                rows.add(row);
            }
            result.put("rows", rows);
            result.put("rowCount", -1);

            return objectMapper.writeValueAsString(result);
        }
        // stmt 和 rs 都会自动关闭
    }

    private String executeUpdate(Connection conn, String sql, List<String> params) throws Exception {
        PreparedStatement stmt = prepareStatement(conn, sql, params);

        try {
            int affectedRows = stmt.executeUpdate();
            Map<String, Object> result = new HashMap<>();
            result.put("success", true);
            result.put("affectedRows", affectedRows);
            return objectMapper.writeValueAsString(result);
        } finally {
            stmt.close();
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

    private void shutdown() {
        if (dataSource != null) {
            dataSource.close();
        }
    }
}
