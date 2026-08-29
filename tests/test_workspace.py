"""
工作区管理模块测试

覆盖路径校验、路径逃逸防护、符号链接消解等安全核心逻辑。
"""

import os
import sys
from pathlib import Path

import pytest

from guardcode import workspace as workspace_module
from guardcode.workspace import WorkspaceManager, init_workspace, get_workspace


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区并初始化全局管理器"""
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    # 重置全局管理器
    workspace_module._workspace_manager = None
    manager = init_workspace(str(ws))
    yield ws
    # 清理
    workspace_module._workspace_manager = None


class TestWorkspaceInitialization:
    """工作区初始化测试"""

    def test_init_with_relative_path(self, tmp_path, monkeypatch):
        """相对路径初始化"""
        monkeypatch.chdir(tmp_path)
        workspace_module._workspace_manager = None
        manager = init_workspace(".")
        assert manager.workspace_root == tmp_path.resolve()
        workspace_module._workspace_manager = None

    def test_init_with_absolute_path(self, tmp_path):
        """绝对路径初始化"""
        ws = tmp_path / "workspace"
        ws.mkdir()
        workspace_module._workspace_manager = None
        manager = init_workspace(str(ws))
        assert manager.workspace_root == ws.resolve()
        workspace_module._workspace_manager = None

    def test_init_nonexistent_path_raises(self, tmp_path):
        """不存在的路径应报错"""
        workspace_module._workspace_manager = None
        with pytest.raises(ValueError, match="does not exist"):
            init_workspace(str(tmp_path / "nonexistent"))

    def test_init_file_not_directory_raises(self, tmp_path):
        """文件路径（非目录）应报错"""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        workspace_module._workspace_manager = None
        with pytest.raises(ValueError, match="not a directory"):
            init_workspace(str(file_path))
        workspace_module._workspace_manager = None

    def test_get_workspace_without_init_raises(self):
        """未初始化时获取工作区应报错"""
        workspace_module._workspace_manager = None
        with pytest.raises(RuntimeError, match="not initialized"):
            get_workspace()


class TestPathValidation:
    """路径校验测试"""

    def test_normal_relative_path(self, workspace):
        """正常相对路径应通过校验"""
        manager = get_workspace()
        result = manager.validate_path("main.py")
        assert result == (workspace / "main.py").resolve()

    def test_normal_relative_path_with_subdir(self, workspace):
        """带子目录的相对路径应通过校验"""
        subdir = workspace / "src"
        subdir.mkdir()
        manager = get_workspace()
        result = manager.validate_path("src/main.py")
        assert result == (workspace / "src" / "main.py").resolve()

    def test_absolute_path_inside_workspace(self, workspace):
        """workspace 内的绝对路径应通过"""
        manager = get_workspace()
        abs_path = str(workspace / "main.py")
        result = manager.validate_path(abs_path)
        assert result == (workspace / "main.py").resolve()

    def test_path_traversal_relative(self, workspace):
        """相对路径穿越 ../../../ 应被拒绝"""
        manager = get_workspace()
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path("../../../etc/passwd")

    def test_path_traversal_deep(self, workspace):
        """深层路径穿越应被拒绝"""
        manager = get_workspace()
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path("src/../../../etc/passwd")

    def test_absolute_path_outside_workspace(self, workspace, tmp_path):
        """workspace 外的绝对路径应被拒绝"""
        manager = get_workspace()
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path(str(outside))

    def test_windows_drive_path_outside(self, workspace):
        """Windows 盘符绝对路径应被拒绝"""
        manager = get_workspace()
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path("C:\\Windows\\System32\\config\\SAM")

    def test_is_within_workspace_true(self, workspace):
        """workspace 内路径返回 True"""
        manager = get_workspace()
        assert manager.is_within_workspace("main.py") is True

    def test_is_within_workspace_false(self, workspace):
        """workspace 外路径返回 False"""
        manager = get_workspace()
        assert manager.is_within_workspace("../../../etc/passwd") is False

    def test_get_relative_path(self, workspace):
        """获取相对路径"""
        manager = get_workspace()
        abs_path = (workspace / "src" / "main.py").resolve()
        subdir = workspace / "src"
        subdir.mkdir()
        rel = manager.get_relative_path(abs_path)
        assert str(rel) == "src" + os.sep + "main.py" or str(rel) == "src/main.py"


class TestSymlinkEscape:
    """符号链接逃逸测试"""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows 创建符号链接需要管理员权限",
    )
    def test_symlink_escape_blocked(self, workspace, tmp_path):
        """符号链接指向 workspace 外应被拒绝"""
        # 在 workspace 外创建目标文件
        outside_file = tmp_path / "outside_secret.txt"
        outside_file.write_text("secret data")

        # 在 workspace 内创建符号链接
        link_path = workspace / "link_to_secret"
        os.symlink(outside_file, link_path)

        manager = get_workspace()
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path("link_to_secret")

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows 创建符号链接需要管理员权限",
    )
    def test_symlink_to_directory_escape_blocked(self, workspace, tmp_path):
        """符号链接指向 workspace 外目录应被拒绝"""
        # 在 workspace 外创建目录
        outside_dir = tmp_path / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("secret")

        # 在 workspace 内创建符号链接
        link_path = workspace / "link_to_dir"
        os.symlink(outside_dir, link_path)

        manager = get_workspace()
        with pytest.raises(ValueError, match="outside workspace"):
            manager.validate_path("link_to_dir/secret.txt")

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows 创建符号链接需要管理员权限",
    )
    def test_symlink_inside_workspace_allowed(self, workspace):
        """workspace 内的符号链接（指向 workspace 内）应通过"""
        # 在 workspace 内创建目标文件
        target = workspace / "real_file.txt"
        target.write_text("content")

        # 在 workspace 内创建符号链接
        link = workspace / "link_to_real"
        os.symlink(target, link)

        manager = get_workspace()
        result = manager.validate_path("link_to_real")
        assert result == target.resolve()
