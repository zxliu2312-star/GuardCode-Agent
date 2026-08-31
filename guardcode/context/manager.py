"""
上下文管理器

估算消息历史的上下文大小，判断是否需要压缩。
"""

import json
from typing import Any


def estimate_context_size(messages: list[dict[str, Any]]) -> int:
    """
    估算消息列表的上下文大小（字符数）。

    使用 json.dumps() 序列化每条消息，累加字符数。
    这是一个粗略估算——实际 token 数通常约为字符数的 1/3 到 1/4
    （取决于语言和编码），但用字符数做阈值判断已经足够。

    Args:
        messages: OpenAI 格式的消息列表

    Returns:
        总字符数
    """
    total = 0
    for msg in messages:
        total += len(json.dumps(msg, ensure_ascii=False))
    return total


def should_compress(
    messages: list[dict[str, Any]],
    threshold: int = 100000,
) -> bool:
    """
    判断是否需要压缩上下文。

    Args:
        messages: 消息列表
        threshold: 字符数阈值，默认 100000（约 25k-30k tokens）

    Returns:
        True 如果总字符数超过阈值
    """
    if len(messages) <= 4:
        # 消息太少，不需要压缩
        return False

    return estimate_context_size(messages) > threshold
