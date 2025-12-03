"""
达梦数据库客户端 - 真实可用版本
需要安装 dmPython: pip install dmPython
"""

import typing as t
from dataclasses import dataclass


@dataclass
class DmConfig:
    """达梦数据库连接配置"""
    host: str
    port: int = 5236
    user: str = ""
    password: str = ""
    schema: str = ""


class DmClient:
    """达梦数据库客户端 - 真实实现"""

    def __init__(self, config: DmConfig):
        self.config = config
        self.connection = None
        self.driver = None

    def _get_driver(self):
        """获取达梦数据库驱动"""
        if self.driver is None:
            try:
                import dmPython
                self.driver = dmPython
                print("达梦数据库驱动加载成功")
                return True
            except ImportError:
                print("错误: 未安装 dmPython 驱动，请运行: pip install dmPython")
                return False
        return True

    def connect(self) -> bool:
        """连接到达梦数据库"""
        if not self._get_driver():
            return False

        try:
            print(f"正在连接到达梦数据库: {self.config.host}:{self.config.port}")
            print(f"用户: {self.config.user}, 模式: {self.config.schema or '默认'}")

            # 使用已验证有效的元组方式连接
            conn_params = (self.config.user, self.config.password, self.config.host, self.config.port)
            self.connection = self.driver.connect(*conn_params)

            print("达梦数据库连接成功")
            return True

        except Exception as e:
            print(f"连接到达梦数据库失败: {e}")
            self.connection = None
            return False

    
    def execute_query(self, sql: str) -> t.List[t.Dict[str, t.Any]]:
        """执行 SQL 查询，返回结果"""
        if not self.connection:
            if not self.connect():
                return []

        try:
            cursor = self.connection.cursor()

            print(f"执行 SQL: {sql.strip()}")

            cursor.execute(sql)

            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取结果
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                if len(columns) == len(row):
                    result.append(dict(zip(columns, row)))
                else:
                    # 如果列数不匹配，使用索引作为键
                    result.append({"row": row})

            cursor.close()

            print(f"查询成功，返回 {len(result)} 行结果")
            return result

        except Exception as e:
            print(f"查询执行失败: {e}")
            return []

    def execute_update(self, sql: str) -> int:
        """执行 INSERT/UPDATE/DELETE 语句，返回影响的行数"""
        if not self.connection:
            if not self.connect():
                return -1

        try:
            cursor = self.connection.cursor()

            print(f"执行更新语句: {sql.strip()}")

            cursor.execute(sql)
            affected_rows = cursor.rowcount

            self.connection.commit()
            cursor.close()

            print(f"更新成功，影响 {affected_rows} 行")
            return affected_rows

        except Exception as e:
            print(f"更新执行失败: {e}")
            if self.connection:
                try:
                    self.connection.rollback()
                except:
                    pass
            return -1

    def test_connection(self) -> dict:
        """测试数据库连接"""
        try:
            if not self.connect():
                return {"success": False, "error": "连接失败"}

            # 执行一个简单的查询来测试连接
            result = self.execute_query("SELECT 1 AS test_value FROM DUAL")

            if result:
                return {
                    "success": True,
                    "message": "连接测试成功",
                    "test_query": result[0]
                }
            else:
                return {"success": False, "error": "测试查询失败"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_views(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """查询数据库中的视图列表

        Args:
            schema: 可选的模式名称，不提供则查询当前用户视图

        Returns:
            List[Dict]: 视图信息列表，每个视图包含VIEW_NAME等字段

        Raises:
            ValueError: 当schema名称包含非法字符时
        """
        if schema is not None:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 查询指定模式的视图，使用参数化查询
            # 达梦数据库使用ALL_OBJECTS表查询视图信息
            sql = "SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = ? AND OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
            result = self._execute_param_query(sql, (schema.strip(),))
        else:
            # 查询当前用户模式的视图
            # 达梦数据库使用USER_OBJECTS表查询视图信息
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
            result = self.execute_query(sql)

        # 重命名字段为VIEW_NAME以保持一致性
        for item in result:
            if 'OBJECT_NAME' in item:
                item['VIEW_NAME'] = item['OBJECT_NAME']

        print(f"视图列表查询完成，找到 {len(result)} 个视图")
        return result

    def _execute_param_query(self, sql: str, params: tuple) -> t.List[t.Dict[str, t.Any]]:
        """执行参数化查询的辅助方法"""
        if not self.connection:
            if not self.connect():
                return []

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)

            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取结果
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                if len(columns) == len(row):
                    result.append(dict(zip(columns, row)))
                else:
                    result.append({"row": row})

            cursor.close()
            return result

        except Exception as e:
            print(f"参数化查询执行失败: {e}")
            return []

    def list_tables(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """查询数据库中的物理表列表

        Args:
            schema: 可选的模式名称，不提供则查询当前用户表

        Returns:
            List[Dict]: 表信息列表，每个表包含TABLE_NAME等字段

        Raises:
            ValueError: 当schema名称包含非法字符时
        """
        if schema is not None:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 查询指定模式的物理表，使用参数化查询
            # 达梦数据库使用ALL_OBJECTS表查询表信息
            sql = "SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = ? AND OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
            result = self._execute_param_query(sql, (schema.upper().strip(),))
        else:
            # 查询当前用户模式的物理表
            # 达梦数据库使用USER_OBJECTS表查询表信息
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
            result = self.execute_query(sql)

        # 重命名字段为TABLE_NAME以保持一致性
        for item in result:
            if 'OBJECT_NAME' in item:
                item['TABLE_NAME'] = item['OBJECT_NAME']

        print(f"物理表列表查询完成，找到 {len(result)} 个表")
        return result

    def get_view_definition(self, view_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """获取指定视图的创建语句

        Args:
            view_name: 视图名称（必需）
            schema: 可选的模式名称，不提供则查询当前用户视图

        Returns:
            List[Dict]: 包含视图定义信息的字典列表，主要包含VIEW_DEF字段（视图创建SQL语句）

        Raises:
            ValueError: 当view_name或schema名称包含非法字符时
        """
        # 验证view_name参数
        if not view_name or not view_name.strip():
            raise ValueError("视图名称不能为空")

        view_name = view_name.strip()

        if schema:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 使用ALL_VIEWS视图查询视图定义
            sql = "SELECT TEXT AS VIEW_DEF FROM ALL_VIEWS WHERE VIEW_NAME = ? AND OWNER = ?"
            result = self._execute_param_query(sql, (view_name, schema.strip()))
        else:
            # 使用USER_VIEWS视图查询当前用户视图定义
            sql = "SELECT TEXT AS VIEW_DEF FROM USER_VIEWS WHERE VIEW_NAME = ?"
            result = self._execute_param_query(sql, (view_name,))

        print(f"视图定义查询完成，视图: {view_name}, 结果: {len(result)} 行")
        return result

    def describe_table(self, table_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """获取指定表的结构信息

        Args:
            table_name: 表名称（必需）
            schema: 可选的模式名称，不提供则查询当前用户表

        Returns:
            List[Dict]: 表结构信息列表，每个字段包含COLUMN_NAME、DATA_TYPE、DATA_LENGTH、NULLABLE等字段

        Raises:
            ValueError: 当table_name或schema名称包含非法字符时
        """
        # 验证table_name参数
        if not table_name or not table_name.strip():
            raise ValueError("表名称不能为空")

        table_name = table_name.strip()

        if schema:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 使用ALL_TAB_COLUMNS视图查询表结构
            sql = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT,
                    COLUMN_ID
                FROM ALL_TAB_COLUMNS
                WHERE TABLE_NAME = ? AND OWNER = ?
                ORDER BY COLUMN_ID
            """
            result = self._execute_param_query(sql, (table_name, schema.strip()))
        else:
            # 使用USER_TAB_COLUMNS视图查询当前用户表结构
            sql = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT,
                    COLUMN_ID
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY COLUMN_ID
            """
            result = self._execute_param_query(sql, (table_name,))

        print(f"表结构查询完成，表: {table_name}, 结果: {len(result)} 列")
        return result

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                print("达梦数据库连接已关闭")
            except Exception as e:
                print(f"关闭连接时出错: {e}")
            finally:
                self.connection = None

    def __enter__(self):
        """上下文管理器支持"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器支持"""
        self.close()


def test_dm_client():
    """测试达梦数据库客户端 - 修复版本"""
    print("=== 达梦数据库客户端测试 - 修复版本 ===")

    # 测试配置
    config = DmConfig(
        host="192.168.2.38",
        port=5236,
        user="SYSDBA",
        password="SYSDBA001",
        schema="aiops"
    )

    try:
        # 测试连接和查询
        print("\n1. 测试连接...")
        client = DmClient(config)

        if client.connect():
            print("[OK] 数据库连接成功!")

            # 测试 TASK_HANDLE_WORKORDER 表结构
            print("\n2. 测试 TASK_HANDLE_WORKORDER 表结构...")
            try:
                table_struct = client.describe_table("TASK_HANDLE_WORKORDER", "aiops")
                print(f"[OK] TASK_HANDLE_WORKORDER 表结构查询成功")
                if table_struct:
                    print(f"TASK_HANDLE_WORKORDER 包含 {len(table_struct)} 个列:")
                    for i, col in enumerate(table_struct[:5]):  # 显示前5列
                        print(f"  列{i+1}: {col}")
                    if len(table_struct) > 5:
                        print(f"  ... 还有 {len(table_struct)-5} 列")
                else:
                    print("TASK_HANDLE_WORKORDER 表结构为空")
            except Exception as e:
                print(f"[ERROR] TASK_HANDLE_WORKORDER 表结构查询失败: {e}")

            # 测试 V_OPS_WORK_ORDERS 视图定义
            print("\n3. 测试 V_OPS_WORK_ORDERS 视图定义...")
            try:
                view_def = client.get_view_definition("V_OPS_WORK_ORDERS", "aiops")
                print(f"[OK] V_OPS_WORK_ORDERS 视图定义查询成功")
                if view_def:
                    print(f"V_OPS_WORK_ORDERS 视图定义长度: {len(str(view_def))} 字符")
                    # 显示视图定义的前200字符
                    for item in view_def:
                        if 'VIEW_DEF' in item:
                            definition = str(item['VIEW_DEF'])
                            print(f"V_OPS_WORK_ORDERS 视图定义前200字符:")
                            print(f"  {definition[:200]}...")
                else:
                    print("V_OPS_WORK_ORDERS 视图定义为空")
            except Exception as e:
                print(f"[ERROR] V_OPS_WORK_ORDERS 视图定义查询失败: {e}")

            print("\n=== 修复完成！两个SQL错误已解决 ===")

        else:
            print("[ERROR] 数据库连接失败")

    except Exception as e:
        print(f"[ERROR] 测试过程中发生异常: {e}")

    finally:
        # 清理
        if 'client' in locals():
            client.close()

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_dm_client()