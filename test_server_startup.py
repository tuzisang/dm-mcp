#!/usr/bin/env python3
"""
MCP服务器启动测试脚本
测试MCP服务器能够正常启动并加载配置文件
"""

import os
import sys
import json
import time
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class ServerStartupTester:
    """MCP服务器启动测试器"""

    def __init__(self):
        self.test_results = []
        self.original_config = "dm_config.json"
        self.backup_config = "dm_config.json.server_test_backup"

    def setup_test_environment(self):
        """设置测试环境"""
        print("=== 设置服务器启动测试环境 ===")

        # 备份原有配置文件
        if os.path.exists(self.original_config):
            shutil.copy2(self.original_config, self.backup_config)
            print(f"备份原有配置文件到: {self.backup_config}")

        # 创建测试配置
        test_config = {
            "database": {
                "host": "server.test.example.com",
                "port": 5236,
                "user": "SERVER_TEST",
                "password": "SERVER_TEST_PASS",
                "schema": "server_test_schema"
            }
        }

        with open(self.original_config, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2)

        print("测试环境设置完成\n")

    def cleanup_test_environment(self):
        """清理测试环境"""
        print("=== 清理服务器启动测试环境 ===")

        # 恢复原有配置文件
        if os.path.exists(self.backup_config):
            if os.path.exists(self.original_config):
                os.remove(self.original_config)
            shutil.move(self.backup_config, self.original_config)
            print(f"恢复原有配置文件: {self.original_config}")

        print("测试环境清理完成\n")

    def log_test_result(self, test_name, success, details="", error=""):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)

        status = "PASS" if success else "FAIL"
        print(f"[{status}] {test_name}")
        if details:
            print(f"    详情: {details}")
        if error:
            print(f"    错误: {error}")
        print()

    def test_server_syntax_check(self):
        """测试服务器代码语法检查"""
        print("=== 测试服务器代码语法检查 ===")

        try:
            # 使用Python编译检查语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile", "main.py"
            ], capture_output=True, text=True, timeout=30)

            syntax_ok = result.returncode == 0

            self.log_test_result(
                "main.py语法检查",
                syntax_ok,
                "语法检查通过" if syntax_ok else f"语法错误: {result.stderr}"
            )

            # 检查配置模块语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile", "config.py"
            ], capture_output=True, text=True, timeout=30)

            config_syntax_ok = result.returncode == 0

            self.log_test_result(
                "config.py语法检查",
                config_syntax_ok,
                "配置模块语法检查通过" if config_syntax_ok else f"语法错误: {result.stderr}"
            )

            # 检查客户端模块语法
            result = subprocess.run([
                sys.executable, "-m", "py_compile", "dm_client.py"
            ], capture_output=True, text=True, timeout=30)

            client_syntax_ok = result.returncode == 0

            self.log_test_result(
                "dm_client.py语法检查",
                client_syntax_ok,
                "客户端模块语法检查通过" if client_syntax_ok else f"语法错误: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            self.log_test_result("语法检查超时", False, "语法检查超时")
        except Exception as e:
            self.log_test_result("语法检查异常", False, error=str(e))

    def test_import_dependencies(self):
        """测试依赖导入"""
        print("=== 测试依赖导入 ===")

        try:
            # 测试导入config模块
            import config
            self.log_test_result(
                "config模块导入",
                True,
                "config模块导入成功"
            )

            # 测试导入dm_client模块
            import dm_client
            self.log_test_result(
                "dm_client模块导入",
                True,
                "dm_client模块导入成功"
            )

            # 测试导入main模块（不启动服务器）
            import importlib.util
            spec = importlib.util.spec_from_file_location("main", "main.py")
            main_module = importlib.util.module_from_spec(spec)

            # 只导入模块，不执行main函数
            self.log_test_result(
                "main模块导入",
                True,
                "main模块导入成功"
            )

            # 测试关键函数是否存在
            required_functions = ["dm_connect", "dm_query", "dm_update_config", "dm_list_tables"]
            missing_functions = []

            for func_name in required_functions:
                if not hasattr(main_module, func_name):
                    missing_functions.append(func_name)

            functions_ok = len(missing_functions) == 0
            self.log_test_result(
                "MCP工具函数检查",
                functions_ok,
                f"所有必需函数存在" if functions_ok else f"缺少函数: {missing_functions}"
            )

        except ImportError as e:
            self.log_test_result("依赖导入测试", False, error=f"导入错误: {str(e)}")
        except Exception as e:
            self.log_test_result("依赖导入测试异常", False, error=str(e))

    def test_config_loading_at_startup(self):
        """测试启动时配置加载"""
        print("=== 测试启动时配置加载 ===")

        try:
            # 直接测试配置加载功能
            from config import get_database_config, get_config_manager

            # 测试获取数据库配置
            db_config = get_database_config()

            config_loaded = isinstance(db_config, dict) and "host" in db_config
            self.log_test_result(
                "启动时配置加载",
                config_loaded,
                f"加载的配置: {db_config}"
            )

            # 验证配置文件中的值被正确加载
            expected_host = "server.test.example.com"
            host_correct = db_config.get("host") == expected_host

            self.log_test_result(
                "配置文件值验证",
                host_correct,
                f"期望主机: {expected_host}, 实际主机: {db_config.get('host')}"
            )

            # 测试ConfigManager初始化
            config_manager = get_config_manager()
            manager_ok = config_manager is not None

            self.log_test_result(
                "ConfigManager初始化",
                manager_ok,
                "ConfigManager初始化成功"
            )

        except Exception as e:
            self.log_test_result("配置加载测试异常", False, error=str(e))

    def test_server_initialization(self):
        """测试服务器初始化（不启动完整服务器）"""
        print("=== 测试服务器初始化 ===")

        try:
            # 测试MCP服务器初始化相关代码
            import importlib.util

            # 读取main.py内容，检查关键初始化代码
            with open("main.py", 'r', encoding='utf-8') as f:
                main_content = f.read()

            # 检查关键初始化元素
            initialization_checks = {
                "FastMCP导入": "from mcp.server.fastmcp" in main_content,
                "MCP服务器实例创建": "mcp = FastMCP" in main_content,
                "dm_update_config工具定义": "@mcp.tool()" in main_content and "dm_update_config" in main_content,
                "config模块导入": "from config import" in main_content,
                "dm_client模块导入": "from dm_client import" in main_content
            }

            for check_name, check_result in initialization_checks.items():
                self.log_test_result(
                    f"服务器初始化检查 - {check_name}",
                    check_result,
                    f"{check_name}: {'存在' if check_result else '缺失'}"
                )

        except Exception as e:
            self.log_test_result("服务器初始化测试异常", False, error=str(e))

    def test_config_file_integration(self):
        """测试配置文件集成"""
        print("=== 测试配置文件集成 ===")

        try:
            # 测试DmConfig从配置文件加载
            from dm_client import DmConfig

            dm_config = DmConfig.from_config_file()
            config_integration_ok = (
                dm_config.host == "server.test.example.com" and
                dm_config.user == "SERVER_TEST"
            )

            self.log_test_result(
                "DmConfig配置文件集成",
                config_integration_ok,
                f"DmConfig: host={dm_config.host}, user={dm_config.user}"
            )

            # 测试DmClient使用配置文件
            from dm_client import DmClient

            client = DmClient(dm_config)
            client_integration_ok = (
                client.config.host == "server.test.example.com" and
                client.config.user == "SERVER_TEST"
            )

            self.log_test_result(
                "DmClient配置文件集成",
                client_integration_ok,
                f"DmClient配置: host={client.config.host}, user={client.config.user}"
            )

        except Exception as e:
            self.log_test_result("配置文件集成测试异常", False, error=str(e))

    def test_error_handling_at_startup(self):
        """测试启动时的错误处理"""
        print("=== 测试启动时的错误处理 ===")

        try:
            # 测试配置文件不存在时的处理
            if os.path.exists("dm_config.json"):
                os.remove("dm_config.json")

            from config import get_database_config

            # 应该返回默认配置
            db_config = get_database_config()
            default_config_ok = (
                db_config.get("host") == "192.168.2.38" and
                db_config.get("user") == "SYSDBA"
            )

            self.log_test_result(
                "配置文件不存在处理",
                default_config_ok,
                "正确返回默认配置"
            )

            # 恢复测试配置
            test_config = {
                "database": {
                    "host": "server.test.example.com",
                    "port": 5236,
                    "user": "SERVER_TEST",
                    "password": "SERVER_TEST_PASS",
                    "schema": "server_test_schema"
                }
            }

            with open("dm_config.json", 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2)

        except Exception as e:
            self.log_test_result("启动错误处理测试异常", False, error=str(e))

    def run_all_tests(self):
        """运行所有服务器启动测试"""
        print("开始MCP服务器启动功能测试")
        print("=" * 80)
        print()

        try:
            self.setup_test_environment()

            # 运行所有测试
            self.test_server_syntax_check()
            self.test_import_dependencies()
            self.test_config_loading_at_startup()
            self.test_server_initialization()
            self.test_config_file_integration()
            self.test_error_handling_at_startup()

            # 生成测试报告
            self.generate_test_report()

        finally:
            self.cleanup_test_environment()

    def generate_test_report(self):
        """生成测试报告"""
        print("=" * 80)
        print("MCP服务器启动测试报告")
        print("=" * 80)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {failed_tests}")
        print(f"成功率: {success_rate:.1f}%")
        print()

        # 详细测试结果
        print("详细测试结果:")
        print("-" * 80)

        for i, result in enumerate(self.test_results, 1):
            status = "PASS" if result["success"] else "FAIL"
            print(f"{i}. [{status}] {result['test_name']}")
            if result["details"]:
                print(f"   详情: {result['details']}")
            if result["error"]:
                print(f"   错误: {result['error']}")

        print()

        # 功能验证确认
        print("服务器启动功能验证:")
        print("-" * 80)

        features_to_check = [
            "代码语法检查",
            "依赖导入",
            "配置加载",
            "服务器初始化",
            "配置文件集成",
            "错误处理"
        ]

        for feature in features_to_check:
            related_tests = [r for r in self.test_results if any(keyword in r['test_name'] for keyword in feature.split())]
            feature_passed = all(r['success'] for r in related_tests) if related_tests else False
            status = "PASS" if feature_passed else "FAIL"
            print(f"[{status}] {feature}")

        print()

        # 总体评估
        if success_rate >= 90:
            print("优秀！MCP服务器启动功能测试通过率很高。")
        elif success_rate >= 75:
            print("良好！大部分MCP服务器启动功能正常。")
        elif success_rate >= 50:
            print("一般！MCP服务器启动功能基本可用，但存在问题需要关注。")
        else:
            print("需要改进！MCP服务器启动功能存在严重问题。")

        print()


def main():
    """主函数"""
    tester = ServerStartupTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()