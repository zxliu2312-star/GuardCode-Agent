"""
逐轮上下文压缩器

每轮工具调用完成后立即压缩非最近一轮的工具消息，
保留操作语义（做了什么、结果如何），丢弃冗余内容（完整文件内容、长输出）。
类似人类工作记忆机制——模型需要具体内容时可重新调 read_file。

设计要点：
- 纯规则压缩，无需额外模型调用，零成本零延迟
- 压缩标记嵌入内容（[compressed: N chars]），通过内容检测避免重复压缩
- 非工具消息（system/user/纯文本 assistant）不压缩
"""

import json
from typing import Any

# ── 压缩阈值 ──────────────────────────────────────────────
MAX_ARG_LENGTH = 200  # 参数值超过此长度则压缩
MAX_RESULT_LENGTH = 200  # 结果内容超过此长度则压缩

# 压缩标记，嵌入被压缩的内容中，同时用于检测是否已压缩
_COMPRESSION_TAG = "[compressed:"


# ── 内部工具函数 ──────────────────────────────────────────


def _is_already_compressed(message: dict[str, Any]) -> bool:
    """检测消息是否已被压缩过。

    通过内容中的压缩标记判断，避免重复压缩。
    """
    if message.get("role") == "assistant" and message.get("tool_calls"):
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            args = str(func.get("arguments", ""))
            if _COMPRESSION_TAG in args:
                return True

    if message.get("role") == "tool":
        content = str(message.get("content", ""))
        if _COMPRESSION_TAG in content:
            return True

    return False


# ── 核心压缩函数 ──────────────────────────────────────────


def compress_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    """压缩单个工具调用的参数。

    保留工具名和关键参数摘要，丢弃大体积参数（如 write_file 的 content 全文）。

    Args:
        tool_call: OpenAI 格式的工具调用
            ``{"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}``

    Returns:
        压缩后的 tool_call dict
    """
    function = tool_call.get("function", {})
    name = function.get("name", "")
    arguments_str = function.get("arguments", "{}")

    # 解析参数 JSON 字符串
    try:
        arguments = (
            json.loads(arguments_str)
            if isinstance(arguments_str, str)
            else arguments_str
        )
    except (json.JSONDecodeError, TypeError):
        # 解析失败，保留原始值
        return tool_call

    # 逐个参数检查：超长的字符串参数替换为压缩标记
    compressed_args: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str) and len(value) > MAX_ARG_LENGTH:
            compressed_args[key] = f"{_COMPRESSION_TAG} {len(value)} chars]"
        else:
            compressed_args[key] = value

    new_tool_call = dict(tool_call)
    new_tool_call["function"] = {
        "name": name,
        "arguments": json.dumps(compressed_args, ensure_ascii=False),
    }
    return new_tool_call


def compress_tool_result(result_msg: dict[str, Any]) -> dict[str, Any]:
    """压缩工具结果消息。

    保留 success/error 状态，截断大体积结果内容（如 read_file 返回的全文）。

    Args:
        result_msg: tool role 消息
            ``{"role": "tool", "tool_call_id": "...", "content": "..."}``

    Returns:
        压缩后的消息 dict
    """
    content_str = result_msg.get("content", "")

    # 尝试解析为 JSON
    try:
        content = (
            json.loads(content_str)
            if isinstance(content_str, str)
            else content_str
        )
    except (json.JSONDecodeError, TypeError):
        # 内容不是 JSON，直接截断字符串
        if isinstance(content_str, str) and len(content_str) > MAX_RESULT_LENGTH:
            new_msg = dict(result_msg)
            new_msg["content"] = (
                content_str[:MAX_RESULT_LENGTH]
                + f"...{_COMPRESSION_TAG} {len(content_str)} chars]"
            )
            return new_msg
        return result_msg

    # 压缩 result 字段（保留 success/error）
    if isinstance(content, dict):
        content = dict(content)  # shallow copy，不修改原始消息
        result_value = content.get("result")
        if isinstance(result_value, str) and len(result_value) > MAX_RESULT_LENGTH:
            original_len = len(result_value)
            content["result"] = (
                result_value[:MAX_RESULT_LENGTH]
                + f"...{_COMPRESSION_TAG} {original_len} chars]"
            )

    new_msg = dict(result_msg)
    new_msg["content"] = json.dumps(content, ensure_ascii=False, default=str)
    return new_msg


def compress_tool_message(message: dict[str, Any]) -> dict[str, Any]:
    """压缩单条工具消息。

    根据消息类型分派：
    - **assistant with tool_calls**：压缩每个 tool_call 的参数
    - **tool role**：压缩 result 内容
    - **非工具消息**（system/user/纯文本 assistant）：原样返回
    - **已压缩消息**：原样返回（避免重复压缩）

    Args:
        message: OpenAI 格式的消息 dict

    Returns:
        压缩后的消息 dict（非工具或已压缩消息原样返回）
    """
    # 已压缩的消息跳过
    if _is_already_compressed(message):
        return message

    role = message.get("role")

    if role == "assistant" and message.get("tool_calls"):
        # 压缩 assistant 消息中的每个 tool_call
        new_msg = dict(message)
        new_msg["tool_calls"] = [
            compress_tool_call(tc) for tc in message["tool_calls"]
        ]
        return new_msg

    elif role == "tool":
        return compress_tool_result(message)

    else:
        # 非工具消息（system/user/纯文本 assistant）不压缩
        return message


# ── 轮次识别与批量压缩 ────────────────────────────────────


def _find_round_starts(messages: list[dict[str, Any]]) -> list[int]:
    """找到每轮工具调用的起始索引。

    一轮从 assistant 消息（带 tool_calls）开始，
    到下一个带 tool_calls 的 assistant 消息之前结束。

    Returns:
        轮次起始索引列表，如 [2, 5, 8] 表示第 0/1/2 轮分别从索引 2/5/8 开始
    """
    round_starts = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            round_starts.append(i)
    return round_starts


def compress_round(
    messages: list[dict[str, Any]],
    keep_recent: int = 2,
) -> list[dict[str, Any]]:
    """每轮工具调用后，压缩非最近 keep_recent 轮的工具消息。

    保留最近 ``keep_recent`` 轮工具消息完整，压缩更早的。
    非工具消息（system/user/纯文本 assistant）不压缩。
    已压缩的消息跳过（避免重复压缩）。

    Args:
        messages: 完整消息列表
        keep_recent: 保留最近几轮工具消息不压缩（默认 2）

    Returns:
        压缩后的消息列表（新列表，不修改原列表）
    """
    round_starts = _find_round_starts(messages)

    # 不足 keep_recent 轮，不需要压缩
    if len(round_starts) <= keep_recent:
        return list(messages)  # 返回浅拷贝，保持一致性

    # cutoff 之前的消息需要压缩
    cutoff = round_starts[-keep_recent]

    result = []
    for i, msg in enumerate(messages):
        if i < cutoff:
            result.append(compress_tool_message(msg))
        else:
            result.append(msg)

    return result


def truncate_compressed(
    messages: list[dict[str, Any]],
    keep_recent: int = 5,
) -> list[dict[str, Any]]:
    """兜底策略：对已压缩消息做最终截断。

    当逐轮压缩后仍超出上下文窗口时（极端长对话），
    保留永久消息（system + 第一条 user）和最近 keep_recent 条消息，
    丢弃中间所有已压缩消息。

    Args:
        messages: 消息列表
        keep_recent: 保留最近几条消息（默认 5）

    Returns:
        截断后的消息列表
    """
    if len(messages) <= keep_recent + 2:
        return list(messages)

    permanent = messages[:2]  # system + 第一条 user
    recent = messages[-keep_recent:]

    truncated_count = len(messages) - 2 - keep_recent
    marker = {
        "role": "system",
        "content": (
            f"[Earlier conversation truncated: "
            f"{truncated_count} messages omitted]"
        ),
    }

    return permanent + [marker] + recent
