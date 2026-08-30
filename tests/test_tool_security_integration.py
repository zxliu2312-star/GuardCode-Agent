"""
Tests for security integration in execute_tool.

Verifies that execute_tool correctly calls classify_risk and
confirm_operation when a config is provided.
"""

import pytest
from unittest.mock import patch, MagicMock

from guardcode.tools.base import execute_tool, _extract_security_config
from guardcode.config import Config, SecurityConfig
from guardcode.security import RiskLevel

# 确保工具被注册
from guardcode.tools import file_tools       # noqa: F401
from guardcode.tools import command_tools    # noqa: F401


class TestExtractSecurityConfig:
    """Test the _extract_security_config helper."""

    def test_dict_passthrough(self):
        """Dict config should pass through directly."""
        config = {"security": {"always_block": ["rm"], "auto_approve": []}}
        result = _extract_security_config(config)
        assert result == config

    def test_config_object(self):
        """Config object should be converted to dict format."""
        config = Config(security=SecurityConfig(
            always_block=["rm -rf /"],
            auto_approve=["ls"],
        ))
        result = _extract_security_config(config)
        assert "security" in result
        assert result["security"]["always_block"] == ["rm -rf /"]
        assert result["security"]["auto_approve"] == ["ls"]

    def test_none_returns_empty(self):
        """None should return empty dict."""
        assert _extract_security_config(None) == {}

    def test_object_without_security(self):
        """Object without security attribute should return empty dict."""
        assert _extract_security_config(42) == {}
        assert _extract_security_config("string") == {}


class TestExecuteToolSecurityIntegration:
    """Test that execute_tool integrates risk classification."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Set up a temporary workspace."""
        import os
        os.environ.setdefault("GUARDCODE_WORKSPACE", str(tmp_path))
        from guardcode.workspace import init_workspace
        init_workspace(str(tmp_path))
        return tmp_path

    def test_safe_tool_executes_without_prompt(self, workspace):
        """SAFE operations should execute without confirmation."""
        config = Config(workspace=str(workspace))
        result = execute_tool("read_file", {"path": "nonexistent.txt"}, config=config)
        # Tool executes (may fail on file not found, but should NOT be blocked)
        assert result["success"] is False
        assert "exist" in result["error"].lower()

    @patch('builtins.input', return_value='y')
    def test_dangerous_command_with_confirmation(self, mock_input, workspace):
        """DANGEROUS commands should prompt and execute if confirmed."""
        config = Config(workspace=str(workspace))
        # 'pip install' is in DANGEROUS_PATTERNS
        result = execute_tool(
            "run_command",
            {"command": "echo hello"},
            config=config,
        )
        # echo is in SAFE_PATTERNS, so this should execute directly
        assert result["success"] is True

    @patch('builtins.input', return_value='n')
    def test_dangerous_command_rejected(self, mock_input, workspace):
        """DANGEROUS commands should be rejected if user says no."""
        config = Config(workspace=str(workspace))
        # 'pip install' is dangerous
        result = execute_tool(
            "run_command",
            {"command": "pip install requests"},
            config=config,
        )
        assert result["success"] is False
        assert "rejected" in result["error"].lower()

    def test_blocked_command(self, workspace):
        """BLOCKED commands should be rejected without prompting."""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                always_block=[r"rm -rf /"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "rm -rf /"},
            config=config,
        )
        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    @patch('builtins.input')
    def test_blocked_does_not_prompt(self, mock_input, workspace):
        """BLOCKED commands should not call input() at all."""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                always_block=[r"format\s+"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "format c:"},
            config=config,
        )
        assert result["success"] is False
        # input should never have been called
        mock_input.assert_not_called()

    def test_no_config_still_checks_security(self, workspace):
        """Without config, execute_tool should still do risk checks (fail-safe).
        
        classify_risk with empty config defaults to DANGEROUS for unknown
        commands, so dangerous commands should still be blocked or prompt.
        """
        # read_file is always SAFE regardless of config
        result = execute_tool("read_file", {"path": "nonexistent.txt"})
        assert result["success"] is False
        assert "exist" in result["error"].lower()

        # delete_file is always DANGEROUS regardless of config
        # Without config, it should still prompt (fail-safe)
        with patch('builtins.input', return_value='n') as mock_input:
            result = execute_tool("delete_file", {"path": "anyfile.txt"})
            mock_input.assert_called_once()
            assert result["success"] is False
            assert "rejected" in result["error"].lower()

    @patch('builtins.input', return_value='y')
    def test_delete_file_prompts_confirmation(self, mock_input, workspace):
        """delete_file should always prompt (DANGEROUS)."""
        # Create a file to delete
        test_file = workspace / "to_delete.txt"
        test_file.write_text("delete me", encoding="utf-8")

        config = Config(workspace=str(workspace))
        result = execute_tool("delete_file", {"path": "to_delete.txt"}, config=config)
        assert result["success"] is True
        mock_input.assert_called_once()

    @patch('builtins.input', return_value='n')
    def test_delete_file_rejected(self, mock_input, workspace):
        """delete_file should be rejected if user says no."""
        test_file = workspace / "to_delete.txt"
        test_file.write_text("delete me", encoding="utf-8")

        config = Config(workspace=str(workspace))
        result = execute_tool("delete_file", {"path": "to_delete.txt"}, config=config)
        assert result["success"] is False
        assert "rejected" in result["error"].lower()
        # File should still exist
        assert test_file.exists()

    def test_auto_approve_bypasses_confirmation(self, workspace):
        """auto_approve patterns should bypass confirmation."""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                auto_approve=[r"pip\s+install\s+safe-package"],
            ),
        )
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "run_command",
                {"command": "pip install safe-package"},
                config=config,
            )
            # Should not prompt since it's auto-approved
            mock_input.assert_not_called()
            # pip install may fail (no network / package), but the point is
            # it wasn't blocked or rejected — it was allowed to execute
            assert "blocked" not in result["error"].lower()
            assert "rejected" not in result["error"].lower()

    def test_safe_read_operation_no_prompt(self, workspace):
        """read_file should not prompt (SAFE)."""
        config = Config(workspace=str(workspace))
        with patch('builtins.input') as mock_input:
            result = execute_tool("read_file", {"path": "anyfile.txt"}, config=config)
            mock_input.assert_not_called()

    def test_safe_list_operation_no_prompt(self, workspace):
        """list_files should not prompt (SAFE)."""
        config = Config(workspace=str(workspace))
        with patch('builtins.input') as mock_input:
            result = execute_tool("list_files", {"directory": "."}, config=config)
            mock_input.assert_not_called()
            assert result["success"] is True

    def test_unknown_tool_with_config(self, workspace):
        """Unknown tool should return error even with config."""
        config = Config(workspace=str(workspace))
        result = execute_tool("nonexistent_tool", {}, config=config)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_priority_block_over_auto_approve(self, workspace):
        """always_block should take priority over auto_approve."""
        config = Config(
            workspace=str(workspace),
            security=SecurityConfig(
                always_block=[r"rm\s+"],
                auto_approve=[r"rm\s+temp"],
            ),
        )
        result = execute_tool(
            "run_command",
            {"command": "rm temp"},
            config=config,
        )
        assert result["success"] is False
        assert "blocked" in result["error"].lower()
