#!/usr/bin/env python3
"""
简单的 Java 桥接服务测试
"""

import os
import subprocess
import json
import time

# 配置
config = {
    'host': '192.168.2.38',
    'port': 5236,
    'user': 'SYSDBA',
    'password': 'SYSDBA001',
    'schema': 'aiops'
}

# 检测 Java
java_home = os.path.expanduser("~/.sdkman/candidates/java/current")
java_exe = os.path.join(java_home, 'bin', 'java')

print(f"使用 Java: {java_exe}")

# 构建 classpath
lib_dir = "lib"
classpath = [
    f"{lib_dir}/dm-jdbc-1.8.jar",
    f"{lib_dir}/HikariCP-4.0.3.jar",
    f"{lib_dir}/slf4j-api-2.0.12.jar",
    "db"  # DmJdbcBridge.class 所在目录
]

# 确保在项目根目录运行
if os.path.exists('db/DmJdbcBridge.class'):
    os.chdir('..')

# 设置环境
env = os.environ.copy()
env['JAVA_HOME'] = java_home
env['DM_HOST'] = config['host']
env['DM_PORT'] = str(config['port'])
env['DM_USER'] = config['user']
env['DM_PASSWORD'] = config['password']
env['DM_SCHEMA'] = config['schema']
env['DM_POOL_MIN'] = '2'
env['DM_POOL_MAX'] = '10'
env['DM_POOL_TIMEOUT'] = '30000'

print(f"连接到: {config['host']}:{config['port']}")

# 启动 Java 进程
print("\n启动 Java 守护进程...")
process = subprocess.Popen(
    [java_exe, '-cp', ':'.join(classpath), 'DmJdbcBridge'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True,
    bufsize=1
)

# 等待启动消息
print("等待启动完成...")
start_time = time.time()
ready = False

while time.time() - start_time < 10:
    if process.poll() is not None:
        stderr = process.stderr.read()
        print(f"✗ 进程退出: {stderr}")
        exit(1)

    try:
        line = process.stdout.readline()
        if line:
            print(f"收到: {line.strip()}")
            try:
                data = json.loads(line.strip())
                if data.get('status') == 'ready':
                    ready = True
                    print("✓ 守护进程就绪!")
                    break
            except json.JSONDecodeError:
                pass
    except:
        pass

    time.sleep(0.1)

if not ready:
    print("✗ 启动超时")
    process.terminate()
    exit(1)

# 发送测试查询
print("\n发送测试查询...")
request = {
    "sql": "SELECT COUNT(*) as cnt FROM USER_TABLES"
}

process.stdin.write(json.dumps(request) + '\n')
process.stdin.flush()

# 读取响应
print("等待响应...")
start_time = time.time()

while time.time() - start_time < 30:
    if process.poll() is not None:
        print("✗ 进程意外退出")
        exit(1)

    try:
        line = process.stdout.readline()
        if line:
            print(f"收到: {line.strip()}")
            try:
                response = json.loads(line.strip())
                if 'error' in response:
                    print(f"✗ 查询错误: {response}")
                else:
                    print(f"✓ 查询成功!")
                    if 'rows' in response and response['rows']:
                        count = response['rows'][0][0]
                        print(f"  表数量: {count}")
                break
            except json.JSONDecodeError as e:
                print(f"JSON 解析错误: {e}")
    except:
        pass

    time.sleep(0.1)

# 清理
print("\n关闭守护进程...")
process.terminate()
process.wait(timeout=5)
print("✓ 完成!")
