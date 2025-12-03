#!/usr/bin/env python3
"""
MCP工具测试脚本
专门测试main.py中的dm_update_config工具和其他MCP工具
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入MCP工具函数
from main import dm_update_config, dm_connect, dm_query
from config import ConfigManager


class MCPToolsTester:
    """MCP工具测试器"""

    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.original_config = "dm_config.json"
        self.backup_config = "dm_config.json.mcp_test_backup"

    def setup_test_environment(self):
        """设置测试环境"""
        print("=== 设置MCP工具测试环境 ===")

        # 备份原有配置文件
        if os.path.exists(self.original_config):
            shutil.copy2(self.original_config, self.backup_config)
            print(f"备份原有配置文件到: {self.backup_config}")

        print("测试环境设置完成\n")

    def cleanup_test_environment(self):
        """清理测试环境"""
        print("=== 清理MCP工具测试环境 ===")

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

    def test_dm_update_config_basic(self):
        """测试dm_update_config基本功能"""
        print("=== 测试dm_update_config基本功能 ===")

        try:
            # 测试更新主机地址
            result = dm_update_config(host="test.mcp.example.com")

            success = result.get("success", False)
            message = result.get("message", "")
            updated_fields = result.get("updated_fields", [])

            self.log_test_result(
                "dm_update_config - 更新主机地址",
                success and "host" in updated_fields,
                f"更新字段: {updated_fields}, 消息: {message}"
            )

            if success:
                # 验证配置文件是否真的更新了
                config_manager = ConfigManager()
                db_config = config_manager.get_database_config()
                host_updated = db_config.get("host") == "test.mcp.example.com"

                self.log_test_result(
                    "dm_update_config - 配置文件验证",
                    host_updated,
                    f"配置文件中的主机地址: {db_config.get('host')}"
                )

        except Exception as e:
            self.log_test_result("dm_update_config基本功能测试异常", False, error=str(e))

    def test_dm_update_config_multiple_params(self):
        """测试dm_update_config多参数更新"""
        print("=== 测试dm_update_config多参数更新 ===")

        try:
            # 测试同时更新多个参数
            result = dm_update_config(
                host="multi.test.com",
                port=5237,
                schema="multi_schema"
            )

            success = result.get("success", False)
            updated_fields = result.get("updated_fields", [])
            current_config = result.get("current_config", {})

            expected_fields = {"host", "port", "schema"}
            actual_fields = set(updated_fields)

            self.log_test_result(
                "dm_update_config - 多参数更新",
                success and expected_fields.issubset(actual_fields),
                f"更新的字段: {updated_fields}"
            )

            if success:
                # 验证更新后的配置
                config_correct = (
                    current_config.get("host") == "multi.test.com" and
                    current_config.get("port") == 5237 and
                    current_config.get("schema") == "multi_schema"
                )

                self.log_test_result(
                    "dm_update_config - 多参数配置验证",
                    config_correct,
                    f"当前配置: {current_config}"
                )

        except Exception as e:
            self.log_test_result("dm_update_config多参数更新测试异常", False, error=str(e))

    def test_dm_update_config_no_params(self):
        """测试dm_update_config无参数情况"""
        print("=== 测试dm_update_config无参数情况 ===")

        try:
            # 测试不提供任何参数
            result = dm_update_config()

            success = result.get("success", False)
            message = result.get("message", "")
            updated_fields = result.get("updated_fields", [])

            self.log_test_result(
                "dm_update_config - 无参数调用",
                success and len(updated_fields) == 0 and "未提供任何更新参数" in message,
                f"消息: {message}, 更新字段: {updated_fields}"
            )

        except Exception as e:
            self.log_test_result("dm_update_config无参数测试异常", False, error=str(e))

    def test_dm_update_config_invalid_params(self):
        """测试dm_update_config无效参数处理"""
        print("=== 测试dm_update_config无效参数处理 ===")

        try:
            # 测试无效端口
            result = dm_update_config(port="invalid_port")

            success = result.get("success", False)
            error = result.get("error", "")

            # 应该失败，因为端口无效
            self.log_test_result(
                "dm_update_config - 无效端口处理",
                not success and "端口" in error,
                f"错误信息: {error}"
            )

        except Exception as e:
            self.log_test_result("dm_update_config无效参数测试异常", False, error=str(e))

    def test_dm_connect_with_config(self):
        """测试dm_connect使用配置文件"""
        print("=== 测试dm_connect使用配置文件 ===")

        try:
            # 设置测试配置
            test_config = {
                "database": {
                    "host": "192.168.200.200",
                    "port": 5236,
                    "user": "TEST_CONNECT",
                    "password": "TEST_CONNECT_PASS",
                    "schema": "test_connect_schema"
                }
            }

            config_manager = ConfigManager()
            config_manager.save_config(test_config)

            # 测试连接（预期会失败，因为我们没有真实的数据库）
            result = dm_connect()

            # 验证使用了配置文件中的设置
            # 由于连接会失败，我们主要检查错误信息中是否包含我们设置的配置信息
            connection_info_in_error = (
                "192.168.200.200" in str(result) or
                "TEST_CONNECT" in str(result)
            )

            self.log_test_result(
                "dm_connect - 使用配置文件验证",
                connection_info_in_error,
                f"连接结果包含配置信息: {connection_info_in_error}"
            )

        except Exception as e:
            self.log_test_result("dm_connect配置文件测试异常", False, error=str(e))

    def test_config_persistence(self):
        """测试配置持久性"""
        print("=== 测试配置持久性 ===")

        try:
            # 更新配置
            dm_update_config(
                host="persistence.test.com",
                port=5238,
                user="PERSIST_USER",
                schema="persistence_schema"
            )

            # 验证配置被保存
            config_manager = ConfigManager()
            db_config = config_manager.get_database_config()

            persistence_check = (
                db_config.get("host") == "persistence.test.com" and
                db_config.get("port") == 5238 and
                db_config.get("user") == "PERSIST_USER" and
                db_config.get("schema") == "persistence_schema"
            )

            self.log_test_result(
                "配置持久性验证",
                persistence_check,
                f"持久配置: {db_config}"
            )

            # 验证配置文件确实存在且包含正确内容
            config_file_exists = os.path.exists("dm_config.json")
            if config_file_exists:
                with open("dm_config.json", 'r', encoding='utf-8') as f:
                    file_config = json.load(f)

                file_config_correct = (
                    file_config["database"]["host"] == "persistence.test.com" and
                    file_config["database"]["port"] == 5238
                )

                self.log_test_result(
                    "配置文件内容验证",
                    file_config_correct,
                    f"文件配置: {file_config['database']}"
                )
            else:
                self.log_test_result("配置文件存在性", False, "配置文件不存在")

        except Exception as e:
            self.log_test_result("配置持久性测试异常", False, error=str(e))

    def test_config_manager_integration(self):
        """测试ConfigManager与MCP工具的集成"""
        print("=== 测试ConfigManager与MCP工具的集成 ===")

        try:
            # 直接使用ConfigManager更新配置
            config_manager = ConfigManager()
            direct_update_result = config_manager.update_database_config(
                host="direct.update.com",
                port=5239
            )

            # 使用MCP工具读取配置
            result = dm_update_config()  # 无参数调用，返回当前配置

            current_config = result.get("current_config", {})
            integration_check = (
                current_config.get("host") == "direct.update.com" and
                current_config.get("port") == 5239
            )

            self.log_test_result(
                "ConfigManager与MCP工具集成",
                direct_update_result and integration_check,
                f"集成测试配置: {current_config}"
            )

        except Exception as e:
            self.log_test_result("ConfigManager集成测试异常", False, error=str(e))

    def run_all_tests(self):
        """运行所有MCP工具测试"""
        print("开始MCP工具功能测试")
        print("=" * 80)
        print()

        try:
            self.setup_test_environment()

            # 运行所有测试
            self.test_dm_update_config_basic()
            self.test_dm_update_config_multiple_params()
            self.test_dm_update_config_no_params()
            self.test_dm_update_config_invalid_params()
            self.test_dm_connect_with_config()
            self.test_config_persistence()
            self.test_config_manager_integration()

            # 生成测试报告
            self.generate_test_report()

        finally:
            self.cleanup_test_environment()

    def generate_test_report(self):
        """生成测试报告"""
        print("=" * 80)
        print("MCP工具测试报告")
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
        print("MCP工具功能验证:")
        print("-" * 80)

        features_to_check = [
            "dm_update_config基本功能",
            "dm_update_config多参数更新",
            "dm_update_config参数验证",
            "dm_connect配置文件集成",
            "配置持久性",
            "ConfigManager集成"
        ]

        for feature in features_to_check:
            related_tests = [r for r in self.test_results if any(keyword in r['test_name'] for keyword in feature.split())]
            feature_passed = all(r['success'] for r in related_tests) if related_tests else False
            status = "PASS" if feature_passed else "FAIL"
            print(f"[{status}] {feature}")

        print()

        # 总体评估
        if success_rate >= 90:
            print("优秀！MCP工具功能测试通过率很高。")
        elif success_rate >= 75:
            print("良好！大部分MCP工具功能正常。")
        elif success_rate >= 50:
            print("一般！MCP工具功能基本可用，但存在问题需要关注。")
        else:
            print("需要改进！MCP工具功能存在严重问题。")

        print()


def main():
    """主函数"""
    tester = MCPToolsTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()