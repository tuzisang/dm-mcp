import dm.jdbc.driver.DmDriver;
import java.sql.*;
import java.util.Scanner;

/**
 * Simple JDBC bridge for DM Database
 * Reads SQL commands from stdin and outputs results as JSON
 */
public class DmJdbcBridge {
    public static void main(String[] args) {
        String url = "jdbc:dm://" + System.getenv("DM_HOST") + ":" + System.getenv("DM_PORT");
        String user = System.getenv("DM_USER");
        String password = System.getenv("DM_PASSWORD");

        try {
            Connection conn = DriverManager.getConnection(url, user, password);
            Scanner scanner = new Scanner(System.in);

            while (scanner.hasNextLine()) {
                String sql = scanner.nextLine();
                if ("EXIT".equals(sql)) break;

                Statement stmt = conn.createStatement();
                boolean hasResults = stmt.execute(sql);

                if (hasResults) {
                    ResultSet rs = stmt.getResultSet();
                    ResultSetMetaData meta = rs.getMetaData();
                    int colCount = meta.getColumnCount();

                    // Print header
                    for (int i = 1; i <= colCount; i++) {
                        System.out.print(meta.getColumnName(i));
                        if (i < colCount) System.out.print("\t");
                    }
                    System.out.println();

                    // Print rows
                    while (rs.next()) {
                        for (int i = 1; i <= colCount; i++) {
                            System.out.print(rs.getString(i));
                            if (i < colCount) System.out.print("\t");
                        }
                        System.out.println();
                    }
                    rs.close();
                } else {
                    System.out.println("Affected rows: " + stmt.getUpdateCount());
                }
                stmt.close();
            }

            conn.close();
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}
