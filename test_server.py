#!/usr/bin/env python3
"""
Test script for DM Database MCP Server
"""

import subprocess
import sys
import time

def test_server_startup():
    """Test that the server starts up properly"""
    print("Testing DM Database MCP Server startup...")
    
    try:
        # Start the server process
        process = subprocess.Popen([
            sys.executable, "main.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if the process is still running
        if process.poll() is None:
            print("✓ Server started successfully")
            # Terminate the process
            process.terminate()
            process.wait()
            return True
        else:
            stdout, stderr = process.communicate()
            print("✗ Server failed to start")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing server: {e}")
        return False

if __name__ == "__main__":
    success = test_server_startup()
    sys.exit(0 if success else 1)