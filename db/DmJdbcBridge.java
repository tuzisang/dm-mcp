import com.fasterxml.jackson.databind.ObjectMapper;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import dm.jdbc.driver.DmdbStatement;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Types;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 最小化的达梦 JDBC 桥接守护进程。
 *
 * 仅保留：
 * - ready / shutdown 协议
 * - HikariCP 连接池
 * - SELECT / EXPLAIN / EXPLAIN_PLAN 执行
 * - 执行计划兼容逻辑
 */
public class DmJdbcBridge {
    private HikariDataSource dataSource;
    private final BufferedReader reader;
    private final ObjectMapper objectMapper;
    private volatile boolean running = true;

    private static final int BLOB_MAX_SIZE = 10 * 1024 * 1024;
    private static final int CLOB_MAX_SIZE = 1 * 1024 * 1024;

    public static void main(String[] args) {
        try {
            DmJdbcBridge bridge = new DmJdbcBridge();
            Runtime.getRuntime().addShutdownHook(new Thread(bridge::shutdown));
            bridge.run();
        } catch (Exception e) {
            System.err.println("{\"error\":\"FATAL\",\"message\":\"" + escapeJson(e.getMessage()) + "\"}");
            System.exit(1);
        }
    }

    public DmJdbcBridge() {
        this.reader = new BufferedReader(new InputStreamReader(System.in));
        this.objectMapper = new ObjectMapper();
    }

    public void run() throws Exception {
        initDataSource();
        System.out.println("{\"status\":\"ready\",\"message\":\"DmJdbcBridge daemon started\"}");
        System.out.flush();

        String line;
        while (running && (line = reader.readLine()) != null) {
            if (line.trim().isEmpty()) {
                continue;
            }

            try {
                String response = processRequest(line);
                if (response != null) {
                    System.out.println(response);
                    System.out.flush();
                }
            } catch (Exception e) {
                System.out.println("{\"error\":\"true\",\"message\":\"" + escapeJson(e.getMessage()) + "\"}");
                System.out.flush();
            }
        }

        shutdown();
    }

    private void initDataSource() {
        String host = requiredEnv("DM_HOST");
        String port = requiredEnv("DM_PORT");
        String user = requiredEnv("DM_USER");
        String password = requiredEnv("DM_PASSWORD");

        HikariConfig config = new HikariConfig();
        config.setDriverClassName("dm.jdbc.driver.DmDriver");
        config.setJdbcUrl("jdbc:dm://" + host + ":" + port);
        config.setUsername(user);
        config.setPassword(password);
        config.setMinimumIdle(parseIntEnv("DM_POOL_MIN", 2));
        config.setMaximumPoolSize(parseIntEnv("DM_POOL_MAX", 20));
        config.setConnectionTimeout(parseLongEnv("DM_POOL_TIMEOUT", 60000L));
        config.setIdleTimeout(300000L);
        config.setMaxLifetime(1800000L);
        config.setLeakDetectionThreshold(60000L);

        this.dataSource = new HikariDataSource(config);
    }

    private String processRequest(String jsonRequest) throws Exception {
        @SuppressWarnings("unchecked")
        Map<String, Object> request = objectMapper.readValue(jsonRequest, Map.class);
        String type = stringValue(request.get("type"));
        if ("shutdown".equals(type)) {
            running = false;
            return "{\"status\":\"shutting_down\"}";
        }

        String sql = stringValue(request.get("sql"));
        if (sql == null || sql.trim().isEmpty()) {
            throw new SQLException("Missing 'sql' field in request");
        }

        String statementType = normalizeStatementType(stringValue(request.get("statement_type")), sql);

        try (Connection conn = dataSource.getConnection()) {
            setSchema(conn);

            if ("SELECT".equals(statementType) || "EXPLAIN".equals(statementType)) {
                return objectMapper.writeValueAsString(executeQuery(conn, sql, statementType));
            }
            if ("EXPLAIN_PLAN".equals(statementType)) {
                return executeExplainPlan(conn, sql);
            }

            throw new SQLException("Only read-only SELECT and EXPLAIN requests are supported");
        }
    }

    private void setSchema(Connection conn) throws Exception {
        String schema = System.getenv("DM_SCHEMA");
        if (schema == null || schema.isEmpty()) {
            return;
        }

        try (Statement stmt = conn.createStatement()) {
            stmt.execute("SET SCHEMA \"" + schema + "\"");
        }
    }

    private String normalizeStatementType(String statementType, String sql) {
        if (statementType != null && !statementType.trim().isEmpty()) {
            return statementType.trim().toUpperCase(Locale.ROOT);
        }

        String normalized = sql.trim().toUpperCase(Locale.ROOT);
        if (normalized.startsWith("EXPLAIN PLAN")) {
            return "EXPLAIN_PLAN";
        }
        if (normalized.startsWith("EXPLAIN")) {
            return "EXPLAIN";
        }
        if (normalized.startsWith("SELECT")) {
            return "SELECT";
        }
        return "UNSUPPORTED";
    }

    private Map<String, Object> executeQuery(Connection conn, String sql, String statementType) throws Exception {
        int timeout = getStatementTimeoutSeconds();

        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            boolean hasResultSet = stmt.execute(sql);

            if (!hasResultSet) {
                if ("EXPLAIN".equals(statementType)) {
                    return explainTextToMap(stmt);
                }
                return createEmptyQueryResult();
            }

            try (ResultSet rs = stmt.getResultSet()) {
                return resultSetToMap(rs);
            }
        }
    }

    private Map<String, Object> explainTextToMap(Statement stmt) throws Exception {
        DmdbStatement dmStmt = stmt.unwrap(DmdbStatement.class);
        String explain = dmStmt.getExplain();

        if (explain == null || explain.trim().isEmpty()) {
            throw new SQLException(
                    "EXPLAIN 已执行，但达梦 JDBC 未返回 ResultSet，且 getExplain() 未返回可读取的计划文本"
            );
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("columns", Collections.singletonList("PLAN_LINE"));
        result.put("columnTypes", Collections.singletonList("VARCHAR"));

        List<List<Object>> rows = new ArrayList<>();
        String[] lines = explain.split("\\R");
        for (String line : lines) {
            if (line == null || line.trim().isEmpty()) {
                continue;
            }
            rows.add(Collections.singletonList(line.replaceFirst("\\s+$", "")));
        }

        if (rows.isEmpty()) {
            throw new SQLException("EXPLAIN 已执行，但达梦 JDBC 返回的计划文本为空");
        }

        result.put("rows", rows);
        result.put("rowCount", rows.size());
        return result;
    }

    private String executeExplainPlan(Connection conn, String sql) throws Exception {
        int timeout = getStatementTimeoutSeconds();
        Set<String> planTableColumns = getPlanTableColumns(conn, timeout);

        if (planTableColumns.contains("STATEMENT_ID")) {
            return executeExplainPlanWithStatementId(conn, sql, timeout, planTableColumns);
        }

        return executeExplainPlanWithSessionCleanup(conn, sql, timeout, planTableColumns);
    }

    private int getStatementTimeoutSeconds() {
        return parseIntEnv("DM_STATEMENT_TIMEOUT", 120);
    }

    private Map<String, Object> createEmptyQueryResult() {
        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        result.put("columns", Collections.emptyList());
        result.put("columnTypes", Collections.emptyList());
        result.put("rows", Collections.emptyList());
        result.put("rowCount", 0);
        return result;
    }

    private Map<String, Object> resultSetToMap(ResultSet rs) throws Exception {
        if (rs == null) {
            return createEmptyQueryResult();
        }

        ResultSetMetaData metaData = rs.getMetaData();
        int columnCount = metaData.getColumnCount();

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);

        List<String> columns = new ArrayList<>();
        for (int i = 1; i <= columnCount; i++) {
            columns.add(metaData.getColumnName(i));
        }
        result.put("columns", columns);

        List<String> columnTypes = new ArrayList<>();
        for (int i = 1; i <= columnCount; i++) {
            columnTypes.add(metaData.getColumnTypeName(i));
        }
        result.put("columnTypes", columnTypes);

        List<List<Object>> rows = new ArrayList<>();
        while (rs.next()) {
            List<Object> row = new ArrayList<>();
            for (int i = 1; i <= columnCount; i++) {
                row.add(getColumnValue(rs, i, metaData));
            }
            rows.add(row);
        }

        result.put("rows", rows);
        result.put("rowCount", rows.size());
        return result;
    }

    private Set<String> getPlanTableColumns(Connection conn, int timeout) throws Exception {
        Set<String> columns = new LinkedHashSet<>();

        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            try (ResultSet rs = stmt.executeQuery("SELECT * FROM PLAN_TABLE WHERE 1 = 0")) {
                ResultSetMetaData metaData = rs.getMetaData();
                int columnCount = metaData.getColumnCount();
                for (int i = 1; i <= columnCount; i++) {
                    columns.add(normalizeColumnName(metaData.getColumnName(i)));
                }
            }
        }

        return columns;
    }

    private String normalizeColumnName(String columnName) {
        if (columnName == null) {
            return "";
        }
        return columnName.trim().toUpperCase(Locale.ROOT);
    }

    private String buildPlanQuery(Set<String> planTableColumns, String whereClause) {
        List<String> preferredColumns = Arrays.asList(
                "ID", "PARENT_ID", "OPERATION", "OPTIONS", "OBJECT_NAME", "POSITION", "COST", "REMARK"
        );
        List<String> selectedColumns = new ArrayList<>();
        for (String column : preferredColumns) {
            if (planTableColumns.contains(column)) {
                selectedColumns.add(column);
            }
        }

        String selectClause = selectedColumns.isEmpty() ? "*" : String.join(", ", selectedColumns);
        StringBuilder query = new StringBuilder("SELECT ").append(selectClause).append(" FROM PLAN_TABLE");

        if (whereClause != null && !whereClause.trim().isEmpty()) {
            query.append(" WHERE ").append(whereClause);
        }

        if (planTableColumns.contains("ID")) {
            query.append(" ORDER BY ID");
        }

        return query.toString();
    }

    private Map<String, Object> readPlanRows(Connection conn, int timeout, Set<String> planTableColumns, String whereClause) throws Exception {
        String planQuery = buildPlanQuery(planTableColumns, whereClause);

        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            try (ResultSet rs = stmt.executeQuery(planQuery)) {
                Map<String, Object> result = resultSetToMap(rs);
                result.put("plan_table_row_count", result.get("rowCount"));
                return result;
            }
        }
    }

    private Map<String, Object> requirePlanRows(Map<String, Object> result) throws SQLException {
        Object rowCountValue = result.get("rowCount");
        int rowCount = 0;
        if (rowCountValue instanceof Number) {
            rowCount = ((Number) rowCountValue).intValue();
        }

        if (rowCount > 0) {
            return result;
        }

        throw planCompatibilityError(
                "EXPLAIN PLAN 已执行，但 PLAN_TABLE 未返回任何计划行，目标环境可能未将执行计划写入 PLAN_TABLE"
        );
    }

    private int countPlanTableRows(Connection conn, int timeout) throws Exception {
        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            try (ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM PLAN_TABLE")) {
                if (rs.next()) {
                    return rs.getInt(1);
                }
            }
        }

        return 0;
    }

    private void clearPlanTable(Connection conn, int timeout) throws Exception {
        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            stmt.executeUpdate("DELETE FROM PLAN_TABLE");
        }
    }

    private SQLException planCompatibilityError(String detail) {
        return new SQLException("当前 PLAN_TABLE 结构不支持安全隔离本次执行计划: " + detail);
    }

    private String executeExplainPlanWithStatementId(Connection conn, String sql, int timeout, Set<String> planTableColumns) throws Exception {
        String statementId = "MCP_" + System.currentTimeMillis() + "_" + Thread.currentThread().getId();

        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);

            try {
                stmt.execute("CALL SP_SET_PLAN_TABLE_STMTID('" + statementId + "')");
            } catch (Exception e) {
                System.err.println("[WARN] Failed to set STATEMENT_ID isolation: " + e.getMessage());
            }

            stmt.execute(sql);
        }

        try {
            Map<String, Object> result = requirePlanRows(
                    readPlanRows(conn, timeout, planTableColumns, "STATEMENT_ID = '" + statementId + "'")
            );
            return objectMapper.writeValueAsString(result);
        } finally {
            try (Statement cleanupStmt = conn.createStatement()) {
                cleanupStmt.setQueryTimeout(timeout);
                cleanupStmt.executeUpdate("DELETE FROM PLAN_TABLE WHERE STATEMENT_ID = '" + statementId + "'");
            } catch (Exception e) {
                System.err.println("[WARN] Failed to cleanup PLAN_TABLE rows by STATEMENT_ID: " + e.getMessage());
            }
        }
    }

    private String executeExplainPlanWithSessionCleanup(Connection conn, String sql, int timeout, Set<String> planTableColumns) throws Exception {
        try {
            clearPlanTable(conn, timeout);
        } catch (Exception e) {
            throw planCompatibilityError("PLAN_TABLE 缺少 STATEMENT_ID，且无法完成当前 session 计划表清理: " + e.getMessage());
        }

        int residualBeforeExplain = countPlanTableRows(conn, timeout);
        if (residualBeforeExplain != 0) {
            throw planCompatibilityError(
                    "PLAN_TABLE 缺少 STATEMENT_ID，清理后当前 session 仍可见 "
                            + residualBeforeExplain + " 行计划，无法确认本次结果隔离"
            );
        }

        try (Statement stmt = conn.createStatement()) {
            stmt.setQueryTimeout(timeout);
            stmt.execute(sql);
        }

        try {
            Map<String, Object> result = requirePlanRows(readPlanRows(conn, timeout, planTableColumns, null));
            return objectMapper.writeValueAsString(result);
        } finally {
            try {
                clearPlanTable(conn, timeout);
            } catch (Exception e) {
                System.err.println("[WARN] Failed to cleanup PLAN_TABLE rows without STATEMENT_ID: " + e.getMessage());
            }
        }
    }

    private Object getColumnValue(ResultSet rs, int column, ResultSetMetaData meta) {
        try {
            int columnType = meta.getColumnType(column);
            String columnTypeName = meta.getColumnTypeName(column);
            String columnName = meta.getColumnName(column);

            if (columnType == Types.BLOB) {
                try {
                    byte[] bytes = rs.getBytes(column);
                    if (bytes == null || rs.wasNull()) {
                        return null;
                    }
                    if (bytes.length > BLOB_MAX_SIZE) {
                        double originalSizeMB = bytes.length / (1024.0 * 1024.0);
                        byte[] truncatedBytes = Arrays.copyOf(bytes, BLOB_MAX_SIZE);
                        String base64 = Base64.getEncoder().encodeToString(truncatedBytes);
                        return base64 + " (truncated from " + String.format("%.2f", originalSizeMB) + "MB)";
                    }
                    return Base64.getEncoder().encodeToString(bytes);
                } catch (Exception e) {
                    System.err.println("[WARN] Failed to convert BLOB column '" + columnName + "': " + e.getMessage());
                    return "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                }
            }

            if (columnType == Types.CLOB || columnType == Types.LONGVARCHAR
                    || "LONG".equalsIgnoreCase(columnTypeName)
                    || "LONG VARCHAR".equalsIgnoreCase(columnTypeName)
                    || "TEXT".equalsIgnoreCase(columnTypeName)) {
                try {
                    String text = rs.getString(column);
                    if (text == null || rs.wasNull()) {
                        return null;
                    }
                    if (text.length() > CLOB_MAX_SIZE) {
                        return text.substring(0, CLOB_MAX_SIZE) + " (truncated)";
                    }
                    return text;
                } catch (Exception e) {
                    System.err.println("[WARN] Failed to convert CLOB column '" + columnName + "': " + e.getMessage());
                    return "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                }
            }

            if (columnType == Types.TIMESTAMP || columnType == Types.DATE || columnType == Types.TIME) {
                try {
                    String value = rs.getString(column);
                    if (value == null || rs.wasNull()) {
                        return null;
                    }
                    return value;
                } catch (Exception e) {
                    System.err.println("[WARN] Failed to convert TIMESTAMP column '" + columnName + "': " + e.getMessage());
                    return "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                }
            }

            if (columnType == Types.DECIMAL || columnType == Types.NUMERIC) {
                try {
                    Object value = rs.getObject(column);
                    if (value == null || rs.wasNull()) {
                        return null;
                    }
                    return rs.getBigDecimal(column);
                } catch (Exception e) {
                    System.err.println("[WARN] Failed to convert DECIMAL column '" + columnName + "': " + e.getMessage());
                    return "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
                }
            }

            Object value = rs.getObject(column);
            if (value == null || rs.wasNull()) {
                return null;
            }
            if (value instanceof String || value instanceof Number || value instanceof Boolean
                    || value instanceof Map || value instanceof List) {
                return value;
            }
            return value.toString();
        } catch (SQLException e) {
            System.err.println("[WARN] SQLException while reading column value: " + e.getMessage());
            return "<类型转换失败: " + escapeJson(e.getMessage()) + ">";
        }
    }

    private String stringValue(Object value) {
        return value == null ? null : value.toString();
    }

    private String requiredEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.trim().isEmpty()) {
            throw new IllegalStateException("Missing required environment variable: " + name);
        }
        return value;
    }

    private int parseIntEnv(String name, int defaultValue) {
        try {
            String value = System.getenv(name);
            return value == null ? defaultValue : Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private long parseLongEnv(String name, long defaultValue) {
        try {
            String value = System.getenv(name);
            return value == null ? defaultValue : Long.parseLong(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private static String escapeJson(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    private void shutdown() {
        running = false;
        if (dataSource != null && !dataSource.isClosed()) {
            dataSource.close();
        }
    }
}
