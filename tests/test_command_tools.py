"""
命令执行工具测试

覆盖 run_command 的正常执行、超时、错误码、工作目录等场景。
"""

import sys
import pytest
from pathlib import Path

from guardcode import workspace as workspace_module
from guardcode.workspace import init_workspace
from guardcode.tools.command_tools import run_command


@pytest.fixture
def workspace(tmp_path):
    """创建临时工作区并初始化全局管理器"""
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    workspace_module._workspace_manager = None
    init_workspace(str(ws))
    yield ws
    workspace_module._workspace_manager = None


class TestRunCommand:
    """run_command 测试"""

    def test_run_simple_command(self, workspace):
        """执行简单命令"""
        if sys.platform == "win32":
            result = run_command("echo hello")
        else:
            result = run_command("echo hello")
        
        assert result["success"] is True
        assert "hello" in result["result"].lower()
        assert result["exit_code"] == 0

    def test_run_command_with_output(self, workspace):
        """执行有输出的命令"""
        if sys.platform == "win32":
            result = run_command("powershell -Command \"Write-Output 'test output'\"")
        else:
            result = run_command("echo 'test output'")
        
        assert result["success"] is True
        assert "test output" in result["result"]

    def test_run_command_failure(self, workspace):
        """执行失败的命令（非零退出码）"""
        if sys.platform == "win32":
            result = run_command("exit 1")
        else:
            result = run_command("exit 1")
        
        assert result["success"] is False
        assert result["exit_code"] == 1
        # Windows 的 exit 命令不产生 stderr，只返回退出码

    def test_run_nonexistent_command(self, workspace):
        """执行不存在的命令"""
        result = run_command("this_command_definitely_does_not_exist_12345")
        assert result["success"] is False
        # Windows: "not recognized", Linux/Mac: "not found" 或 "command not found"
        error_msg = result["error"].lower()
        assert "not recognized" in error_msg or "not found" in error_msg or "command not found" in error_msg

    def test_run_command_timeout(self, workspace):
        """命令执行超时"""
        if sys.platform == "win32":
            # Windows: 使用 timeout 命令（但它不响应 Ctrl+C，用 ping 代替）
            result = run_command("ping -n 6 127.0.0.1", timeout=2)
        else:
            result = run_command("sleep 10", timeout=2)
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()

    def test_run_command_in_workspace(self, workspace):
        """命令在工作区目录执行"""
        # 创建测试文件
        test_file = workspace / "test.txt"
        test_file.write_text("content")
        
        if sys.platform == "win32":
            result = run_command("dir test.txt")
            assert result["success"] is True
            assert "test.txt" in result["result"]
        else:
            result = run_command("ls test.txt")
            assert result["success"] is True
            assert "test.txt" in result["result"]

    def test_run_python_command(self, workspace):
        """执行 Python 命令"""
        result = run_command('python -c "print(1+1)"')
        assert result["success"] is True
        assert "2" in result["result"]

    def test_run_command_with_stderr(self, workspace):
        """捕获 stderr 输出"""
        if sys.platform == "win32":
            result = run_command('python -c "import sys; sys.stderr.write(\'error message\\n\')"')
        else:
            result = run_command('python -c "import sys; sys.stderr.write(\'error message\\n\')"')
        
        # stderr 被捕获到 result 中（stdout 和 stderr 合并）
        assert "error message" in result["result"] or "error message" in result.get("error", "")

    def test_run_command_multiline_output(self, workspace):
        """多行输出"""
        if sys.platform == "win32":
            result = run_command('python -c "print(\'line1\'); print(\'line2\'); print(\'line3\')"')
        else:
            result = run_command('python -c "print(\'line1\\nline2\\nline3\')"')
        
        assert result["success"] is True
        assert "line1" in result["result"]
        assert "line2" in result["result"]
        assert "line3" in result["result"]

    def test_run_command_empty_output(self, workspace):
        """空输出命令"""
        if sys.platform == "win32":
            result = run_command("cd .")
        else:
            result = run_command("true")
        
        assert result["success"] is True
        # 空输出也是成功的
        assert result["exit_code"] == 0
