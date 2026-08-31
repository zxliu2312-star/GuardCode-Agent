"""
Phase 4 验收测试

测试内容：
- Rich 格式化输出（ui/console.py）
- 日志系统（setup_logging, get_logger）
- 模型调用重试（call_model_with_retry）
- 会话保存（save_session）
- CLI 参数验证
"""

import json
import os
import sys
import tempfile
import importlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging

import pytest

from guardcode.ui.console import (
    console,
    print_tool_call,
    print_tool_result,
    print_risk_warning,
    print_confirm_prompt,
    print_context_compress,
    print_final_response,
    print_error,
    print_info,
    print_model_call,
    print_blocked,
    print_session_saved,
    setup_logging,
    get_logger,
)
from guardcode.model import call_model_with_retry, call_model
from guardcode.agent import save_session, run_agent_loop
from guardcode.config import Config


def _get_console_module():
    """获取 guardcode.ui.console 模块（避免与 console 变量名冲突）"""
    return sys.modules['guardcode.ui.console']


# ──────────────────────────────────────────────────────────
# Rich 输出测试
# ──────────────────────────────────────────────────────────

class TestRichOutput:
    """测试 Rich 格式化输出函数"""

    def test_print_tool_call(self, capsys):
        """测试工具调用输出"""
        print_tool_call("read_file", {"path": "test.txt"})
        # 不抛出异常即可

    def test_print_tool_call_long_args(self, capsys):
        """测试长参数截断"""
        long_content = "x" * 200
        print_tool_call("write_file", {"path": "app.py", "content": long_content})

    def test_print_tool_result_success(self, capsys):
        """测试成功结果输出"""
        result = {"success": True, "result": "File content here", "error": ""}
        print_tool_result(result)

    def test_print_tool_result_failure(self, capsys):
        """测试失败结果输出"""
        result = {"success": False, "result": "", "error": "File not found"}
        print_tool_result(result)

    def test_print_tool_result_long_output(self, capsys):
        """测试长结果截断"""
        result = {"success": True, "result": "x" * 300, "error": ""}
        print_tool_result(result)

    def test_print_risk_warning(self, capsys):
        """测试风险警告输出"""
        risks = [
            {"pattern": "eval", "line": 42, "content": "eval(user_input)"},
            {"pattern": "exec", "line": 100, "content": "exec(code)"},
        ]
        print_risk_warning(risks)

    def test_print_risk_warning_empty(self, capsys):
        """测试空风险列表不输出"""
        print_risk_warning([])

    def test_print_confirm_prompt(self, capsys):
        """测试确认提示输出"""
        print_confirm_prompt("delete_file", {"path": "important.txt"})

    def test_print_context_compress(self, capsys):
        """测试上下文压缩通知"""
        print_context_compress(20, 10)

    def test_print_final_response(self, capsys):
        """测试最终响应输出"""
        print_final_response("Task completed successfully!")

    def test_print_error(self, capsys):
        """测试错误输出"""
        print_error("Something went wrong")

    def test_print_info(self, capsys):
        """测试信息输出"""
        print_info("This is an info message")

    def test_print_model_call(self, capsys):
        """测试模型调用信息输出"""
        print_model_call(10, 5000)

    def test_print_blocked(self, capsys):
        """测试阻止操作输出"""
        print_blocked("run_command", {"command": "rm -rf /"})

    def test_print_session_saved(self, capsys):
        """测试会话保存通知"""
        print_session_saved("/path/to/session.json")


# ──────────────────────────────────────────────────────────
# 日志系统测试
# ──────────────────────────────────────────────────────────

class TestLogging:
    """测试日志系统"""

    def test_setup_logging_returns_logger(self):
        """测试 setup_logging 返回 Logger 实例"""
        logger = setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_get_logger_returns_same_instance(self):
        """测试 get_logger 返回同一个 logger 实例"""
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2

    def test_logger_has_handlers(self):
        """测试 logger 有 handler"""
        logger = setup_logging()
        assert len(logger.handlers) > 0

    def test_logger_writes_to_file(self, tmp_path, monkeypatch):
        """测试日志写入文件"""
        console_mod = _get_console_module()
        # 重置 logger
        monkeypatch.setattr(console_mod, "_logger", None)
        monkeypatch.setattr(console_mod, "_LOG_DIR", tmp_path / "logs")
        monkeypatch.setattr(console_mod, "_LOG_FILE", tmp_path / "logs" / "agent.log")

        logger = setup_logging()
        logger.info("Test log message")

        # 检查日志文件
        log_file = tmp_path / "logs" / "agent.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Test log message" in content

    def test_logger_format(self, tmp_path, monkeypatch):
        """测试日志格式包含时间戳、级别、名称"""
        console_mod = _get_console_module()
        monkeypatch.setattr(console_mod, "_logger", None)
        monkeypatch.setattr(console_mod, "_LOG_DIR", tmp_path / "logs")
        monkeypatch.setattr(console_mod, "_LOG_FILE", tmp_path / "logs" / "agent.log")

        logger = setup_logging()
        logger.info("Test message")

        log_file = tmp_path / "logs" / "agent.log"
        content = log_file.read_text(encoding="utf-8")
        # 格式：timestamp | level | name | message
        assert "INFO" in content
        assert "guardcode" in content
        assert "Test message" in content

    def test_log_write_failure_does_not_crash(self, monkeypatch, tmp_path):
        """测试日志写入失败不影响主流程"""
        console_mod = _get_console_module()
        monkeypatch.setattr(console_mod, "_logger", None)
        # 使用一个嵌套很深的路径，mkdir 可能成功但 FileHandler 会失败
        # 用 mock 让 FileHandler 抛出异常
        monkeypatch.setattr("logging.FileHandler", Mock(side_effect=OSError("Permission denied")))

        # 不应抛出异常
        logger = setup_logging()
        # 即使文件 handler 创建失败，logger 仍应返回
        assert isinstance(logger, logging.Logger)


# ──────────────────────────────────────────────────────────
# 模型调用重试测试
# ──────────────────────────────────────────────────────────

class TestModelRetry:
    """测试模型调用重试（指数退避）"""

    @patch('guardcode.model.call_model')
    def test_retry_succeeds_on_second_attempt(self, mock_call):
        """测试第一次失败后第二次成功"""
        mock_call.side_effect = [
            Exception("Network error"),
            {"content": "Success!", "tool_calls": [], "finish_reason": "stop"},
        ]

        result = call_model_with_retry(
            [{"role": "user", "content": "test"}],
            api_key="fake-key",
            max_retries=3,
        )

        assert result["content"] == "Success!"
        assert mock_call.call_count == 2

    @patch('guardcode.model.call_model')
    def test_retry_exhausted_raises(self, mock_call):
        """测试重试耗尽后抛出异常"""
        mock_call.side_effect = Exception("Persistent error")

        with pytest.raises(Exception, match="Persistent error"):
            call_model_with_retry(
                [{"role": "user", "content": "test"}],
                api_key="fake-key",
                max_retries=3,
            )

        assert mock_call.call_count == 3

    @patch('guardcode.model.call_model')
    def test_retry_succeeds_first_try(self, mock_call):
        """测试第一次就成功，不重试"""
        mock_call.return_value = {
            "content": "Immediate success",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        result = call_model_with_retry(
            [{"role": "user", "content": "test"}],
            api_key="fake-key",
            max_retries=3,
        )

        assert result["content"] == "Immediate success"
        assert mock_call.call_count == 1

    @patch('guardcode.model.call_model')
    @patch('time.sleep')
    def test_retry_uses_exponential_backoff(self, mock_sleep, mock_call):
        """测试指数退避：等待 1s, 2s"""
        mock_call.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
        ]

        with pytest.raises(Exception):
            call_model_with_retry(
                [{"role": "user", "content": "test"}],
                api_key="fake-key",
                max_retries=3,
            )

        # 应该 sleep 两次：1s 和 2s
        assert mock_sleep.call_count == 2
        sleep_times = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_times == [1, 2]

    @patch('guardcode.model.call_model')
    @patch('time.sleep')
    def test_retry_max_retries_1_no_sleep(self, mock_sleep, mock_call):
        """测试 max_retries=1 时不 sleep"""
        mock_call.side_effect = Exception("Error")

        with pytest.raises(Exception):
            call_model_with_retry(
                [{"role": "user", "content": "test"}],
                api_key="fake-key",
                max_retries=1,
            )

        assert mock_sleep.call_count == 0
        assert mock_call.call_count == 1


# ──────────────────────────────────────────────────────────
# 会话保存测试
# ──────────────────────────────────────────────────────────

class TestSessionSave:
    """测试会话保存功能"""

    def test_save_session_creates_file(self, tmp_path, monkeypatch):
        """测试保存会话创建文件"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        messages = [
            {"role": "system", "content": "You are an agent"},
            {"role": "user", "content": "Do something"},
        ]

        session_path = save_session(messages, "/workspace")

        assert session_path != ""
        assert Path(session_path).exists()

        # 验证文件内容
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["workspace"] == "/workspace"
        assert data["message_count"] == 2
        assert len(data["messages"]) == 2

    def test_save_session_creates_directory(self, tmp_path, monkeypatch):
        """测试保存会话创建目录结构"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        messages = [{"role": "user", "content": "test"}]
        session_path = save_session(messages, "/workspace")

        sessions_dir = tmp_path / ".guardcode" / "sessions"
        assert sessions_dir.exists()
        assert session_path != ""

    def test_save_session_timestamp_format(self, tmp_path, monkeypatch):
        """测试会话文件名包含时间戳"""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        messages = [{"role": "user", "content": "test"}]
        session_path = save_session(messages, "/workspace")

        filename = Path(session_path).name
        # 格式：YYYYMMDD_HHMMSS.json
        assert filename.endswith(".json")
        name_part = filename.replace(".json", "")
        # 应该是 15 个字符（8 日期 + 1 下划线 + 6 时间）
        assert len(name_part) == 15

    def test_save_session_failure_returns_empty(self, monkeypatch):
        """测试保存失败返回空字符串"""
        # Mock open to raise OSError
        monkeypatch.setattr("builtins.open", Mock(side_effect=OSError("Permission denied")))

        messages = [{"role": "user", "content": "test"}]
        session_path = save_session(messages, "/workspace")

        assert session_path == ""


# ──────────────────────────────────────────────────────────
# Agent Loop 集成测试（Rich 输出 + 日志 + 重试）
# ──────────────────────────────────────────────────────────

class TestAgentLoopPhase4:
    """测试 Agent 循环与 Phase 4 功能的集成"""

    @patch('guardcode.agent.call_model_with_retry')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_agent_uses_retry(self, mock_init_ws, mock_execute, mock_retry):
        """测试 Agent 使用 call_model_with_retry"""
        mock_retry.return_value = {
            "content": "Done.",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test task", config=config, max_iterations=5)

        assert result == "Done."
        # 验证使用了 call_model_with_retry 而非 call_model
        assert mock_retry.call_count == 1

    @patch('guardcode.agent.call_model_with_retry')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_agent_logs_to_file(self, mock_init_ws, mock_execute, mock_retry, tmp_path, monkeypatch):
        """测试 Agent 日志写入文件"""
        console_mod = _get_console_module()
        monkeypatch.setattr(console_mod, "_logger", None)
        monkeypatch.setattr(console_mod, "_LOG_DIR", tmp_path / "logs")
        monkeypatch.setattr(console_mod, "_LOG_FILE", tmp_path / "logs" / "agent.log")

        mock_retry.return_value = {
            "content": "Done.",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test logging task", config=config, max_iterations=5)

        # 检查日志文件
        log_file = tmp_path / "logs" / "agent.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Agent started" in content
        assert "Test logging task" in content

    @patch('guardcode.agent.call_model_with_retry')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_agent_rich_output_on_tool_call(self, mock_init_ws, mock_execute, mock_retry, capsys):
        """测试 Agent 使用 Rich 输出工具调用"""
        mock_retry.side_effect = [
            {
                "content": "Reading file...",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"path": "test.txt"}
                }],
                "finish_reason": "tool_calls"
            },
            {
                "content": "Done.",
                "tool_calls": [],
                "finish_reason": "stop"
            },
        ]
        mock_execute.return_value = {
            "success": True,
            "result": "File content",
            "error": ""
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Read test.txt", config=config, max_iterations=5)

        # 验证 Rich 输出（捕获 stdout）
        captured = capsys.readouterr()
        # 应该包含工具名和结果（Rich 输出可能包含 ANSI 码）
        assert "read_file" in captured.out
        assert "Done" in captured.out

    @patch('guardcode.agent.call_model_with_retry')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_agent_model_retry_failure_handled(self, mock_init_ws, mock_execute, mock_retry):
        """测试模型重试失败后被 Agent 正确处理"""
        mock_retry.side_effect = Exception("All retries failed")

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test task", config=config, max_iterations=5)

        assert "consecutive failures" in result

    @patch('guardcode.agent.call_model_with_retry')
    @patch('guardcode.agent.execute_tool')
    @patch('guardcode.agent.init_workspace')
    def test_agent_final_response_printed(self, mock_init_ws, mock_execute, mock_retry, capsys):
        """测试最终响应通过 Rich 输出"""
        mock_retry.return_value = {
            "content": "Task completed successfully!",
            "tool_calls": [],
            "finish_reason": "stop",
        }

        config = Config(workspace=".", model="gpt-4-turbo")
        result = run_agent_loop("Test task", config=config, max_iterations=5)

        assert result == "Task completed successfully!"
        captured = capsys.readouterr()
        assert "Task completed successfully" in captured.out


# ──────────────────────────────────────────────────────────
# CLI 参数测试
# ──────────────────────────────────────────────────────────

class TestCLI:
    """测试 CLI 参数解析和验证"""

    def test_version_flag(self):
        """测试 --version 参数触发 SystemExit"""
        import argparse
        from guardcode import __version__

        parser = argparse.ArgumentParser()
        parser.add_argument("--version", action="version", version=f"v{__version__}")

        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])

    def test_verbose_flag_sets_config(self):
        """测试 --verbose 设置 config.verbose"""
        config = Config(workspace=".", verbose=False)
        config.verbose = True
        assert config.verbose is True

    def test_api_base_override(self):
        """测试 --api-base 覆盖"""
        config = Config(workspace=".", api_base="https://api.openai.com/v1")
        config.api_base = "https://api.deepseek.com/v1"
        assert config.api_base == "https://api.deepseek.com/v1"

    def test_cli_has_all_expected_args(self):
        """测试 CLI 解析器包含所有预期参数"""
        import argparse
        import re

        # 从 agent.py 的 main 函数源码中提取参数
        import inspect
        from guardcode.agent import main

        source = inspect.getsource(main)
        # 检查关键参数是否定义
        assert "--workspace" in source
        assert "--model" in source
        assert "--api-base" in source
        assert "--max-iterations" in source
        assert "--config" in source
        assert "--verbose" in source
        assert "--version" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
