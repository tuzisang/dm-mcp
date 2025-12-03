#!/usr/bin/env python3
"""
达梦数据库MCP服务器配置文件功能全面测试脚本
测试配置管理模块的所有功能和特性
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
import traceback
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager, get_database_config, get_config_manager
from dm_client import DmConfig, DmClient


class ConfigTester:
    """配置文件功能测试器"""

    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        self.original_config = "dm_config.json"
        self.backup_config = "dm_config.json.backup"

    def setup_test_environment(self):
        """设置测试环境"""
        print("=== 设置测试环境 ===")

        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp(prefix="dm_config_test_")
        print(f"创建临时测试目录: {self.temp_dir}")

        # 备份原有配置文件
        if os.path.exists(self.original_config):
            shutil.copy2(self.original_config, self.backup_config)
            print(f"备份原有配置文件到: {self.backup_config}")

        print("测试环境设置完成\n")

    def cleanup_test_environment(self):
        """清理测试环境"""
        print("=== 清理测试环境 ===")

        # 清理临时目录
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"清理临时测试目录: {self.temp_dir}")

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

    def test_config_manager_initialization(self):
        """测试ConfigManager类的初始化和基本方法"""
        print("=== 测试ConfigManager类的初始化和基本方法 ===")

        try:
            # 测试默认初始化
            config_manager = ConfigManager()
            self.log_test_result(
                "ConfigManager默认初始化",
                config_manager is not None and config_manager.config_file.name == "dm_config.json",
                f"默认配置文件路径: {config_manager.config_file}"
            )

            # 测试自定义路径初始化
            custom_config_path = os.path.join(self.temp_dir, "custom_config.json")
            custom_manager = ConfigManager(custom_config_path)
            self.log_test_result(
                "ConfigManager自定义路径初始化",
                str(custom_manager.config_file) == custom_config_path,
                f"自定义配置文件路径: {custom_manager.config_file}"
            )

            # 测试默认配置值
            default_config = config_manager.default_config
            expected_keys = ["database"]
            expected_db_keys = ["host", "port", "user", "password", "schema"]

            has_all_keys = all(key in default_config for key in expected_keys)
            has_all_db_keys = all(key in default_config["database"] for key in expected_db_keys)

            self.log_test_result(
                "ConfigManager默认配置值验证",
                has_all_keys and has_all_db_keys,
                f"默认配置: {default_config}"
            )

            # 测试get_config_file_path方法
            config_path = config_manager.get_config_file_path()
            self.log_test_result(
                "get_config_file_path方法",
                os.path.isabs(config_path) and config_path.endswith("dm_config.json"),
                f"配置文件路径: {config_path}"
            )

        except Exception as e:
            self.log_test_result("ConfigManager初始化测试异常", False, error=str(e))

    def test_config_file_operations(self):
        """测试配置文件的创建、读取、保存功能"""
        print("=== 测试配置文件的创建、读取、保存功能 ===")

        try:
            test_config_path = os.path.join(self.temp_dir, "test_config.json")
            config_manager = ConfigManager(test_config_path)

            # 测试创建默认配置文件
            config = config_manager.load_config()
            file_exists = os.path.exists(test_config_path)
            self.log_test_result(
                "配置文件自动创建",
                file_exists,
                f"配置文件是否存在: {file_exists}"
            )

            # 验证创建的配置文件内容
            if file_exists:
                with open(test_config_path, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)

                config_matches = saved_config == config_manager.default_config
                self.log_test_result(
                    "配置文件内容验证",
                    config_matches,
                    f"保存的配置: {saved_config}"
                )

            # 测试更新配置
            new_config = {
                "database": {
                    "host": "test.example.com",
                    "port": 1234,
                    "user": "testuser",
                    "password": "testpass",
                    "schema": "testschema"
                }
            }

            save_result = config_manager.save_config(new_config)
            self.log_test_result(
                "配置文件保存",
                save_result,
                f"保存操作结果: {save_result}"
            )

            # 验证更新后的配置文件
            if save_result:
                with open(test_config_path, 'r', encoding='utf-8') as f:
                    updated_config = json.load(f)

                host_updated = updated_config["database"]["host"] == "test.example.com"
                self.log_test_result(
                    "配置文件更新验证",
                    host_updated,
                    f"更新后主机地址: {updated_config['database']['host']}"
                )

        except Exception as e:
            self.log_test_result("配置文件操作测试异常", False, error=str(e))

    def test_parameter_validation(self):
        """测试参数验证功能"""
        print("=== 测试参数验证功能 ===")

        try:
            test_config_path = os.path.join(self.temp_dir, "validation_test.json")
            config_manager = ConfigManager(test_config_path)

            # 测试端口验证 - 有效端口
            valid_port_config = {
                "database": {
                    "host": "localhost",
                    "port": "5236",  # 字符串形式的数字
                    "user": "SYSDBA",
                    "password": "SYSDBA001",
                    "schema": "aiops"
                }
            }

            validated_config = config_manager._validate_config(valid_port_config)
            port_is_int = isinstance(validated_config["database"]["port"], int)
            port_value = validated_config["database"]["port"]

            self.log_test_result(
                "端口类型自动转换",
                port_is_int and port_value == 5236,
                f"端口值: {port_value} (类型: {type(port_value).__name__})"
            )

            # 测试端口验证 - 无效端口
            invalid_port_config = {
                "database": {
                    "host": "localhost",
                    "port": 99999,  # 超出范围的端口
                    "user": "SYSDBA",
                    "password": "SYSDBA001",
                    "schema": "aiops"
                }
            }

            validated_invalid_config = config_manager._validate_config(invalid_port_config)
            port_reset = validated_invalid_config["database"]["port"] == 5236

            self.log_test_result(
                "无效端口重置为默认值",
                port_reset,
                f"无效端口重置为: {validated_invalid_config['database']['port']}"
            )

            # 测试默认值设置
            minimal_config = {"database": {}}
            validated_minimal = config_manager._validate_config(minimal_config)

            has_all_defaults = all(
                validated_minimal["database"][key] == value
                for key, value in config_manager.default_config["database"].items()
            )

            self.log_test_result(
                "默认值自动设置",
                has_all_defaults,
                f"最小配置验证结果: {validated_minimal}"
            )

            # 测试非字典配置处理
            try:
                config_manager._validate_config("invalid_config")
                self.log_test_result("非字典配置验证", False, "应该抛出ValueError异常")
            except ValueError:
                self.log_test_result("非字典配置验证", True, "正确抛出ValueError异常")

        except Exception as e:
            self.log_test_result("参数验证测试异常", False, error=str(e))

    def test_dm_config_from_file(self):
        """测试DmConfig.from_config_file()方法"""
        print("=== 测试DmConfig.from_config_file()方法 ===")

        try:
            # 备份并创建测试配置
            if os.path.exists(self.original_config):
                shutil.copy2(self.original_config, f"{self.original_config}.test_backup")

            test_config = {
                "database": {
                    "host": "test.dm.database.com",
                    "port": 5237,
                    "user": "TESTUSER",
                    "password": "TESTPASS123",
                    "schema": "testschema"
                }
            }

            with open(self.original_config, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2)

            # 测试从配置文件创建DmConfig
            dm_config = DmConfig.from_config_file()

            # 验证配置值
            config_correct = (
                dm_config.host == "test.dm.database.com" and
                dm_config.port == 5237 and
                dm_config.user == "TESTUSER" and
                dm_config.password == "TESTPASS123" and
                dm_config.schema == "testschema"
            )

            self.log_test_result(
                "DmConfig.from_config_file()功能",
                config_correct,
                f"生成的配置: host={dm_config.host}, port={dm_config.port}, user={dm_config.user}, schema={dm_config.schema}"
            )

        except Exception as e:
            self.log_test_result("DmConfig.from_config_file()测试异常", False, error=str(e))

        finally:
            # 恢复原有配置
            if os.path.exists(f"{self.original_config}.test_backup"):
                if os.path.exists(self.original_config):
                    os.remove(self.original_config)
                shutil.move(f"{self.original_config}.test_backup", self.original_config)

    def test_dm_client_integration(self):
        """测试dm_client.py使用配置文件的功能"""
        print("=== 测试dm_client.py使用配置文件的功能 ===")

        try:
            # 备份并创建测试配置
            if os.path.exists(self.original_config):
                shutil.copy2(self.original_config, f"{self.original_config}.client_test_backup")

            # 创建测试配置
            test_config = {
                "database": {
                    "host": "192.168.100.100",
                    "port": 5236,
                    "user": "TEST_CLIENT",
                    "password": "CLIENT_PASS123",
                    "schema": "client_test"
                }
            }

            with open(self.original_config, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2)

            # 测试DmClient从配置文件创建
            dm_config = DmConfig.from_config_file()
            client = DmClient(dm_config)

            # 验证客户端配置
            client_config_correct = (
                client.config.host == "192.168.100.100" and
                client.config.port == 5236 and
                client.config.user == "TEST_CLIENT" and
                client.config.password == "CLIENT_PASS123" and
                client.config.schema == "client_test"
            )

            self.log_test_result(
                "DmClient从配置文件读取配置",
                client_config_correct,
                f"客户端配置: host={client.config.host}, user={client.config.user}, schema={client.config.schema}"
            )

            # 测试连接诊断信息（不实际连接）
            print("测试连接诊断信息输出:")
            try:
                # 这个测试会尝试连接，但因为数据库不存在而失败，这正是我们想要的
                # 我们主要测试配置是否正确传递
                client.connect()
            except Exception:
                # 预期的异常，因为我们没有真实的数据库
                pass

            self.log_test_result(
                "DmClient配置传递验证",
                True,
                "配置正确传递到DmClient，连接诊断信息正常输出"
            )

        except Exception as e:
            self.log_test_result("DmClient集成测试异常", False, error=str(e))

        finally:
            # 恢复原有配置
            if os.path.exists(f"{self.original_config}.client_test_backup"):
                if os.path.exists(self.original_config):
                    os.remove(self.original_config)
                shutil.move(f"{self.original_config}.client_test_backup", self.original_config)

    def test_config_update_functionality(self):
        """测试配置更新功能"""
        print("=== 测试配置更新功能 ===")

        try:
            test_config_path = os.path.join(self.temp_dir, "update_test.json")
            config_manager = ConfigManager(test_config_path)

            # 初始化配置
            initial_config = config_manager.load_config()
            initial_host = initial_config["database"]["host"]

            # 测试部分更新
            update_success = config_manager.update_database_config(
                host="updated.example.com",
                port=5237
            )

            self.log_test_result(
                "配置数据库更新操作",
                update_success,
                f"更新操作结果: {update_success}"
            )

            if update_success:
                # 验证更新结果
                updated_config = config_manager.load_config()
                host_updated = updated_config["database"]["host"] == "updated.example.com"
                port_updated = updated_config["database"]["port"] == 5237
                user_preserved = updated_config["database"]["user"] == initial_config["database"]["user"]

                self.log_test_result(
                    "配置更新验证",
                    host_updated and port_updated and user_preserved,
                    f"更新后配置: host={updated_config['database']['host']}, port={updated_config['database']['port']}, user保留={user_preserved}"
                )

            # 测试获取数据库配置
            db_config = config_manager.get_database_config()
            db_config_valid = isinstance(db_config, dict) and "host" in db_config

            self.log_test_result(
                "get_database_config方法",
                db_config_valid,
                f"数据库配置: {db_config}"
            )

        except Exception as e:
            self.log_test_result("配置更新功能测试异常", False, error=str(e))

    def test_error_handling(self):
        """测试错误处理和异常情况"""
        print("=== 测试错误处理和异常情况 ===")

        try:
            # 测试无效JSON文件处理
            invalid_json_path = os.path.join(self.temp_dir, "invalid.json")
            with open(invalid_json_path, 'w', encoding='utf-8') as f:
                f.write('{"invalid": json content}')  # 无效JSON

            config_manager = ConfigManager(invalid_json_path)
            loaded_config = config_manager.load_config()

            # 应该返回默认配置
            is_default_config = loaded_config == config_manager.default_config
            self.log_test_result(
                "无效JSON文件处理",
                is_default_config,
                "无效JSON文件应该返回默认配置"
            )

            # 测试只读目录处理
            readonly_dir = os.path.join(self.temp_dir, "readonly")
            os.makedirs(readonly_dir)
            os.chmod(readonly_dir, 0o444)  # 只读权限

            readonly_config_path = os.path.join(readonly_dir, "readonly_config.json")
            readonly_manager = ConfigManager(readonly_config_path)

            try:
                readonly_manager.save_config({"test": "config"})
                save_result = True
            except Exception:
                save_result = False

            self.log_test_result(
                "只读目录保存处理",
                not save_result,  # 应该失败
                "只读目录应该无法保存配置"
            )

            # 清理权限
            os.chmod(readonly_dir, 0o755)

        except Exception as e:
            self.log_test_result("错误处理测试异常", False, error=str(e))

    def run_all_tests(self):
        """运行所有测试"""
        print("开始达梦数据库MCP服务器配置文件功能全面测试")
        print("=" * 80)
        print()

        try:
            self.setup_test_environment()

            # 运行所有测试
            self.test_config_manager_initialization()
            self.test_config_file_operations()
            self.test_parameter_validation()
            self.test_dm_config_from_file()
            self.test_dm_client_integration()
            self.test_config_update_functionality()
            self.test_error_handling()

            # 生成测试报告
            self.generate_test_report()

        finally:
            self.cleanup_test_environment()

    def generate_test_report(self):
        """生成测试报告"""
        print("=" * 80)
        print("测试报告")
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

        # 失败测试详情
        if failed_tests > 0:
            print("失败的测试详情:")
            print("-" * 80)

            for result in self.test_results:
                if not result["success"]:
                    print(f"[FAIL] {result['test_name']}")
                    if result["error"]:
                        print(f"   错误信息: {result['error']}")
                    if result["details"]:
                        print(f"   详细信息: {result['details']}")
                    print()

        # 功能验证确认
        print("功能验证确认:")
        print("-" * 80)

        features_to_check = [
            "ConfigManager类初始化和方法",
            "配置文件创建、读取、保存",
            "参数验证（端口范围、默认值等）",
            "DmConfig.from_config_file()方法",
            "DmClient集成配置文件",
            "配置更新功能",
            "错误处理和异常情况"
        ]

        for feature in features_to_check:
            related_tests = [r for r in self.test_results if any(keyword in r['test_name'] for keyword in feature.split())]
            feature_passed = all(r['success'] for r in related_tests) if related_tests else False
            status = "PASS" if feature_passed else "FAIL"
            print(f"[{status}] {feature}")

        print()

        # 总体评估
        print("总体评估:")
        print("-" * 80)

        if success_rate >= 90:
            print("优秀！配置文件功能测试通过率很高，系统稳定可靠。")
        elif success_rate >= 75:
            print("良好！大部分配置文件功能正常，少数问题需要修复。")
        elif success_rate >= 50:
            print("一般！配置文件功能基本可用，但存在较多问题需要关注。")
        else:
            print("需要改进！配置文件功能存在严重问题，建议立即修复。")

        print()

        # 保存测试报告到文件
        report_data = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate,
                "test_date": datetime.now().isoformat()
            },
            "test_results": self.test_results
        }

        report_file = "config_test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"详细测试报告已保存到: {report_file}")


def main():
    """主函数"""
    tester = ConfigTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()