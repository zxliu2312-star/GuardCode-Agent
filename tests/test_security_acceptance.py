"""
Tests for 2.8: 安全机制验收测试

端到端验证安全功能在 agent 循环中的表现：
1. 危险命令触发确认
2. 代码风险触发警告
3. 自定义 auto_approve 自动放行
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from guardcode.agent import run_agent_loop
from guardcode.config import Config, SecurityConfig
from guardcode.workspace import init_workspace
from guardcode.tools import file_tools, command_tools  # noqa: F401
from guardcode.tools.base import execute_tool


@pytest.fixture
def workspace(tmp_path):
    """临时工作区。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    init_workspace(str(ws))
    return ws


# ── 2.8.1 危险命令触发确认 ─────────────────────────────────


class TestDangerousCommandConfirmation:
    """验收：危险命令应该触发用户确认。"""

    def test_rm_rf_prompts_confirmation(self, workspace):
        """rm -rf 命令应该触发确认提示。"""
        config = Config(workspace=str(workspace))
        # 模拟非交互环境，input 抛 EOFError → 确认失败 → 操作被拒绝
        with patch('builtins.input', side_effect=EOFError()) as mock_input:
            result = execute_tool(
                "run_command",
                {"command": "rm -rf /tmp/test"},
                config=config,
            )
            mock_input.assert_called_once()
            assert result["success"] is False

    @patch('builtins.input', return_value='y')
    def test_rm_rf_executes_on_confirm(self, mock_input, workspace):
        """用户确认后 rm 命令应该执行。"""
        config = Config(workspace=str(workspace))
        result = execute_tool(
            "run_command",
            {"command": "rm -rf nonexist_dir"},
            config=config,
        )
        mock_input.assert_called_once()
        # rm 可能因为目录不存在而失败，但不应该被安全策略阻止
        assert "blocked" not in result["error"].lower()
        assert "rejected" not in result["error"].lower()

    @patch('builtins.input', return_value='n')
    def test_rm_rf_rejected_by_user(self, mock_input, workspace):
        """用户拒绝后 rm 命令不应该执行。"""
        config = Config(workspace=str(workspace))
        result = execute_tool(
            "run_command",
            {"command": "rm -rf nonexist_dir"},
            config=config,
        )
        assert result["success"] is False
        assert "rejected" in result["error"].lower()

    def test_pip_install_prompts_confirmation(self, workspace):
        """pip install 应该触发确认。"""
        config = Config(workspace=str(workspace))
        with patch('builtins.input', return_value='n') as mock_input:
            result = execute_tool(
                "run_command",
                {"command": "pip install requests"},
                config=config,
            )
            mock_input.assert_called_once()
            assert result["success"] is False
            assert "rejected" in result["error"].lower()

    def test_safe_command_no_prompt(self, workspace):
        """安全命令不应该触发确认。"""
        config = Config(workspace=str(workspace))
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "run_command",
                {"command": "echo hello"},
                config=config,
            )
            mock_input.assert_not_called()
            assert result["success"] is True


# ── 2.8.2 代码风险触发警告 ─────────────────────────────────


class TestCodeRiskWarning:
    """验收：写入含 eval() 的代码应该触发风险警告。"""

    @patch('builtins.input', return_value='a')
    def test_eval_code_aborts_write(self, mock_input, workspace):
        """含 eval() 的代码应该触发警告，用户选择 abort 时不写入。"""
        config = Config(workspace=str(workspace))
        result = execute_tool(
            "write_file",
            {"path": "bad.py", "content": "eval('os.system(\"rm -rf /\")')\n"},
            config=config,
        )
        assert result["success"] is False
        assert "aborted" in result["error"].lower()
        # 文件不应该存在
        assert not (workspace / "bad.py").exists()

    @patch('builtins.input', return_value='c')
    def test_eval_code_continues_write(self, mock_input, workspace):
        """含 eval() 的代码，用户选择 continue 时写入。"""
        config = Config(workspace=str(workspace))
        result = execute_tool(
            "write_file",
            {"path": "risky.py", "content": "x = eval('1+1')\n"},
            config=config,
        )
        assert result["success"] is True
        assert (workspace / "risky.py").exists()
        assert (workspace / "risky.py").read_text() == "x = eval('1+1')\n"

    @patch('builtins.input')
    def test_multiple_risks_shown(self, mock_input, workspace):
        """多个风险应该全部显示。"""
        mock_input.return_value = 'a'
        config = Config(workspace=str(workspace))
        code = "import os\nos.system('ls')\neval('x')\nexec('y')\n"
        result = execute_tool(
            "write_file",
            {"path": "multi.py", "content": code},
            config=config,
        )
        assert result["success"] is False
        # 应该调用了一次 input（确认）
        mock_input.assert_called_once()

    def test_clean_code_no_warning(self, workspace):
        """干净代码不应该触发警告。"""
        config = Config(workspace=str(workspace))
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "clean.py", "content": "x = 1\nprint(x)\n"},
                config=config,
            )
            mock_input.assert_not_called()
            assert result["success"] is True


# ── 2.8.3 自定义 auto_approve 自动放行 ─────────────────────


class TestCustomAutoApprove:
    """验收：配置 auto_approve 后危险命令自动放行。"""

    @patch('builtins.input')
    def test_auto_approve_bypasses_prompt(self, mock_input, workspace):
        """auto_approve 匹配的命令不应该触发确认。"""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                auto_approve=[r"pip install\s+safe-package"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "pip install safe-package"},
            config=config,
        )
        # 不应该调用 input
        mock_input.assert_not_called()
        # 不应该被 rejected 或 blocked
        assert "rejected" not in result["error"].lower()
        assert "blocked" not in result["error"].lower()

    @patch('builtins.input')
    def test_auto_approve_regex_match(self, mock_input, workspace):
        """auto_approve 用正则匹配。"""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                auto_approve=[r"rm\s+.*\.pyc"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "rm test.pyc"},
            config=config,
        )
        mock_input.assert_not_called()
        assert "rejected" not in result["error"].lower()

    @patch('builtins.input', return_value='n')
    def test_non_matching_auto_approve_still_prompts(self, mock_input, workspace):
        """不匹配 auto_approve 的命令仍然触发确认。"""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                auto_approve=[r"pip install\s+safe-package"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "pip install dangerous-package"},
            config=config,
        )
        # 不匹配 auto_approve，应该触发确认
        mock_input.assert_called_once()
        assert result["success"] is False
        assert "rejected" in result["error"].lower()

    def test_always_block_overrides_auto_approve(self, workspace):
        """always_block 优先级高于 auto_approve。"""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                always_block=[r"rm -rf"],
                auto_approve=[r"rm -rf"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "rm -rf test"},
            config=config,
        )
        assert result["success"] is False
        assert "blocked" in result["error"].lower()


# ── 2.8.4 端到端 Agent 循环安全测试 ────────────────────────


class TestAgentLoopSecurity:
    """验收：在 agent 循环中安全机制正常工作。"""

    @patch('builtins.input', return_value='n')
    def test_agent_loop_blocks_dangerous_command(self, mock_input, workspace):
        """Agent 循环中，危险命令被用户拒绝后返回错误。"""
        config = Config(workspace=str(workspace))

        # 模拟模型返回一个危险命令调用
        mock_response = {
            "content": None,
            "tool_calls": [{
                "id": "call-1",
                "name": "run_command",
                "arguments": {"command": "rm -rf /tmp/test"},
            }],
            "finish_reason": "tool_calls",
        }
        mock_final = {
            "content": "OK, I won't delete.",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        with patch('guardcode.agent.call_model', side_effect=[mock_response, mock_final]):
            with patch('guardcode.agent.init_workspace'):
                result = run_agent_loop("delete temp files", config=config, max_iterations=5)

        # 用户拒绝了，工具返回错误
        # agent 应该继续运行并最终返回
        assert isinstance(result, str)

    @patch('builtins.input', return_value='a')
    def test_agent_loop_warns_code_risk(self, mock_input, workspace):
        """Agent 循环中，写入危险代码被用户中止。"""
        config = Config(workspace=str(workspace))

        mock_response = {
            "content": None,
            "tool_calls": [{
                "id": "call-1",
                "name": "write_file",
                "arguments": {"path": "bad.py", "content": "eval('x')\n"},
            }],
            "finish_reason": "tool_calls",
        }
        mock_final = {
            "content": "Write aborted by user.",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        with patch('guardcode.agent.call_model', side_effect=[mock_response, mock_final]):
            with patch('guardcode.agent.init_workspace'):
                result = run_agent_loop("write eval script", config=config, max_iterations=5)

        assert isinstance(result, str)
        # 文件不应该被写入
        assert not (workspace / "bad.py").exists()
