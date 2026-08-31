"""
上下文管理模块

提供上下文大小估算和逐轮压缩功能。
"""

from .manager import estimate_context_size, should_compress
from .compressor import (
    compress_tool_call,
    compress_tool_result,
    compress_tool_message,
    compress_round,
    truncate_compressed,
)

__all__ = [
    "estimate_context_size",
    "should_compress",
    "compress_tool_call",
    "compress_tool_result",
    "compress_tool_message",
    "compress_round",
    "truncate_compressed",
]
