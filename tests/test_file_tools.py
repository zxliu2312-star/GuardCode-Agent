"""
文件操作工具测试

覆盖 read_file、write_file、list_files、delete_file 的正常流程和路径逃逸防护。
"""

import os
import sys
from pathlib import Path

import pytest

from guardcode import workspace as workspace_module
from guardcode.workspace import init_workspace
from guardcode.tools.file_tools import read_file, write_file, list_files, delete_file


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区并初始化全局管理器"""
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    workspace_module._workspace_manager = None
    init_workspace(str(ws))
    yield ws
    workspace_module._workspace_manager = None


class TestReadFile:
    """read_file 测试"""

    def test_read_existing_file(self, workspace):
        """读取存在的文件"""
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        result = read_file("main.py")
        assert result["success"] is True
        assert result["result"] == "print('hello')"
        assert result["error"] == ""

    def test_read_nonexistent_file(self, workspace):
        """读取不存在的文件"""
        result = read_file("nonexistent.py")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_read_directory_as_file(self, workspace):
        """把目录当文件读取"""
        (workspace / "subdir").mkdir()
        result = read_file("subdir")
        assert result["success"] is False
        assert "not a file" in result["error"]

    def test_read_path_traversal_blocked(self, workspace):
        """路径穿越被拒绝"""
        result = read_file("../../../etc/passwd")
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_read_absolute_path_outside_blocked(self, workspace, tmp_path):
        """workspace 外绝对路径被拒绝"""
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        result = read_file(str(outside))
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_read_file_in_subdirectory(self, workspace):
        """读取子目录中的文件"""
        subdir = workspace / "src"
        subdir.mkdir()
        (subdir / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
        result = read_file("src/utils.py")
        assert result["success"] is True
        assert "def add" in result["result"]


class TestWriteFile:
    """write_file 测试"""

    def test_write_new_file(self, workspace):
        """写入新文件"""
        result = write_file("main.py", "print('hello')")
        assert result["success"] is True
        assert (workspace / "main.py").read_text(encoding="utf-8") == "print('hello')"

    def test_write_overwrite_existing(self, workspace):
        """覆盖已有文件"""
        (workspace / "main.py").write_text("old content", encoding="utf-8")
        result = write_file("main.py", "new content")
        assert result["success"] is True
        assert (workspace / "main.py").read_text(encoding="utf-8") == "new content"

    def test_write_creates_parent_dirs(self, workspace):
        """自动创建父目录"""
        result = write_file("src/deep/nested/file.py", "content")
        assert result["success"] is True
        assert (workspace / "src" / "deep" / "nested" / "file.py").exists()

    def test_write_path_traversal_blocked(self, workspace):
        """路径穿越被拒绝"""
        result = write_file("../../../tmp/evil.txt", "hacked")
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_write_absolute_path_outside_blocked(self, workspace, tmp_path):
        """workspace 外绝对路径被拒绝"""
        outside = tmp_path / "outside_write.txt"
        result = write_file(str(outside), "content")
        assert result["success"] is False
        assert "outside workspace" in result["error"]


class TestListFiles:
    """list_files 测试"""

    def test_list_root_directory(self, workspace):
        """列出根目录"""
        (workspace / "a.py").write_text("a", encoding="utf-8")
        (workspace / "b.py").write_text("b", encoding="utf-8")
        (workspace / "subdir").mkdir()

        result = list_files(".")
        assert result["success"] is True
        assert "a.py" in result["result"]
        assert "b.py" in result["result"]
        # 目录带尾部斜杠
        dir_entries = [item for item in result["result"] if "subdir" in item]
        assert len(dir_entries) == 1

    def test_list_empty_directory(self, workspace):
        """空目录"""
        result = list_files(".")
        assert result["success"] is True
        assert result["result"] == []

    def test_list_nonexistent_directory(self, workspace):
        """不存在的目录"""
        result = list_files("nonexistent")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_list_path_traversal_blocked(self, workspace):
        """路径穿越被拒绝"""
        result = list_files("../../../")
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_list_subdirectory(self, workspace):
        """列出子目录"""
        subdir = workspace / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("main", encoding="utf-8")
        (subdir / "utils.py").write_text("utils", encoding="utf-8")

        result = list_files("src")
        assert result["success"] is True
        # Windows 用 \ 作为路径分隔符，兼容两种
        assert any("main.py" in item for item in result["result"])
        assert any("utils.py" in item for item in result["result"])


class TestDeleteFile:
    """delete_file 测试"""

    def test_delete_existing_file(self, workspace):
        """删除存在的文件"""
        (workspace / "temp.py").write_text("temp", encoding="utf-8")
        result = delete_file("temp.py")
        assert result["success"] is True
        assert not (workspace / "temp.py").exists()

    def test_delete_nonexistent_file(self, workspace):
        """删除不存在的文件"""
        result = delete_file("nonexistent.py")
        assert result["success"] is False
        assert "does not exist" in result["error"]

    def test_delete_directory_as_file(self, workspace):
        """把目录当文件删除"""
        (workspace / "subdir").mkdir()
        result = delete_file("subdir")
        assert result["success"] is False
        assert "not a file" in result["error"]

    def test_delete_path_traversal_blocked(self, workspace):
        """路径穿越被拒绝"""
        result = delete_file("../../../etc/passwd")
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_delete_absolute_path_outside_blocked(self, workspace, tmp_path):
        """workspace 外绝对路径被拒绝"""
        outside = tmp_path / "outside_delete.txt"
        outside.write_text("content")
        result = delete_file(str(outside))
        assert result["success"] is False
        assert "outside workspace" in result["error"]
