"""
Tests for security module - risk classification
"""

import pytest
from guardcode.security import RiskLevel, classify_risk


class TestRiskClassification:
    """Test risk classification for various tool operations."""
    
    def test_read_operations_are_safe(self):
        """Read-only file operations should be classified as SAFE."""
        config = {}
        
        assert classify_risk("read_file", {"path": "test.txt"}, config) == RiskLevel.SAFE
        assert classify_risk("list_files", {"directory": "."}, config) == RiskLevel.SAFE
    
    def test_delete_operations_are_dangerous(self):
        """File deletion should always be classified as DANGEROUS."""
        config = {}
        
        assert classify_risk("delete_file", {"path": "test.txt"}, config) == RiskLevel.DANGEROUS
    
    def test_write_operations_are_safe_in_workspace(self):
        """Write operations within workspace should be SAFE."""
        config = {}
        
        assert classify_risk("write_file", {"path": "new.txt", "content": "test"}, config) == RiskLevel.SAFE
    
    def test_safe_commands_patterns(self):
        """Commands matching SAFE_PATTERNS should be classified as SAFE."""
        config = {}
        
        safe_commands = [
            "ls -la",
            "cat file.txt",
            "grep pattern file.txt",
            "git status",
            "git log",
            "git diff",
            "pwd",
            "echo hello",
            "python test.py",
            "python -m pytest",
            "pytest tests/",
            "pip list",
            "npm list",
        ]
        
        for command in safe_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.SAFE, f"Command '{command}' should be SAFE but got {result}"
    
    def test_dangerous_commands_patterns(self):
        """Commands matching DANGEROUS_PATTERNS should be classified as DANGEROUS."""
        config = {}
        
        dangerous_commands = [
            "rm file.txt",
            "rm -rf /tmp/*",
            "del file.txt",
            "sudo apt-get install package",
            "kill 1234",
            "pip install package",
            "npm install package",
            "git reset --hard HEAD",
            "git clean -fd",
            "chmod 777 file.txt",
            "curl -X POST http://example.com",
            "DROP TABLE users",
            "DELETE FROM users",
        ]
        
        for command in dangerous_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"Command '{command}' should be DANGEROUS but got {result}"
    
    def test_unknown_commands_are_dangerous(self):
        """Unknown commands should default to DANGEROUS (conservative)."""
        config = {}
        
        unknown_commands = [
            "some_unknown_tool --flag",
            "custom_script.sh",
            "mysterious_command",
        ]
        
        for command in unknown_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"Unknown command '{command}' should be DANGEROUS"
    
    def test_config_always_block(self):
        """Commands matching always_block patterns should be BLOCKED."""
        config = {
            "security": {
                "always_block": [
                    r"rm -rf /",
                    r"format\s+",
                    r"DROP DATABASE"
                ]
            }
        }
        
        blocked_commands = [
            "rm -rf /",
            "format c:",
            "DROP DATABASE production",
        ]
        
        for command in blocked_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.BLOCKED, f"Command '{command}' should be BLOCKED"
    
    def test_config_auto_approve(self):
        """Commands matching auto_approve patterns should be SAFE."""
        config = {
            "security": {
                "auto_approve": [
                    r"rm .*\.pyc$",
                    r"del .*\.tmp$",
                ]
            }
        }
        
        approved_commands = [
            "rm test.pyc",
            "rm cache/__pycache__/file.pyc",
            "del temp.tmp",
        ]
        
        for command in approved_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.SAFE, f"Command '{command}' should be auto-approved"
    
    def test_config_priority_order(self):
        """always_block should take priority over auto_approve."""
        config = {
            "security": {
                "always_block": [r"rm -rf"],
                "auto_approve": [r"rm .*"]
            }
        }
        
        # Should be blocked (always_block takes priority)
        assert classify_risk("run_command", {"command": "rm -rf temp"}, config) == RiskLevel.BLOCKED
        
        # Should be safe (matches auto_approve and not always_block)
        assert classify_risk("run_command", {"command": "rm temp.txt"}, config) == RiskLevel.SAFE
    
    def test_empty_config(self):
        """Should work correctly with empty config."""
        config = {}
        
        assert classify_risk("read_file", {"path": "test.txt"}, config) == RiskLevel.SAFE
        assert classify_risk("delete_file", {"path": "test.txt"}, config) == RiskLevel.DANGEROUS
        assert classify_risk("run_command", {"command": "rm file.txt"}, config) == RiskLevel.DANGEROUS
    
    def test_missing_security_section(self):
        """Should handle config without security section."""
        config = {"other_settings": {"key": "value"}}
        
        assert classify_risk("read_file", {"path": "test.txt"}, config) == RiskLevel.SAFE
        assert classify_risk("run_command", {"command": "rm file.txt"}, config) == RiskLevel.DANGEROUS
    
    def test_unknown_tool(self):
        """Unknown tools should default to DANGEROUS."""
        config = {}
        
        result = classify_risk("unknown_tool", {"arg": "value"}, config)
        assert result == RiskLevel.DANGEROUS
    
    def test_case_insensitive_sql_commands(self):
        """SQL dangerous commands should be detected case-insensitively."""
        config = {}
        
        sql_commands = [
            "DROP TABLE users",
            "drop table users",
            "DrOp TaBlE users",
            "DELETE FROM users WHERE id=1",
            "delete from users",
            "TRUNCATE TABLE logs",
            "truncate table logs",
        ]
        
        for command in sql_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"SQL command '{command}' should be DANGEROUS"
    
    def test_git_safe_vs_dangerous(self):
        """Test Git commands are properly classified."""
        config = {}
        
        # Safe git commands
        safe_git = [
            "git status",
            "git log --oneline",
            "git diff HEAD",
            "git show abc123",
            "git branch -a",
        ]
        
        for command in safe_git:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.SAFE, f"Git command '{command}' should be SAFE"
        
        # Dangerous git commands
        dangerous_git = [
            "git reset --hard HEAD",
            "git clean -fd",
            "git push origin main --force",
            "git branch -D feature-branch",
        ]
        
        for command in dangerous_git:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"Git command '{command}' should be DANGEROUS"
    
    def test_python_test_commands_are_safe(self):
        """Python test execution should be classified as SAFE."""
        config = {}
        
        test_commands = [
            "python test.py",
            "python3 test_module.py",
            "python -m pytest",
            "python -m pytest tests/",
            "pytest",
            "pytest tests/test_file.py",
            "python -m unittest",
        ]
        
        for command in test_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.SAFE, f"Test command '{command}' should be SAFE"
    
    def test_package_manager_read_only(self):
        """Package manager read-only operations should be SAFE."""
        config = {}
        
        safe_pm_commands = [
            "pip list",
            "pip show requests",
            "npm list",
            "npm ls",
        ]
        
        for command in safe_pm_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.SAFE, f"Package command '{command}' should be SAFE"
    
    def test_package_manager_install_uninstall(self):
        """Package installation/removal should be DANGEROUS."""
        config = {}
        
        dangerous_pm_commands = [
            "pip install requests",
            "pip uninstall numpy",
            "npm install express",
            "npm uninstall lodash",
            "apt-get install vim",
            "yum remove httpd",
        ]
        
        for command in dangerous_pm_commands:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"Package command '{command}' should be DANGEROUS"
    
    def test_file_overwrite_redirection(self):
        """Shell redirection that overwrites should be DANGEROUS."""
        config = {}
        
        dangerous_redirects = [
            "echo test > file.txt",
            "cat input.txt > output.txt",
            "ls > filelist.txt",
        ]
        
        for command in dangerous_redirects:
            result = classify_risk("run_command", {"command": command}, config)
            assert result == RiskLevel.DANGEROUS, f"Redirect command '{command}' should be DANGEROUS"


class TestRiskLevelEnum:
    """Test RiskLevel enumeration."""
    
    def test_risk_level_values(self):
        """Test RiskLevel enum has correct values."""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.DANGEROUS.value == "dangerous"
        assert RiskLevel.BLOCKED.value == "blocked"
    
    def test_risk_level_comparison(self):
        """Test RiskLevel enum comparison."""
        assert RiskLevel.SAFE == RiskLevel.SAFE
        assert RiskLevel.DANGEROUS == RiskLevel.DANGEROUS
        assert RiskLevel.BLOCKED == RiskLevel.BLOCKED
        assert RiskLevel.SAFE != RiskLevel.DANGEROUS
    
    def test_risk_level_members(self):
        """Test all expected RiskLevel members exist."""
        levels = [member.name for member in RiskLevel]
        assert "SAFE" in levels
        assert "DANGEROUS" in levels
        assert "BLOCKED" in levels
        assert len(levels) == 3
