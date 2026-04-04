import dm.jdbc.driver.DmdbStatement;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

public class ExplainProbe {
    public static void main(String[] args) throws Exception {
        String host = System.getenv("DM_HOST");
        String port = System.getenv("DM_PORT");
        String user = System.getenv("DM_USER");
        String password = System.getenv("DM_PASSWORD");
        String schema = System.getenv("DM_SCHEMA");

        String sql = args.length > 0 ? args[0] : "SELECT COUNT(*) AS C FROM USER_OBJECTS";

        Class.forName("dm.jdbc.driver.DmDriver");
        try (Connection conn = DriverManager.getConnection("jdbc:dm://" + host + ":" + port, user, password)) {
            if (schema != null && !schema.isEmpty()) {
                try (Statement schemaStmt = conn.createStatement()) {
                    schemaStmt.execute("SET SCHEMA \"" + schema + "\"");
                }
            }

            try (Statement stmt = conn.createStatement()) {
                boolean hasResultSet = stmt.execute(sql);
                System.out.println("hasResultSet=" + hasResultSet);

                if (hasResultSet) {
                    try (ResultSet rs = stmt.getResultSet()) {
                        int rowCount = 0;
                        while (rs.next() && rowCount < 5) {
                            rowCount++;
                        }
                        System.out.println("sampleRowsRead=" + rowCount);
                    }
                } else {
                    System.out.println("updateCount=" + stmt.getUpdateCount());
                }

                System.out.println("stmtClass=" + stmt.getClass().getName());
                DmdbStatement dmStmt = stmt.unwrap(DmdbStatement.class);
                System.out.println("executeId=" + dmStmt.getExecuteId());
                System.out.println("sqlType=" + dmStmt.getSqlType());
                System.out.println("retType=" + dmStmt.getRetType());
                System.out.println("explain=" + dmStmt.getExplain());
                System.out.println("printMsg=" + dmStmt.getPrintMsg());
            }
        }
    }
}
