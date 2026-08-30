"""
Tests for user confirmation module
"""

import pytest
from unittest.mock import patch, MagicMock
from guardcode.security import confirm_operation, format_blocked_message


class TestConfirmOperation:
    """Test user confirmation for dangerous operations."""
    
    @patch('builtins.input', return_value='y')
    def test_confirm_with_yes(self, mock_input):
        """User confirming with 'y' should return True."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is True
        mock_input.assert_called_once()
    
    @patch('builtins.input', return_value='yes')
    def test_confirm_with_yes_full(self, mock_input):
        """User confirming with 'yes' should return True."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is True
        mock_input.assert_called_once()
    
    @patch('builtins.input', return_value='n')
    def test_reject_with_no(self, mock_input):
        """User rejecting with 'n' should return False."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is False
        mock_input.assert_called_once()
    
    @patch('builtins.input', return_value='no')
    def test_reject_with_no_full(self, mock_input):
        """User rejecting with 'no' should return False."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is False
        mock_input.assert_called_once()
    
    @patch('builtins.input', side_effect=['invalid', 'maybe', 'y'])
    def test_invalid_input_retry(self, mock_input):
        """Invalid input should prompt again until valid input."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is True
        assert mock_input.call_count == 3
    
    @patch('builtins.input', side_effect=['Y'])
    def test_case_insensitive_yes(self, mock_input):
        """Input should be case insensitive."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is True
    
    @patch('builtins.input', side_effect=['N'])
    def test_case_insensitive_no(self, mock_input):
        """Input should be case insensitive."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is False
    
    @patch('builtins.input', side_effect=EOFError())
    def test_eof_handling(self, mock_input):
        """EOF should be handled gracefully and return False."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is False
    
    @patch('builtins.input', side_effect=KeyboardInterrupt())
    def test_keyboard_interrupt_handling(self, mock_input):
        """Keyboard interrupt should be handled gracefully and return False."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is False
    
    @patch('builtins.input', return_value='y')
    def test_confirm_run_command(self, mock_input):
        """Test confirmation for run_command tool."""
        result = confirm_operation("run_command", {"command": "rm -rf temp"})
        assert result is True
    
    @patch('builtins.input', return_value='y')
    def test_confirm_with_multiple_args(self, mock_input):
        """Test confirmation with multiple arguments."""
        result = confirm_operation(
            "write_file",
            {"path": "test.txt", "content": "Hello World"}
        )
        assert result is True
    
    @patch('builtins.input', return_value='y')
    def test_confirm_with_long_content(self, mock_input):
        """Test confirmation with long content (should be truncated)."""
        long_content = "x" * 200
        result = confirm_operation(
            "write_file",
            {"path": "test.txt", "content": long_content}
        )
        assert result is True
    
    @patch('builtins.input', return_value='y')
    def test_confirm_with_dict_args(self, mock_input):
        """Test confirmation with dictionary arguments."""
        result = confirm_operation(
            "some_tool",
            {"config": {"key1": "value1", "key2": "value2"}}
        )
        assert result is True
    
    @patch('builtins.input', return_value='y')
    def test_confirm_with_list_args(self, mock_input):
        """Test confirmation with list arguments."""
        result = confirm_operation(
            "some_tool",
            {"files": ["file1.txt", "file2.txt", "file3.txt"]}
        )
        assert result is True
    
    @patch('builtins.input', return_value='  y  ')
    def test_whitespace_handling(self, mock_input):
        """Input with whitespace should be stripped."""
        result = confirm_operation("delete_file", {"path": "test.txt"})
        assert result is True


class TestFormatBlockedMessage:
    """Test formatting of blocked operation messages."""
    
    def test_basic_blocked_message(self):
        """Test basic blocked message formatting."""
        message = format_blocked_message("delete_file", {"path": "test.txt"})
        
        assert "OPERATION BLOCKED" in message
        assert "delete_file" in message
        assert "test.txt" in message
        assert "security" in message.lower()
    
    def test_blocked_message_with_reason(self):
        """Test blocked message with custom reason."""
        message = format_blocked_message(
            "run_command",
            {"command": "rm -rf /"},
            reason="Attempting to delete root directory"
        )
        
        assert "OPERATION BLOCKED" in message
        assert "run_command" in message
        assert "rm -rf /" in message
        assert "Attempting to delete root directory" in message
    
    def test_blocked_message_with_long_arg(self):
        """Test blocked message with long argument (should be truncated)."""
        long_command = "x" * 200
        message = format_blocked_message(
            "run_command",
            {"command": long_command}
        )
        
        assert "OPERATION BLOCKED" in message
        assert "run_command" in message
        assert "..." in message  # Should be truncated
    
    def test_blocked_message_with_multiple_args(self):
        """Test blocked message with multiple arguments."""
        message = format_blocked_message(
            "some_tool",
            {"arg1": "value1", "arg2": "value2", "arg3": "value3"}
        )
        
        assert "OPERATION BLOCKED" in message
        assert "arg1" in message
        assert "arg2" in message
        assert "arg3" in message
        assert "value1" in message
        assert "value2" in message
        assert "value3" in message
    
    def test_blocked_message_format(self):
        """Test blocked message has proper formatting."""
        message = format_blocked_message("delete_file", {"path": "test.txt"})
        
        # Should have separators
        assert "=" * 60 in message
        # Should have proper sections
        assert "Tool:" in message
        assert "Arguments:" in message
        assert "Reason:" in message
