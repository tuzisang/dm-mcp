"""服务器装配层的轻量单元测试。"""

from unittest.mock import MagicMock

import db
from main import mcp
from tools import register_tools


def test_main_exposes_mcp_server():
    assert mcp is not None


def test_register_tools_registers_expected_tool_set():
    mock_mcp = MagicMock()
    decorator = MagicMock(side_effect=lambda func: func)
    mock_mcp.tool.return_value = decorator

    register_tools(mock_mcp)

    registered = [call.args[0].__name__ for call in decorator.call_args_list]
    assert registered == [
        "dm_query",
        "dm_explain_plan",
        "dm_connect",
        "dm_list_tables",
        "dm_list_views",
        "dm_describe_table",
        "dm_get_view_definition",
        "dm_update_config",
    ]


def test_db_exports_no_legacy_config_types():
    assert hasattr(db, "DmConfig")
    assert not hasattr(db, "PoolConfig")
    assert not hasattr(db, "CacheConfig")
