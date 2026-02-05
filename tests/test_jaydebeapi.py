#!/usr/bin/env python3
"""
Simple test case for DM Database using Java subprocess
"""

import json
import os
import subprocess
import sys


def load_config():
    """Load database configuration from dm_config.json"""
    with open('dm_config.json', 'r') as f:
        config = json.load(f)
    return config['database']


def test_connection():
    """Test database connection using Java subprocess"""
    config = load_config()

    print(f"Testing connection to: jdbc:dm://{config['host']}:{config['port']}")
    print(f"User: {config['user']}")
    print(f"Schema: {config['schema']}")

    # Get Java home
    java_home = os.path.expanduser("~/.sdkman/candidates/java/current")
    java_exe = os.path.join(java_home, "bin/java")

    if not os.path.exists(java_exe):
        print(f"ERROR: Java not found at {java_exe}")
        return False

    print(f"Using Java: {java_exe}")

    # Create simple SQL test
    jar_path = os.path.join(os.path.dirname(__file__), "lib/dm-jdbc-1.8.jar")
    if not os.path.exists(jar_path):
        print(f"ERROR: JAR file not found at: {jar_path}")
        return False

    # Create inline Java class for testing
    java_code = f"""
import java.sql.*;

public class DmTest {{
    public static void main(String[] args) {{
        try {{
            Class.forName("dm.jdbc.driver.DmDriver");
            Connection conn = DriverManager.getConnection(
                "jdbc:dm://{config['host']}:{config['port']}",
                "{config['user']}",
                "{config['password']}"
            );

            System.out.println("Connection successful!");

            Statement stmt = conn.createStatement();
            ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM USER_TABLES");

            if (rs.next()) {{
                int count = rs.getInt(1);
                System.out.println("Tables found: " + count);
            }}

            rs.close();
            stmt.close();
            conn.close();

        }} catch (Exception e) {{
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }}
    }}
}}
"""

    # Write Java file
    with open('DmTest.java', 'w') as f:
        f.write(java_code)

    try:
        # Compile Java
        print("\nCompiling Java test...")
        compile_result = subprocess.run(
            ['javac', '-cp', jar_path, 'DmTest.java'],
            capture_output=True,
            text=True
        )

        if compile_result.returncode != 0:
            print(f"Compilation failed: {compile_result.stderr}")
            return False

        print("✓ Compilation successful")

        # Run Java
        print("\nRunning Java test...")
        env = os.environ.copy()
        env['JAVA_HOME'] = java_home

        run_result = subprocess.run(
            ['java', '-cp', f"{jar_path}:.", 'DmTest'],
            capture_output=True,
            text=True,
            env=env
        )

        print(run_result.stdout)
        if run_result.stderr:
            print("STDERR:", run_result.stderr)

        if run_result.returncode == 0:
            print("\n✓ Test completed successfully!")
            return True
        else:
            print(f"\n✗ Test failed with exit code {run_result.returncode}")
            return False

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        for f in ['DmTest.java', 'DmTest.class']:
            if os.path.exists(f):
                os.remove(f)


if __name__ == "__main__":
    print("=" * 50)
    print("DM Database Connection Test (Java Subprocess)")
    print("=" * 50)
    test_connection()
