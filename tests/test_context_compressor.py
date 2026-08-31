"""
测试上下文压缩器

覆盖 Level 1 规则压缩的所有规则：
- 写后失效（Write Invalidation）
- 按需重读（Lazy Re-reading）
- 压缩大型 tool_calls
- 工作集保留
- 幂等性
- compress_history 分区逻辑
"""

import json
import pytest

from guardcode.context.compressor import (
    compress_history,
    _find_modified_paths,
    _invalidate_outdated_reads,
    _compress_large_results,
    _compress_tool_call_arguments,
)


# ──────────────────────────────────────────────────────────
# 辅助函数：构造测试消息
# ──────────────────────────────────────────────────────────

def make_tool_msg(
    tool_call_id: str,
    tool_name: str,
    result: dict,
    path: str = "",
) -> dict:
    """构造 tool 消息（含 _tool_name 和 _path 元信息）"""
    content = result.copy()
    content["_tool_name"] = tool_name
    if path:
        content["_path"] = path
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(content, ensure_ascii=False),
    }


def make_assistant_msg(
    content: str = "",
    tool_calls: list[dict] | None = None,
) -> dict:
    """构造 assistant 消息"""
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def make_tool_call(
    call_id: str,
    name: str,
    arguments: dict,
) -> dict:
    """构造 tool_call（OpenAI 格式）"""
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def make_system_and_task() -> list[dict]:
    """构造 permanent 区（system + first user）"""
    return [
        {"role": "system", "content": "You are GuardCode Agent."},
        {"role": "user", "content": "Fix the bug in main.py"},
    ]


# ──────────────────────────────────────────────────────────
# 测试 _find_modified_paths
# ──────────────────────────────────────────────────────────

class TestFindModifiedPaths:
    """测试找出被修改过的路径"""

    def test_finds_write_file_paths(self):
        """write_file 成功的路径应被收集"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "a", "error": ""}, "src/a.py"),
            make_tool_msg("2", "write_file", {"success": True, "result": "wrote", "error": ""}, "src/b.py"),
            make_tool_msg("3", "write_file", {"success": True, "result": "wrote", "error": ""}, "src/c.py"),
        ]
        result = _find_modified_paths(messages)
        assert result == {"src/b.py", "src/c.py"}

    def test_finds_delete_file_paths(self):
        """delete_file 成功的路径应被收集"""
        messages = [
            make_tool_msg("1", "delete_file", {"success": True, "result": "deleted", "error": ""}, "old.py"),
        ]
        result = _find_modified_paths(messages)
        assert result == {"old.py"}

    def test_ignores_failed_writes(self):
        """失败的 write_file 不应被收集"""
        messages = [
            make_tool_msg("1", "write_file", {"success": False, "result": "", "error": "denied"}, "fail.py"),
        ]
        result = _find_modified_paths(messages)
        assert result == set()

    def test_ignores_read_file(self):
        """read_file 不应被收集"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "content", "error": ""}, "src/a.py"),
        ]
        result = _find_modified_paths(messages)
        assert result == set()

    def test_ignores_non_tool_messages(self):
        """非 tool 消息应被跳过"""
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "task"},
            make_assistant_msg("thinking"),
        ]
        result = _find_modified_paths(messages)
        assert result == set()

    def test_handles_malformed_content(self):
        """content 不是合法 JSON 时应跳过，不崩溃"""
        messages = [
            {"role": "tool", "tool_call_id": "1", "content": "not json"},
        ]
        result = _find_modified_paths(messages)
        assert result == set()

    def test_path_normalization(self):
        """./src/main.py 和 src/main.py 应被视为同一路径"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "x", "error": ""}, "./src/main.py"),
            make_tool_msg("2", "write_file", {"success": True, "result": "wrote", "error": ""}, "src/main.py"),
        ]
        result = _find_modified_paths(messages)
        # _path 在 _format_tool_result 中已规范化为 "src/main.py"
        assert "src/main.py" in result


# ──────────────────────────────────────────────────────────
# 测试 _invalidate_outdated_reads
# ──────────────────────────────────────────────────────────

class TestInvalidateOutdatedReads:
    """测试写后失效"""

    def test_invalidates_read_after_write(self):
        """write_file 后，旧 read_file 结果应被标记过期"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "old content", "error": ""}, "main.py"),
        ]
        modified = {"main.py"}
        result = _invalidate_outdated_reads(messages, modified)

        content = json.loads(result[0]["content"])
        assert content["compressed"] is True
        assert "modified later" in content["result"]
        assert content["_path"] == "main.py"

    def test_invalidates_read_after_delete(self):
        """delete_file 后，旧 read_file 结果应被标记过期"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "content", "error": ""}, "temp.py"),
        ]
        modified = {"temp.py"}
        result = _invalidate_outdated_reads(messages, modified)

        content = json.loads(result[0]["content"])
        assert content["compressed"] is True
        assert "modified later" in content["result"]

    def test_does_not_invalidate_unmodified_files(self):
        """未被修改的文件的 read_file 结果应保持不变"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "content", "error": ""}, "other.py"),
        ]
        modified = {"main.py"}
        result = _invalidate_outdated_reads(messages, modified)

        content = json.loads(result[0]["content"])
        assert "compressed" not in content
        assert content["result"] == "content"

    def test_skips_already_compressed(self):
        """已压缩的消息不应被重复处理"""
        messages = [
            make_tool_msg("1", "read_file", {
                "success": True,
                "result": "<file main.py was modified later, content outdated>",
                "error": "",
                "compressed": True,
            }, "main.py"),
        ]
        modified = {"main.py"}
        result = _invalidate_outdated_reads(messages, modified)

        content = json.loads(result[0]["content"])
        # 应保持原样
        assert content["result"] == "<file main.py was modified later, content outdated>"

    def test_empty_modified_set(self):
        """modified_paths 为空时返回原列表"""
        messages = [make_tool_msg("1", "read_file", {"success": True, "result": "x", "error": ""}, "a.py")]
        result = _invalidate_outdated_reads(messages, set())
        assert result == messages

    def test_preserves_non_tool_messages(self):
        """非 tool 消息应原样保留"""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "assistant", "content": "thinking"},
            make_tool_msg("1", "read_file", {"success": True, "result": "x", "error": ""}, "main.py"),
        ]
        modified = {"main.py"}
        result = _invalidate_outdated_reads(messages, modified)

        assert result[0] == messages[0]
        assert result[1] == messages[1]
        # tool 消息被压缩
        content = json.loads(result[2]["content"])
        assert content.get("compressed") is True


# ──────────────────────────────────────────────────────────
# 测试 _compress_large_results
# ──────────────────────────────────────────────────────────

class TestCompressLargeResults:
    """测试按需重读"""

    def test_compresses_large_result(self):
        """超过阈值的 result 应被压缩"""
        large_content = "x" * 600
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": large_content, "error": ""}, "big.py"),
        ]
        result = _compress_large_results(messages, threshold=500)

        content = json.loads(result[0]["content"])
        assert content["compressed"] is True
        assert content["result"] == "<content: 600 chars>"

    def test_preserves_small_result(self):
        """未超过阈值的 result 应保持不变"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "small", "error": ""}, "small.py"),
        ]
        result = _compress_large_results(messages, threshold=500)

        content = json.loads(result[0]["content"])
        assert "compressed" not in content
        assert content["result"] == "small"

    def test_boundary_threshold(self):
        """恰好等于阈值的不压缩"""
        content_str = "x" * 500
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": content_str, "error": ""}, "b.py"),
        ]
        result = _compress_large_results(messages, threshold=500)

        parsed = json.loads(result[0]["content"])
        assert "compressed" not in parsed

    def test_skips_already_compressed(self):
        """已压缩的消息不应被重复处理"""
        messages = [
            make_tool_msg("1", "read_file", {
                "success": True,
                "result": "<content: 600 chars>",
                "error": "",
                "compressed": True,
            }, "big.py"),
        ]
        result = _compress_large_results(messages, threshold=500)

        content = json.loads(result[0]["content"])
        assert content["result"] == "<content: 600 chars>"

    def test_preserves_non_string_result(self):
        """非字符串 result（如 list）不应被压缩"""
        messages = [
            make_tool_msg("1", "list_files", {"success": True, "result": ["a.py", "b.py"], "error": ""}),
        ]
        result = _compress_large_results(messages, threshold=500)

        content = json.loads(result[0]["content"])
        assert "compressed" not in content
        assert content["result"] == ["a.py", "b.py"]

    def test_custom_threshold(self):
        """自定义阈值"""
        messages = [
            make_tool_msg("1", "read_file", {"success": True, "result": "x" * 150, "error": ""}, "m.py"),
        ]
        result = _compress_large_results(messages, threshold=100)

        content = json.loads(result[0]["content"])
        assert content["compressed"] is True
        assert content["result"] == "<content: 150 chars>"


# ──────────────────────────────────────────────────────────
# 测试 _compress_tool_call_arguments
# ──────────────────────────────────────────────────────────

class TestCompressToolCallArguments:
    """测试压缩大型 tool_calls"""

    def test_compresses_write_file_content(self):
        """write_file 的大型 content 应被压缩"""
        large_code = "print('hello')\n" * 100  # > 500 chars
        tc = make_tool_call("1", "write_file", {"path": "app.py", "content": large_code})
        messages = [make_assistant_msg("Writing file", [tc])]

        result = _compress_tool_call_arguments(messages, threshold=500)

        args = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        assert args["content"].startswith("<")
        assert "chars" in args["content"]
        assert args["path"] == "app.py"

    def test_preserves_small_write_file(self):
        """小型 write_file content 不应被压缩"""
        tc = make_tool_call("1", "write_file", {"path": "small.py", "content": "print('hi')"})
        messages = [make_assistant_msg("Writing", [tc])]

        result = _compress_tool_call_arguments(messages, threshold=500)

        args = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        assert args["content"] == "print('hi')"

    def test_preserves_non_write_file_tools(self):
        """非 write_file 工具的参数不应被压缩"""
        large_content = "x" * 600
        tc = make_tool_call("1", "read_file", {"path": "big.py"})
        messages = [make_assistant_msg("Reading", [tc])]

        result = _compress_tool_call_arguments(messages, threshold=500)

        args = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        assert args["path"] == "big.py"

    def test_skips_already_compressed_content(self):
        """已压缩的 content（占位符格式）不应被重复处理"""
        tc = make_tool_call("1", "write_file", {"path": "app.py", "content": "<1024 chars>"})
        messages = [make_assistant_msg("Writing", [tc])]

        result = _compress_tool_call_arguments(messages, threshold=500)

        args = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        assert args["content"] == "<1024 chars>"

    def test_preserves_assistant_without_tool_calls(self):
        """无 tool_calls 的 assistant 消息应原样保留"""
        messages = [make_assistant_msg("Just thinking")]
        result = _compress_tool_call_arguments(messages, threshold=500)
        assert result == messages

    def test_multiple_tool_calls_in_one_message(self):
        """一条消息中的多个 tool_calls 都应被处理"""
        large_code = "x" * 600
        tc1 = make_tool_call("1", "write_file", {"path": "a.py", "content": large_code})
        tc2 = make_tool_call("2", "write_file", {"path": "b.py", "content": "small"})
        messages = [make_assistant_msg("Writing", [tc1, tc2])]

        result = _compress_tool_call_arguments(messages, threshold=500)

        args1 = json.loads(result[0]["tool_calls"][0]["function"]["arguments"])
        args2 = json.loads(result[0]["tool_calls"][1]["function"]["arguments"])
        assert args1["content"].startswith("<")
        assert args2["content"] == "small"


# ──────────────────────────────────────────────────────────
# 测试 compress_history
# ──────────────────────────────────────────────────────────

class TestCompressHistory:
    """测试 compress_history 主函数"""

    def test_too_few_messages(self):
        """消息数不足时直接返回"""
        messages = make_system_and_task() + [
            make_assistant_msg("thinking"),
            make_tool_msg("1", "read_file", {"success": True, "result": "x", "error": ""}, "a.py"),
        ]
        result = compress_history(messages, keep_recent=5)
        assert result == messages

    def test_preserves_permanent_and_recent(self):
        """permanent 和 recent 区应完整保留"""
        permanent = make_system_and_task()
        middle = [
            make_tool_msg("1", "read_file", {"success": True, "result": "x" * 600, "error": ""}, "old.py"),
            make_assistant_msg("thinking"),
        ]
        recent = [
            make_tool_msg("2", "read_file", {"success": True, "result": "new", "error": ""}, "new.py"),
            make_assistant_msg("final"),
        ]
        messages = permanent + middle + recent

        result = compress_history(messages, keep_recent=2)

        # permanent 区不变
        assert result[0] == permanent[0]
        assert result[1] == permanent[1]
        # recent 区不变
        assert result[-1] == recent[-1]
        assert result[-2] == recent[-2]

    def test_compresses_middle_large_results(self):
        """中间区的大型 result 应被压缩"""
        permanent = make_system_and_task()
        middle = [
            make_tool_msg("1", "read_file", {"success": True, "result": "x" * 600, "error": ""}, "big.py"),
        ]
        recent = [
            make_assistant_msg("done"),
            make_tool_msg("2", "read_file", {"success": True, "result": "ok", "error": ""}, "new.py"),
        ]
        messages = permanent + middle + recent

        result = compress_history(messages, keep_recent=2)

        # 中间区的 tool 消息应被压缩
        middle_content = json.loads(result[2]["content"])
        assert middle_content.get("compressed") is True

    def test_write_invalidation_in_compress_history(self):
        """compress_history 中写后失效应正常工作"""
        permanent = make_system_and_task()
        middle = [
            make_tool_msg("1", "read_file", {"success": True, "result": "old content", "error": ""}, "main.py"),
            make_assistant_msg("modifying"),
            make_tool_msg("2", "write_file", {"success": True, "result": "wrote", "error": ""}, "main.py"),
        ]
        recent = [
            make_assistant_msg("done"),
            make_tool_msg("3", "read_file", {"success": True, "result": "new", "error": ""}, "other.py"),
        ]
        messages = permanent + middle + recent

        result = compress_history(messages, keep_recent=2)

        # 中间区的 read_file 应被标记过期
        read_content = json.loads(result[2]["content"])
        assert read_content.get("compressed") is True
        assert "modified later" in read_content["result"]

    def test_empty_middle(self):
        """中间区为空时直接返回"""
        permanent = make_system_and_task()
        recent = [make_assistant_msg("done")]
        messages = permanent + recent

        result = compress_history(messages, keep_recent=1)
        assert result == messages

    def test_idempotent_compression(self):
        """多次压缩不应产生不同结果"""
        permanent = make_system_and_task()
        middle = [
            make_tool_msg("1", "read_file", {"success": True, "result": "x" * 600, "error": ""}, "big.py"),
            make_assistant_msg("thinking"),
        ]
        recent = [
            make_assistant_msg("done"),
            make_tool_msg("2", "read_file", {"success": True, "result": "ok", "error": ""}, "new.py"),
        ]
        messages = permanent + middle + recent

        first = compress_history(messages, keep_recent=2)
        second = compress_history(first, keep_recent=2)

        # 第二次压缩不应改变任何内容
        assert len(first) == len(second)
        for i in range(len(first)):
            assert first[i] == second[i]

    def test_non_tool_messages_preserved(self):
        """非工具消息（assistant content）应原样保留"""
        permanent = make_system_and_task()
        middle = [
            make_assistant_msg("I am thinking about the problem"),
            make_assistant_msg("Let me read a file"),
        ]
        recent = [
            make_assistant_msg("done"),
            make_tool_msg("1", "read_file", {"success": True, "result": "ok", "error": ""}, "a.py"),
        ]
        messages = permanent + middle + recent

        result = compress_history(messages, keep_recent=2)

        # assistant 消息内容不变
        assert result[2]["content"] == "I am thinking about the problem"
        assert result[3]["content"] == "Let me read a file"

    def test_full_pipeline(self):
        """完整管道测试：写后失效 + 按需重读 + 压缩 tool_calls"""
        permanent = make_system_and_task()
        large_code = "x" * 600
        middle = [
            # 读取大文件
            make_tool_msg("1", "read_file", {"success": True, "result": "x" * 600, "error": ""}, "main.py"),
            make_assistant_msg("I will modify main.py"),
            # 写入大文件（content 参数很大）
            make_assistant_msg("Writing", [
                make_tool_call("2", "write_file", {"path": "main.py", "content": large_code})
            ]),
            make_tool_msg("2", "write_file", {"success": True, "result": "wrote", "error": ""}, "main.py"),
        ]
        recent = [
            make_assistant_msg("done"),
            make_tool_msg("3", "read_file", {"success": True, "result": "ok", "error": ""}, "other.py"),
        ]
        messages = permanent + middle + recent

        result = compress_history(messages, keep_recent=2)

        # 1. read_file 结果被标记过期（写后失效）
        read_content = json.loads(result[2]["content"])
        assert read_content.get("compressed") is True
        assert "modified later" in read_content["result"]

        # 2. assistant 消息内容保留
        assert result[3]["content"] == "I will modify main.py"

        # 3. write_file 的 content 参数被压缩
        write_args = json.loads(result[4]["tool_calls"][0]["function"]["arguments"])
        assert write_args["content"].startswith("<")
        assert "chars" in write_args["content"]

        # 4. write_file 的 tool 结果保持不变（success + "wrote" 很小）
        write_result = json.loads(result[5]["content"])
        assert write_result["result"] == "wrote"

        # 5. recent 区不变
        assert result[-1] == recent[-1]
        assert result[-2] == recent[-2]
