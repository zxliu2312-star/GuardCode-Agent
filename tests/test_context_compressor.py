"""
Tests for context compressor (3.2 逐轮压缩器).

Tests cover:
- compress_tool_call: large arguments compressed, small preserved
- compress_tool_result: large results compressed, status preserved
- compress_tool_message: assistant/tool messages dispatched correctly
- compress_round: recent rounds kept, earlier compressed, idempotent
- truncate_compressed: fallback truncation
"""

import json
import pytest
from guardcode.context.compressor import (
    compress_tool_call,
    compress_tool_result,
    compress_tool_message,
    compress_round,
    truncate_compressed,
    _is_already_compressed,
    MAX_ARG_LENGTH,
    MAX_RESULT_LENGTH,
)


# ── Helper: build OpenAI-format messages ───────────────────


def make_assistant_with_tool_calls(
    tool_calls: list[dict],
    content: str | None = None,
) -> dict:
    """Build an assistant message with tool_calls in OpenAI format."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                },
            }
            for tc in tool_calls
        ],
    }


def make_tool_result(tool_call_id: str, result: dict) -> dict:
    """Build a tool result message in OpenAI format."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }


# ── compress_tool_call ────────────────────────────────────


class TestCompressToolCall:
    """Test compress_tool_call function."""

    def test_small_args_preserved(self):
        """Small arguments should be preserved unchanged."""
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"path": "src/main.py"}),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])
        assert args["path"] == "src/main.py"

    def test_large_content_compressed(self):
        """Large content argument should be replaced with compression marker."""
        large_content = "x" * 5000
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps(
                    {"path": "app.py", "content": large_content}
                ),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])

        # path should be preserved
        assert args["path"] == "app.py"
        # content should be compressed
        assert "[compressed:" in args["content"]
        assert str(5000) in args["content"]
        # original content should NOT be in the result
        assert large_content not in json.dumps(result)

    def test_boundary_length(self):
        """Arguments at exactly MAX_ARG_LENGTH should NOT be compressed."""
        content = "x" * MAX_ARG_LENGTH
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps({"path": "f.py", "content": content}),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])
        assert args["content"] == content  # not compressed

    def test_just_over_boundary(self):
        """Arguments just over MAX_ARG_LENGTH should be compressed."""
        content = "x" * (MAX_ARG_LENGTH + 1)
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps({"path": "f.py", "content": content}),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])
        assert "[compressed:" in args["content"]

    def test_non_string_args_preserved(self):
        """Non-string arguments (int, bool) should be preserved."""
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "run_command",
                "arguments": json.dumps(
                    {"command": "pytest", "timeout": 30}
                ),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])
        assert args["command"] == "pytest"
        assert args["timeout"] == 30

    def test_invalid_json_arguments(self):
        """Invalid JSON arguments should return original tool_call."""
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": "not valid json{{{",
            },
        }
        result = compress_tool_call(tc)
        # Should return original unchanged
        assert result == tc

    def test_tool_name_preserved(self):
        """Tool name should always be preserved."""
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "delete_file",
                "arguments": json.dumps({"path": "temp.txt"}),
            },
        }
        result = compress_tool_call(tc)
        assert result["function"]["name"] == "delete_file"

    def test_id_preserved(self):
        """Tool call ID should be preserved."""
        tc = {
            "id": "call-abc-123",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"path": "test.py"}),
            },
        }
        result = compress_tool_call(tc)
        assert result["id"] == "call-abc-123"

    def test_multiple_args_some_compressed(self):
        """Multiple args: only large ones compressed."""
        large = "y" * 1000
        tc = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps(
                    {"path": "big.py", "content": large, "mode": "overwrite"}
                ),
            },
        }
        result = compress_tool_call(tc)
        args = json.loads(result["function"]["arguments"])
        assert args["path"] == "big.py"
        assert "[compressed:" in args["content"]
        assert args["mode"] == "overwrite"


# ── compress_tool_result ──────────────────────────────────


class TestCompressToolResult:
    """Test compress_tool_result function."""

    def test_small_result_preserved(self):
        """Small result should be preserved."""
        msg = make_tool_result("call-1", {"success": True, "result": "OK"})
        result = compress_tool_result(msg)
        content = json.loads(result["content"])
        assert content["success"] is True
        assert content["result"] == "OK"

    def test_large_result_compressed(self):
        """Large result content should be compressed."""
        large_result = "x" * 5000
        msg = make_tool_result(
            "call-1",
            {"success": True, "result": large_result},
        )
        result = compress_tool_result(msg)
        content = json.loads(result["content"])
        assert content["success"] is True
        assert "[compressed:" in content["result"]
        assert str(5000) in content["result"]
        # original should not be in the result
        assert large_result not in result["content"]

    def test_error_preserved(self):
        """Error status and message should be preserved."""
        msg = make_tool_result(
            "call-1",
            {"success": False, "error": "File not found: test.py"},
        )
        result = compress_tool_result(msg)
        content = json.loads(result["content"])
        assert content["success"] is False
        assert content["error"] == "File not found: test.py"

    def test_boundary_result(self):
        """Result at exactly MAX_RESULT_LENGTH should NOT be compressed."""
        result_str = "x" * MAX_RESULT_LENGTH
        msg = make_tool_result(
            "call-1",
            {"success": True, "result": result_str},
        )
        result = compress_tool_result(msg)
        content = json.loads(result["content"])
        assert content["result"] == result_str

    def test_just_over_boundary_result(self):
        """Result just over MAX_RESULT_LENGTH should be compressed."""
        result_str = "x" * (MAX_RESULT_LENGTH + 1)
        msg = make_tool_result(
            "call-1",
            {"success": True, "result": result_str},
        )
        result = compress_tool_result(msg)
        content = json.loads(result["content"])
        assert "[compressed:" in content["result"]

    def test_tool_call_id_preserved(self):
        """tool_call_id should be preserved."""
        msg = make_tool_result(
            "call-xyz",
            {"success": True, "result": "done"},
        )
        result = compress_tool_result(msg)
        assert result["tool_call_id"] == "call-xyz"

    def test_non_json_content(self):
        """Non-JSON content should be truncated as string."""
        msg = {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": "x" * 5000,  # raw string, not JSON
        }
        result = compress_tool_result(msg)
        assert "[compressed:" in result["content"]
        assert len(result["content"]) < 5000

    def test_non_json_short_content(self):
        """Short non-JSON content should be preserved."""
        msg = {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": "short text",
        }
        result = compress_tool_result(msg)
        assert result["content"] == "short text"


# ── compress_tool_message ──────────────────────────────────


class TestCompressToolMessage:
    """Test compress_tool_message function."""

    def test_assistant_with_tool_calls(self):
        """Assistant message with tool_calls should have args compressed."""
        large = "x" * 1000
        msg = make_assistant_with_tool_calls(
            [{"id": "call-1", "name": "write_file",
              "arguments": {"path": "f.py", "content": large}}],
            content="Writing file",
        )
        result = compress_tool_message(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "Writing file"  # content preserved
        # tool_calls should be compressed
        args = json.loads(result["tool_calls"][0]["function"]["arguments"])
        assert "[compressed:" in args["content"]

    def test_tool_message(self):
        """Tool message should have result compressed."""
        large = "x" * 1000
        msg = make_tool_result(
            "call-1",
            {"success": True, "result": large},
        )
        result = compress_tool_message(msg)
        content = json.loads(result["content"])
        assert "[compressed:" in content["result"]

    def test_plain_assistant_not_compressed(self):
        """Assistant message without tool_calls should be unchanged."""
        msg = {"role": "assistant", "content": "Task completed."}
        result = compress_tool_message(msg)
        assert result == msg

    def test_system_message_not_compressed(self):
        """System message should be unchanged."""
        msg = {"role": "system", "content": "You are a helpful assistant."}
        result = compress_tool_message(msg)
        assert result == msg

    def test_user_message_not_compressed(self):
        """User message should be unchanged."""
        msg = {"role": "user", "content": "Fix the bug in main.py"}
        result = compress_tool_message(msg)
        assert result == msg

    def test_already_compressed_skipped(self):
        """Already compressed messages should not be re-compressed."""
        large = "x" * 1000
        msg = make_assistant_with_tool_calls(
            [{"id": "call-1", "name": "write_file",
              "arguments": {"path": "f.py", "content": large}}],
        )
        # First compression
        first = compress_tool_message(msg)
        # Second compression should be a no-op
        second = compress_tool_message(first)
        # The content should be the same (not double-compressed)
        assert first == second

    def test_multiple_tool_calls_in_one_message(self):
        """Multiple tool_calls in one assistant message should all be compressed."""
        large = "x" * 1000
        msg = make_assistant_with_tool_calls([
            {"id": "call-1", "name": "write_file",
             "arguments": {"path": "a.py", "content": large}},
            {"id": "call-2", "name": "write_file",
             "arguments": {"path": "b.py", "content": large}},
        ])
        result = compress_tool_message(msg)
        for tc in result["tool_calls"]:
            args = json.loads(tc["function"]["arguments"])
            assert "[compressed:" in args["content"]


# ── _is_already_compressed ────────────────────────────────


class TestIsAlreadyCompressed:
    """Test _is_already_compressed detection function."""

    def test_uncompressed_assistant(self):
        """Uncompressed assistant message should return False."""
        msg = make_assistant_with_tool_calls(
            [{"id": "call-1", "name": "read_file",
              "arguments": {"path": "test.py"}}],
        )
        assert _is_already_compressed(msg) is False

    def test_compressed_assistant(self):
        """Compressed assistant message should return True."""
        large = "x" * 1000
        msg = make_assistant_with_tool_calls(
            [{"id": "call-1", "name": "write_file",
              "arguments": {"path": "f.py", "content": large}}],
        )
        compressed = compress_tool_message(msg)
        assert _is_already_compressed(compressed) is True

    def test_compressed_tool(self):
        """Compressed tool message should return True."""
        large = "x" * 1000
        msg = make_tool_result(
            "call-1",
            {"success": True, "result": large},
        )
        compressed = compress_tool_result(msg)
        assert _is_already_compressed(compressed) is True

    def test_plain_message(self):
        """Non-tool messages should return False."""
        assert _is_already_compressed(
            {"role": "system", "content": "hello"}
        ) is False
        assert _is_already_compressed(
            {"role": "user", "content": "hi"}
        ) is False
        assert _is_already_compressed(
            {"role": "assistant", "content": "done"}
        ) is False


# ── compress_round ────────────────────────────────────────


class TestCompressRound:
    """Test compress_round function."""

    def test_not_enough_rounds(self):
        """Fewer rounds than keep_recent should return messages unchanged."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "read_file",
                  "arguments": {"path": "f.py"}}],
            ),
            make_tool_result("c1", {"success": True, "result": "content"}),
        ]
        result = compress_round(messages, keep_recent=2)
        # Only 1 round, keep_recent=2 → no compression
        assert len(result) == len(messages)
        # Content should be unchanged
        assert result == messages

    def test_exactly_keep_recent_rounds(self):
        """Exactly keep_recent rounds should not compress."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "read_file",
                  "arguments": {"path": "f.py"}}],
            ),
            make_tool_result("c1", {"success": True, "result": "content"}),
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "read_file",
                  "arguments": {"path": "g.py"}}],
            ),
            make_tool_result("c2", {"success": True, "result": "content2"}),
        ]
        result = compress_round(messages, keep_recent=2)
        # 2 rounds, keep_recent=2 → no compression
        assert result == messages

    def test_compresses_earlier_rounds(self):
        """Earlier rounds should be compressed when > keep_recent rounds."""
        large = "x" * 1000
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            # Round 1 (should be compressed)
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "write_file",
                  "arguments": {"path": "a.py", "content": large}}],
            ),
            make_tool_result("c1", {"success": True, "result": large}),
            # Round 2 (should be compressed)
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "write_file",
                  "arguments": {"path": "b.py", "content": large}}],
            ),
            make_tool_result("c2", {"success": True, "result": large}),
            # Round 3 (should be kept - most recent)
            make_assistant_with_tool_calls(
                [{"id": "c3", "name": "write_file",
                  "arguments": {"path": "c.py", "content": large}}],
            ),
            make_tool_result("c3", {"success": True, "result": large}),
        ]
        result = compress_round(messages, keep_recent=2)

        # Round 1 (index 2-3) should be compressed
        r1_assistant_args = json.loads(
            result[2]["tool_calls"][0]["function"]["arguments"]
        )
        assert "[compressed:" in r1_assistant_args["content"]
        r1_tool_content = json.loads(result[3]["content"])
        assert "[compressed:" in r1_tool_content["result"]

        # Round 2 (index 4-5) should be UNCOMPRESSED (within keep_recent=2)
        r2_assistant_args = json.loads(
            result[4]["tool_calls"][0]["function"]["arguments"]
        )
        assert r2_assistant_args["content"] == large  # original content

        # Round 3 (index 6-7) should be UNCOMPRESSED
        r3_assistant_args = json.loads(
            result[6]["tool_calls"][0]["function"]["arguments"]
        )
        assert r3_assistant_args["content"] == large  # original content
        r3_tool_content = json.loads(result[7]["content"])
        assert r3_tool_content["result"] == large  # original result

    def test_non_tool_messages_preserved(self):
        """Non-tool messages between rounds should be preserved."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            # Round 1
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "read_file",
                  "arguments": {"path": "f.py"}}],
            ),
            make_tool_result("c1", {"success": True, "result": "ok"}),
            # Plain assistant message (no tool_calls)
            {"role": "assistant", "content": "I found an issue."},
            # Round 2
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "write_file",
                  "arguments": {"path": "g.py", "content": "x" * 500}}],
            ),
            make_tool_result("c2", {"success": True, "result": "written"}),
            # Round 3
            make_assistant_with_tool_calls(
                [{"id": "c3", "name": "read_file",
                  "arguments": {"path": "h.py"}}],
            ),
            make_tool_result("c3", {"success": True, "result": "ok2"}),
        ]
        result = compress_round(messages, keep_recent=2)

        # The plain assistant message (index 4) should be preserved
        assert result[4] == {"role": "assistant", "content": "I found an issue."}

    def test_idempotent(self):
        """Running compress_round twice should not double-compress."""
        large = "x" * 1000
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "write_file",
                  "arguments": {"path": "a.py", "content": large}}],
            ),
            make_tool_result("c1", {"success": True, "result": large}),
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "write_file",
                  "arguments": {"path": "b.py", "content": large}}],
            ),
            make_tool_result("c2", {"success": True, "result": large}),
            make_assistant_with_tool_calls(
                [{"id": "c3", "name": "write_file",
                  "arguments": {"path": "c.py", "content": large}}],
            ),
            make_tool_result("c3", {"success": True, "result": large}),
        ]
        first_pass = compress_round(messages, keep_recent=2)
        second_pass = compress_round(first_pass, keep_recent=2)
        # Second pass should not change already-compressed messages
        assert first_pass == second_pass

    def test_empty_messages(self):
        """Empty message list should return empty list."""
        assert compress_round([]) == []

    def test_only_system_user(self):
        """Only system + user messages should return unchanged."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
        ]
        result = compress_round(messages, keep_recent=2)
        assert result == messages

    def test_keep_recent_one(self):
        """keep_recent=1 should only keep the last round."""
        large = "x" * 1000
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            # Round 1 (should be compressed)
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "write_file",
                  "arguments": {"path": "a.py", "content": large}}],
            ),
            make_tool_result("c1", {"success": True, "result": large}),
            # Round 2 (should be kept - most recent)
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "write_file",
                  "arguments": {"path": "b.py", "content": large}}],
            ),
            make_tool_result("c2", {"success": True, "result": large}),
        ]
        result = compress_round(messages, keep_recent=1)

        # Round 1 should be compressed
        r1_args = json.loads(
            result[2]["tool_calls"][0]["function"]["arguments"]
        )
        assert "[compressed:" in r1_args["content"]

        # Round 2 should be uncompressed
        r2_args = json.loads(
            result[4]["tool_calls"][0]["function"]["arguments"]
        )
        assert r2_args["content"] == large

    def test_returns_new_list(self):
        """compress_round should return a new list, not modify the original."""
        large = "x" * 1000
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            make_assistant_with_tool_calls(
                [{"id": "c1", "name": "write_file",
                  "arguments": {"path": "a.py", "content": large}}],
            ),
            make_tool_result("c1", {"success": True, "result": large}),
            make_assistant_with_tool_calls(
                [{"id": "c2", "name": "write_file",
                  "arguments": {"path": "b.py", "content": large}}],
            ),
            make_tool_result("c2", {"success": True, "result": large}),
            make_assistant_with_tool_calls(
                [{"id": "c3", "name": "write_file",
                  "arguments": {"path": "c.py", "content": large}}],
            ),
            make_tool_result("c3", {"success": True, "result": large}),
        ]
        original_json = json.dumps(messages, ensure_ascii=False, default=str)
        _ = compress_round(messages, keep_recent=2)
        # Original should be unchanged
        assert json.dumps(messages, ensure_ascii=False, default=str) == original_json


# ── truncate_compressed ───────────────────────────────────


class TestTruncateCompressed:
    """Test truncate_compressed fallback function."""

    def test_short_messages_unchanged(self):
        """Short message lists should not be truncated."""
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "done"},
        ]
        result = truncate_compressed(messages, keep_recent=5)
        assert result == messages

    def test_truncates_middle(self):
        """Long message lists should have middle truncated."""
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
        ]
        # Add 20 middle messages
        for i in range(20):
            messages.append(
                {"role": "assistant", "content": f"message {i}"}
            )
        # Add 3 recent messages
        recent = [
            {"role": "assistant", "content": "recent1"},
            {"role": "assistant", "content": "recent2"},
            {"role": "assistant", "content": "recent3"},
        ]
        messages.extend(recent)

        result = truncate_compressed(messages, keep_recent=3)

        # Should have: 2 permanent + 1 marker + 3 recent = 6
        assert len(result) == 6
        assert result[0] == {"role": "system", "content": "sys"}
        assert result[1] == {"role": "user", "content": "task"}
        assert "truncated" in result[2]["content"].lower()
        assert result[3:] == recent

    def test_marker_contains_count(self):
        """Truncation marker should contain the count of omitted messages."""
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
        ]
        for i in range(10):
            messages.append({"role": "assistant", "content": f"msg {i}"})
        messages.extend([
            {"role": "assistant", "content": "recent1"},
            {"role": "assistant", "content": "recent2"},
        ])

        result = truncate_compressed(messages, keep_recent=2)
        # 10 middle messages omitted
        assert "10" in result[2]["content"]

    def test_empty_messages(self):
        """Empty message list should return empty list."""
        assert truncate_compressed([]) == []
