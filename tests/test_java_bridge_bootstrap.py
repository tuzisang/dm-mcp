"""Java 桥接启动引导与错误传播回归测试。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import db.client as client_module
import db.java_bridge as java_bridge_module
from core.exceptions import DatabaseConnectionError
from db.client import get_shared_client, reset_shared_client
from db.java_bridge import JavaBridgeClient, JavaBridgeError


def _bootstrap_client() -> JavaBridgeClient:
    client = object.__new__(JavaBridgeClient)
    client.config = {}
    return client


def _patch_bridge_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path]:
    bridge_dir = tmp_path / "db"
    lib_dir = tmp_path / "lib"
    bridge_dir.mkdir()
    lib_dir.mkdir()

    source_file = bridge_dir / "DmJdbcBridge.java"
    class_file = bridge_dir / "DmJdbcBridge.class"

    monkeypatch.setattr(java_bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(java_bridge_module, "LIB_DIR", lib_dir)
    monkeypatch.setattr(java_bridge_module, "BRIDGE_SOURCE_FILE", source_file)
    monkeypatch.setattr(java_bridge_module, "BRIDGE_CLASS_FILE", class_file)
    return source_file, class_file


@pytest.fixture(autouse=True)
def reset_shared_runtime():
    reset_shared_client()
    yield
    reset_shared_client()


def test_bridge_class_needs_compile_when_source_is_newer(tmp_path, monkeypatch):
    source_file, class_file = _patch_bridge_paths(monkeypatch, tmp_path)
    source_file.write_text("class source", encoding="utf-8")
    class_file.write_text("compiled", encoding="utf-8")
    os.utime(class_file, (10, 10))
    os.utime(source_file, (20, 20))

    client = _bootstrap_client()

    assert client._bridge_class_needs_compile() is True


def test_ensure_bridge_class_ready_invokes_javac_when_class_missing(tmp_path, monkeypatch):
    source_file, class_file = _patch_bridge_paths(monkeypatch, tmp_path)
    source_file.write_text("public class DmJdbcBridge {}", encoding="utf-8")
    commands = []

    def fake_run(args, capture_output, text, check, env):
        commands.append(args)
        class_file.write_text("compiled", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(java_bridge_module.subprocess, "run", fake_run)
    client = _bootstrap_client()
    monkeypatch.setattr(client, "_find_javac", lambda java_home: "/fake/bin/javac")

    client._ensure_bridge_class_ready("/fake/java-home")

    assert class_file.exists()
    assert commands == [[
        "/fake/bin/javac",
        "-cp",
        os.pathsep.join([str((tmp_path / "lib") / "*"), str(tmp_path / "db")]),
        str(source_file),
    ]]


def test_ensure_bridge_class_ready_surfaces_javac_output(tmp_path, monkeypatch):
    source_file, _ = _patch_bridge_paths(monkeypatch, tmp_path)
    source_file.write_text("public class DmJdbcBridge {}", encoding="utf-8")

    def fake_run(args, capture_output, text, check, env):
        return subprocess.CompletedProcess(args, 1, "", "missing dependency")

    monkeypatch.setattr(java_bridge_module.subprocess, "run", fake_run)
    client = _bootstrap_client()
    monkeypatch.setattr(client, "_find_javac", lambda java_home: "/fake/bin/javac")

    with pytest.raises(JavaBridgeError, match="missing dependency"):
        client._ensure_bridge_class_ready("/fake/java-home")


def test_ensure_bridge_class_ready_reports_missing_javac(tmp_path, monkeypatch):
    source_file, _ = _patch_bridge_paths(monkeypatch, tmp_path)
    source_file.write_text("public class DmJdbcBridge {}", encoding="utf-8")

    client = _bootstrap_client()

    def raise_missing_javac(java_home):
        raise JavaBridgeError("找不到 javac。首次启动或 Java 桥接源码更新时需要可用的 JDK。")

    monkeypatch.setattr(client, "_find_javac", raise_missing_javac)

    with pytest.raises(JavaBridgeError, match="找不到 javac"):
        client._ensure_bridge_class_ready("/fake/java-home")


def test_get_shared_client_propagates_bridge_startup_root_cause():
    class FakeClient:
        def __init__(self, message: str):
            self.message = message
            self.closed = False

        def ensure_connected(self) -> None:
            raise DatabaseConnectionError(self.message)

        def close(self) -> None:
            self.closed = True

    first = FakeClient(
        "Java 守护进程启动失败: 错误: 找不到或无法加载主类 DmJdbcBridge 原因: java.lang.ClassNotFoundException: DmJdbcBridge"
    )
    second = FakeClient(
        "Java 守护进程启动失败: 错误: 找不到或无法加载主类 DmJdbcBridge 原因: java.lang.ClassNotFoundException: DmJdbcBridge"
    )

    with patch.object(client_module, "_new_client", side_effect=[first, second]):
        with pytest.raises(DatabaseConnectionError, match="ClassNotFoundException: DmJdbcBridge"):
            get_shared_client()

    assert first.closed is True
