"""
Tests for code static scanner (2.5) and write_file integration (2.6).
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from guardcode.security.code_scanner import (
    CODE_RISK_PATTERNS,
    scan_python_code,
    format_scan_results,
)
from guardcode.tools import file_tools  # noqa: F401 – ensure tools registered
from guardcode.tools.base import execute_tool
from guardcode.workspace import init_workspace, get_workspace


# ── 2.5 code_scanner 单元测试 ──────────────────────────────


class TestScanPythonCode:
    """Test scan_python_code function."""

    def test_clean_code_no_risks(self):
        """Clean code should return empty list."""
        code = "x = 1\ny = 2\nprint(x + y)\n"
        assert scan_python_code(code) == []

    def test_detect_eval(self):
        """Should detect eval()."""
        code = "result = eval(user_input)\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        assert risks[0]["pattern"] == "eval"
        assert risks[0]["line"] == 1

    def test_detect_exec(self):
        """Should detect exec()."""
        code = "exec(\"print('hello')\")\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        assert risks[0]["pattern"] == "exec"

    def test_detect_os_system(self):
        """Should detect os.system()."""
        code = "import os\nos.system('rm -rf /')\n"
        risks = scan_python_code(code)
        assert any(r["pattern"] == "os.system" for r in risks)

    def test_detect_subprocess_shell_true(self):
        """Should detect subprocess with shell=True."""
        code = "import subprocess\nsubprocess.run(cmd, shell=True)\n"
        risks = scan_python_code(code)
        assert any(r["pattern"] == "subprocess.shell_true" for r in risks)

    def test_detect_pickle(self):
        """Should detect pickle.loads."""
        code = "import pickle\ndata = pickle.loads(raw)\n"
        risks = scan_python_code(code)
        assert any(r["pattern"] == "pickle.loads" for r in risks)

    def test_detect_hardcoded_password(self):
        """Should detect hardcoded password."""
        code = 'password = "my_secret_123"\n'
        risks = scan_python_code(code)
        assert any(r["pattern"] == "hardcoded_password" for r in risks)

    def test_detect_sql_fstring(self):
        """Should detect SQL injection via f-string."""
        code = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        risks = scan_python_code(code)
        assert any(r["pattern"] == "sql_fstring" for r in risks)

    def test_detect_multiple_risks(self):
        """Should detect multiple risks in one file."""
        code = (
            "import os\n"
            "os.system('ls')\n"
            "result = eval(input())\n"
        )
        risks = scan_python_code(code)
        assert len(risks) == 2
        patterns = [r["pattern"] for r in risks]
        assert "os.system" in patterns
        assert "eval" in patterns

    def test_line_numbers_correct(self):
        """Line numbers should be 1-based and accurate."""
        code = "x = 1\ny = 2\neval('x')\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        assert risks[0]["line"] == 3

    def test_line_numbers_multiline(self):
        """Line numbers should be correct across multiple lines."""
        code = "x = 1\ny = 2\neval('x')\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        assert risks[0]["line"] == 3

    def test_comment_lines_skipped(self):
        """Comment lines should be skipped."""
        code = "# eval('test')\nx = 1\n"
        risks = scan_python_code(code)
        assert len(risks) == 0

    def test_inline_comment_not_skipped(self):
        """Code with inline comment should still be detected."""
        code = "eval('x')  # dangerous\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        assert risks[0]["pattern"] == "eval"

    def test_empty_content(self):
        """Empty string should return empty list."""
        assert scan_python_code("") == []

    def test_risk_dict_format(self):
        """Each risk should have pattern, line, and content keys."""
        code = "eval('x')\n"
        risks = scan_python_code(code)
        assert len(risks) == 1
        risk = risks[0]
        assert "pattern" in risk
        assert "line" in risk
        assert "content" in risk
        assert isinstance(risk["line"], int)
        assert isinstance(risk["pattern"], str)
        assert isinstance(risk["content"], str)

    def test_verify_false_detected(self):
        """Should detect requests verify=False."""
        code = "requests.get(url, verify=False)\n"
        risks = scan_python_code(code)
        assert any(r["pattern"] == "requests_verify_false" for r in risks)


class TestFormatScanResults:
    """Test format_scan_results function."""

    def test_empty_risks(self):
        """Empty risk list should return empty string."""
        assert format_scan_results([]) == ""

    def test_format_output(self):
        """Should format risks into readable text."""
        risks = [
            {"pattern": "eval", "line": 3, "content": "eval(user_input)"},
            {"pattern": "exec", "line": 5, "content": "exec(code)"},
        ]
        result = format_scan_results(risks)
        assert "2" in result  # count
        assert "eval" in result
        assert "exec" in result
        assert "Line 3" in result
        assert "Line 5" in result


# ── 2.6 write_file 集成测试 ─────────────────────────────────


class TestWriteFileSecurityIntegration:
    """Test that write_file integrates code scanning."""

    @pytest.fixture
    def workspace(self, tmp_path):
        """Set up a temporary workspace."""
        init_workspace(str(tmp_path))
        return tmp_path

    def test_clean_py_file_writes_without_prompt(self, workspace):
        """Clean .py file should write without prompting."""
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "clean.py", "content": "x = 1\nprint(x)\n"},
            )
            mock_input.assert_not_called()
            assert result["success"] is True

    def test_risky_py_file_prompts_and_aborts(self, workspace):
        """Risky .py file should prompt and abort if user says 'a'."""
        with patch('builtins.input', return_value='a') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "bad.py", "content": "eval('x')\n"},
            )
            mock_input.assert_called_once()
            assert result["success"] is False
            assert "aborted" in result["error"].lower()

    def test_risky_py_file_prompts_and_continues(self, workspace):
        """Risky .py file should prompt and write if user says 'c'."""
        with patch('builtins.input', return_value='c') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "risky.py", "content": "eval('x')\n"},
            )
            mock_input.assert_called_once()
            assert result["success"] is True
            # Verify file was actually written
            assert (workspace / "risky.py").read_text() == "eval('x')\n"

    def test_non_py_file_no_scan(self, workspace):
        """Non-.py files should not be scanned."""
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "script.sh", "content": "eval('x')\nos.system('rm')\n"},
            )
            mock_input.assert_not_called()
            assert result["success"] is True

    def test_txt_file_no_scan(self, workspace):
        """.txt files should not be scanned."""
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "write_file",
                {"path": "notes.txt", "content": "eval('x')\n"},
            )
            mock_input.assert_not_called()
            assert result["success"] is True

    def test_aborted_file_not_written(self, workspace):
        """If user aborts, file should not be created."""
        with patch('builtins.input', return_value='a'):
            execute_tool(
                "write_file",
                {"path": "aborted.py", "content": "eval('x')\n"},
            )
            assert not (workspace / "aborted.py").exists()

    def test_multiple_risks_all_shown(self, workspace):
        """Multiple risks should all be shown in the prompt."""
        with patch('builtins.input', return_value='a') as mock_input:
            result = execute_tool(
                "write_file",
                {
                    "path": "multi.py",
                    "content": "import os\nos.system('ls')\neval('x')\n",
                },
            )
            assert result["success"] is False
            # Check that the prompt was called
            mock_input.assert_called_once()

    def test_clean_py_with_subprocess_no_shell(self, workspace):
        """subprocess without shell=True should not trigger."""
        with patch('builtins.input') as mock_input:
            result = execute_tool(
                "write_file",
                {
                    "path": "safe_sub.py",
                    "content": "import subprocess\nsubprocess.run(['ls', '-l'])\n",
                },
            )
            mock_input.assert_not_called()
            assert result["success"] is True
