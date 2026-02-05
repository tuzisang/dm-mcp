import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dm.jdbc.driver.DmDriver;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.sql.*;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

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
    private ExecutorService executor;

    public static void main(String[] args) {
        try {
            DmJdbcBridge bridge = new DmJdbcBridge();
            bridge.run();
        } catch (Exception e) {
            System.err.println("{\"error\": \"FATAL\", \"message\": \"" + e.getMessage().replace("\\", "\\\\").replace("\"", "\\\"") + "\"}");
            System.exit(1);
        }
    }

    public DmJdbcBridge() {
        this.reader = new BufferedReader(new InputStreamReader(System.in));
        this.executor = Executors.newSingleThreadExecutor();
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

    private String processRequest(String jsonRequest) throws Exception {
        // 简单解析 JSON（避免引入额外的 JSON 库）
        String sql = extractJsonValue(jsonRequest, "sql");
        String paramsStr = extractJsonValue(jsonRequest, "params");

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
                return executeQuery(conn, sql, paramsStr);
            } else {
                return executeUpdate(conn, sql, paramsStr);
            }
        }
    }

    private String executeQuery(Connection conn, String sql, String paramsStr) throws Exception {
        PreparedStatement stmt;
        ResultSet rs;

        if (paramsStr != null && !paramsStr.equals("null") && !paramsStr.equals("[]")) {
            // 解析参数数组
            List<String> params = parseJsonArray(paramsStr);
            stmt = conn.prepareStatement(sql);
            for (int i = 0; i < params.size(); i++) {
                stmt.setString(i + 1, params.get(i));
            }
        } else {
            stmt = conn.prepareStatement(sql);
        }

        rs = stmt.executeQuery();

        // 获取列信息
        ResultSetMetaData metaData = rs.getMetaData();
        int columnCount = metaData.getColumnCount();

        // 构建 JSON 结果
        StringBuilder json = new StringBuilder();
        json.append("{\"success\": true, \"columns\": [");

        // 列名
        for (int i = 1; i <= columnCount; i++) {
            if (i > 1) json.append(",");
            json.append("\"").append(escapeJson(metaData.getColumnName(i))).append("\"");
        }

        json.append("], \"rows\": [");

        // 数据行
        boolean firstRow = true;
        while (rs.next()) {
            if (!firstRow) json.append(",");
            firstRow = false;

            json.append("[");
            for (int i = 1; i <= columnCount; i++) {
                if (i > 1) json.append(",");

                Object value = rs.getObject(i);
                if (value == null) {
                    json.append("null");
                } else if (value instanceof Number) {
                    json.append(value);
                } else if (value instanceof Boolean) {
                    json.append(value);
                } else {
                    json.append("\"").append(escapeJson(value.toString())).append("\"");
                }
            }
            json.append("]");
        }

        json.append("], \"rowCount\": ").append(getRowCount(metaData, conn)).append("}");

        rs.close();
        stmt.close();

        return json.toString();
    }

    private String executeUpdate(Connection conn, String sql, String paramsStr) throws Exception {
        PreparedStatement stmt;

        if (paramsStr != null && !paramsStr.equals("null") && !paramsStr.equals("[]")) {
            List<String> params = parseJsonArray(paramsStr);
            stmt = conn.prepareStatement(sql);
            for (int i = 0; i < params.size(); i++) {
                stmt.setString(i + 1, params.get(i));
            }
        } else {
            stmt = conn.prepareStatement(sql);
        }

        int affectedRows = stmt.executeUpdate();
        stmt.close();

        return "{\"success\": true, \"affectedRows\": " + affectedRows + "}";
    }

    private int getRowCount(ResultSetMetaData metaData, Connection conn) throws Exception {
        // 对于达梦数据库，使用 USER_TABLES 获取表数量
        String tableName = metaData.getTableName(1);
        if (tableName != null && !tableName.isEmpty()) {
            try (Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM " + tableName)) {
                if (rs.next()) {
                    return rs.getInt(1);
                }
            }
        }
        return -1; // 无法获取
    }

    private List<String> parseJsonArray(String jsonArray) {
        List<String> result = new ArrayList<>();
        String content = jsonArray.trim();
        if (content.startsWith("[") && content.endsWith("]")) {
            content = content.substring(1, content.length() - 1);
            String[] parts = content.split(",");
            for (String part : parts) {
                part = part.trim();
                if (!part.isEmpty()) {
                    // 移除引号
                    if (part.startsWith("\"") && part.endsWith("\"")) {
                        part = part.substring(1, part.length() - 1);
                    }
                    // 处理转义
                    part = part.replace("\\\"", "\"").replace("\\\\", "\\");
                    result.add(part);
                }
            }
        }
        return result;
    }

    private String extractJsonValue(String json, String key) {
        String searchKey = "\"" + key + "\"";
        int keyIndex = json.indexOf(searchKey);
        if (keyIndex == -1) return null;

        int colonIndex = json.indexOf(":", keyIndex);
        if (colonIndex == -1) return null;

        String rest = json.substring(colonIndex + 1).trim();

        if (rest.startsWith("[")) {
            // 数组值
            int end = rest.indexOf("]");
            if (end == -1) return null;
            return rest.substring(0, end + 1);
        } else if (rest.startsWith("\"")) {
            // 字符串值
            int end = rest.indexOf("\"", 1);
            if (end == -1) return null;
            return rest.substring(1, end);
        } else {
            // 数字或布尔值
            int commaIndex = rest.indexOf(",");
            int braceIndex = rest.indexOf("}");
            int end = Math.min(commaIndex == -1 ? Integer.MAX_VALUE : commaIndex,
                             braceIndex == -1 ? Integer.MAX_VALUE : braceIndex);
            if (end == Integer.MAX_VALUE) return null;
            return rest.substring(0, end).trim();
        }
    }

    private String escapeJson(String s) {
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
        if (executor != null) {
            executor.shutdown();
        }
    }
}
