"""
Tests for context manager (3.1).
"""

import json
import pytest
from guardcode.context.manager import estimate_context_size, should_compress


class TestEstimateContextSize:
    """Test estimate_context_size function."""

    def test_empty_list(self):
        """Empty message list should return 0."""
        assert estimate_context_size([]) == 0

    def test_single_message(self):
        """Single message size should match json.dumps length."""
        msg = {"role": "user", "content": "hello"}
        expected = len(json.dumps(msg, ensure_ascii=False))
        assert estimate_context_size([msg]) == expected

    def test_multiple_messages(self):
        """Multiple messages should sum up."""
        msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hi"},
        ]
        expected = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs)
        assert estimate_context_size(msgs) == expected

    def test_chinese_content(self):
        """Chinese characters should be counted correctly."""
        msg = {"role": "user", "content": "你好世界"}
        size = estimate_context_size([msg])
        # json.dumps with ensure_ascii=False keeps Chinese chars as-is
        assert size == len(json.dumps(msg, ensure_ascii=False))

    def test_tool_calls_in_message(self):
        """Messages with tool_calls should be counted."""
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call-1", "name": "read_file", "arguments": {"path": "test.py"}}
            ],
        }
        size = estimate_context_size([msg])
        assert size > 0

    def test_tool_result_message(self):
        """Tool result messages should be counted."""
        msg = {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": json.dumps({"success": True, "result": "file content"}),
        }
        size = estimate_context_size([msg])
        assert size > 0

    def test_large_content(self):
        """Large content should produce large size."""
        msg = {"role": "user", "content": "x" * 10000}
        size = estimate_context_size([msg])
        assert size >= 10000

    def test_returns_int(self):
        """Should return an integer."""
        msg = {"role": "user", "content": "hi"}
        result = estimate_context_size([msg])
        assert isinstance(result, int)


class TestShouldCompress:
    """Test should_compress function."""

    def test_empty_list(self):
        """Empty list should not need compression."""
        assert should_compress([]) is False

    def test_few_messages(self):
        """Few messages should not need compression."""
        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hi"},
        ]
        assert should_compress(msgs) is False

    def test_le_4_messages(self):
        """4 or fewer messages should not compress regardless of size."""
        # Even with huge content, 4 messages shouldn't compress
        msgs = [
            {"role": "system", "content": "x" * 50000},
            {"role": "user", "content": "x" * 50000},
            {"role": "assistant", "content": "x" * 50000},
            {"role": "user", "content": "x" * 50000},
        ]
        assert should_compress(msgs) is False

    def test_5_messages_small(self):
        """5 small messages should not compress."""
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
            {"role": "assistant", "content": "4"},
        ]
        assert should_compress(msgs) is False

    def test_exceeds_threshold(self):
        """Messages exceeding threshold should compress."""
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
            {"role": "assistant", "content": "x" * 200000},
        ]
        assert should_compress(msgs, threshold=100000) is True

    def test_custom_threshold(self):
        """Custom threshold should work."""
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
            {"role": "assistant", "content": "hello world"},
        ]
        # Very small threshold should trigger
        assert should_compress(msgs, threshold=10) is True
        # Large threshold should not
        assert should_compress(msgs, threshold=1000000) is False

    def test_boundary_threshold(self):
        """Exactly at threshold should not compress (uses >)."""
        msg_content = "x" * 100
        msgs = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
            {"role": "assistant", "content": msg_content},
        ]
        size = estimate_context_size(msgs)
        # size > threshold → True, size == threshold → False
        assert should_compress(msgs, threshold=size) is False
        assert should_compress(msgs, threshold=size - 1) is True
