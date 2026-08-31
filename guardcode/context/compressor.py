"""
上下文压缩器

两级压缩策略：
- Level 1: 规则压缩（写后失效 + 按需重读 + 压缩大型 tool_calls + 工作集保留）
- Level 2: LLM 摘要（可选，仅在 Level 1 压缩率不足时启用）

核心原则：
- Workspace 是 Source of Truth（文件系统为准）
- 历史是易失性记忆（messages 可压缩）
- 重新读取优于大上下文（模型需要时可重新调 read_file）
"""

import json
from typing import Any

from .manager import estimate_context_size


# ──────────────────────────────────────────────────────────
# Level 1: 规则压缩
# ──────────────────────────────────────────────────────────

def _find_modified_paths(messages: list[dict[str, Any]]) -> set[str]:
    """扫描历史，找出所有被 write_file/delete_file 成功修改的路径。

    扫描所有消息（包括 recent 区），因为即使修改发生在最近几轮，
    中间区的旧读取结果也已经过期。

    Returns:
        被修改过的规范化路径集合
    """
    modified: set[str] = set()
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        try:
            content = json.loads(msg["content"])
        except (json.JSONDecodeError, TypeError):
            continue

        tool_name = content.get("_tool_name", "")
        if tool_name in ("write_file", "delete_file") and content.get("success"):
            path = content.get("_path", "")
            if path:
                modified.add(path)
    return modified


def _invalidate_outdated_reads(
    messages: list[dict[str, Any]],
    modified_paths: set[str],
) -> list[dict[str, Any]]:
    """将所有被修改过的文件的旧 read_file 结果标记为过期。

    如果文件后续被 write_file 或 delete_file 修改，
    旧的 read_file 结果已不可信，替换为过期标记。

    幂等性：已标记 compressed 的消息不会被重复处理。
    """
    if not modified_paths:
        return messages

    compressed: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "tool":
            try:
                content = json.loads(msg["content"])
            except (json.JSONDecodeError, TypeError):
                compressed.append(msg)
                continue

            # 跳过已压缩的
            if content.get("compressed"):
                compressed.append(msg)
                continue

            # 检查是否为 read_file 结果且路径被修改过
            if content.get("_tool_name") == "read_file":
                path = content.get("_path", "")
                if path in modified_paths:
                    content["result"] = (
                        f"<file {path} was modified later, content outdated>"
                    )
                    content["compressed"] = True
                    msg = msg.copy()
                    msg["content"] = json.dumps(
                        content, ensure_ascii=False, default=str
                    )
                    compressed.append(msg)
                    continue

        compressed.append(msg)

    return compressed


def _compress_large_results(
    messages: list[dict[str, Any]],
    threshold: int = 500,
) -> list[dict[str, Any]]:
    """压缩大型工具结果，保留元信息。

    将超过阈值的 result 字符串替换为 `<content: N chars>` 占位符。
    模型需要具体内容时可重新调 read_file。

    幂等性：已标记 compressed 的消息不会被重复处理。
    """
    compressed: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "tool":
            try:
                content = json.loads(msg["content"])
            except (json.JSONDecodeError, TypeError):
                compressed.append(msg)
                continue

            # 跳过已压缩的
            if content.get("compressed"):
                compressed.append(msg)
                continue

            # 压缩大型 result
            result = content.get("result", "")
            if isinstance(result, str) and len(result) > threshold:
                content["result"] = f"<content: {len(result)} chars>"
                content["compressed"] = True
                msg = msg.copy()
                msg["content"] = json.dumps(
                    content, ensure_ascii=False, default=str
                )
                compressed.append(msg)
                continue

        compressed.append(msg)

    return compressed


def _compress_tool_call_arguments(
    messages: list[dict[str, Any]],
    threshold: int = 500,
) -> list[dict[str, Any]]:
    """压缩 assistant 消息中 write_file 的大型 content 参数。

    write_file 的 content 参数可能非常大（完整文件内容），
    压缩为 `<N chars>` 占位符，保留工具名和其他小参数。

    幂等性：通过检查 arguments 中 content 是否已是占位符格式来跳过。
    """
    compressed: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            msg = msg.copy()
            compressed_tool_calls = []

            for tc in msg["tool_calls"]:
                tc_copy = tc.copy()
                func = tc_copy.get("function", {}).copy()

                try:
                    args = json.loads(func.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    compressed_tool_calls.append(tc_copy)
                    continue

                # 仅压缩 write_file 的 content 参数
                if func.get("name") == "write_file":
                    content = args.get("content", "")
                    # 跳过已压缩的（占位符格式：<N chars>）
                    if (
                        isinstance(content, str)
                        and len(content) > threshold
                        and not content.startswith("<")
                    ):
                        args["content"] = f"<{len(content)} chars>"
                        func["arguments"] = json.dumps(
                            args, ensure_ascii=False
                        )

                tc_copy["function"] = func
                compressed_tool_calls.append(tc_copy)

            msg["tool_calls"] = compressed_tool_calls
            compressed.append(msg)
            continue

        compressed.append(msg)

    return compressed


# ──────────────────────────────────────────────────────────
# Level 2: LLM 摘要（可选）
# ──────────────────────────────────────────────────────────

def _summarize_with_llm(
    messages: list[dict[str, Any]],
    api_key: str = "",
    api_base: str = "",
    model_name: str = "gpt-3.5-turbo",
) -> str:
    """调用 LLM 生成对话历史摘要。

    禁止脑补 Prompt：只记录已执行的操作，不添加未执行的计划。

    Args:
        messages: 要摘要的消息列表
        api_key: API 密钥
        api_base: API 端点
        model_name: 使用的模型（建议用较次模型节省成本）

    Returns:
        摘要文本，失败时返回兜底消息
    """
    prompt = (
        "Summarize the following conversation history in 2-3 sentences.\n"
        "Focus ONLY on:\n"
        "- What tasks were completed\n"
        "- What files were read/written\n"
        "- What commands were executed\n"
        "- Current progress and state\n\n"
        "Do NOT add:\n"
        "- New suggestions\n"
        "- Future plans\n"
        "- Unexecuted steps\n\n"
        "Summary:"
    )

    summary_messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(messages, ensure_ascii=False, default=str),
        },
    ]

    try:
        from ..model import call_model

        response = call_model(
            summary_messages,
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
        )
        return response.get("content") or "[Summarization returned empty]"
    except Exception as e:
        return f"[Summarization failed: {e}]"


# ──────────────────────────────────────────────────────────
# 主入口：compress_history
# ──────────────────────────────────────────────────────────

def compress_history(
    messages: list[dict[str, Any]],
    keep_recent: int = 5,
    use_llm_summary: bool = False,
    api_key: str = "",
    api_base: str = "",
    summary_model: str = "gpt-3.5-turbo",
) -> list[dict[str, Any]]:
    """两级压缩策略。

    分区结构：
    - permanent: messages[0:2]（system prompt + 第一条 user task）
    - middle: messages[2:-keep_recent]（可压缩的中间区）
    - recent: messages[-keep_recent:]（工作集，完整保留）

    Level 1 规则压缩（始终执行）：
    1. 写后失效：write_file/delete_file 后旧 read_file 标记过期
    2. 按需重读：大型 result 压缩为元信息
    3. 压缩大型 tool_calls：write_file 的大型 content 压缩为占位符

    Level 2 LLM 摘要（可选，use_llm_summary=True 时）：
    - 仅在 Level 1 压缩率不足 50% 时启用
    - 使用较次模型生成 2-3 句话摘要

    Args:
        messages: 完整消息列表
        keep_recent: 保留最近 N 条完整消息
        use_llm_summary: 是否启用 Level 2 LLM 摘要
        api_key: API 密钥（Level 2 需要）
        api_base: API 端点（Level 2 需要）
        summary_model: 摘要使用的模型（Level 2 需要）

    Returns:
        压缩后的消息列表
    """
    # 消息数不足，无需压缩
    if len(messages) <= keep_recent + 2:
        return messages

    # 分区
    permanent = messages[0:2]
    middle = messages[2:-keep_recent]
    recent = messages[-keep_recent:]

    if not middle:
        return messages

    # 从所有消息中找出被修改过的路径（包括 recent 区）
    modified_paths = _find_modified_paths(messages)

    # Level 1: 规则压缩
    compressed_middle = middle
    if modified_paths:
        compressed_middle = _invalidate_outdated_reads(
            compressed_middle, modified_paths
        )
    compressed_middle = _compress_large_results(compressed_middle)
    compressed_middle = _compress_tool_call_arguments(compressed_middle)

    # Level 2: LLM 摘要（可选）
    if use_llm_summary:
        original_size = estimate_context_size(middle)
        compressed_size = estimate_context_size(compressed_middle)
        if original_size > 0 and compressed_size / original_size > 0.5:
            summary = _summarize_with_llm(
                compressed_middle,
                api_key=api_key,
                api_base=api_base,
                model_name=summary_model,
            )
            compressed_middle = [
                {
                    "role": "user",
                    "content": f"[Previous conversation summary]: {summary}",
                }
            ]

    return permanent + compressed_middle + recent
