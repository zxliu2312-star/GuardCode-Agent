"""
GuardCode Agent UI 模块

提供 Rich 终端格式化输出和日志系统。
"""

from .console import (
    console,
    print_tool_call,
    print_tool_result,
    print_risk_warning,
    print_confirm_prompt,
    print_context_compress,
    print_final_response,
    print_error,
    print_info,
    print_model_call,
    print_blocked,
    setup_logging,
    get_logger,
)

__all__ = [
    "console",
    "print_tool_call",
    "print_tool_result",
    "print_risk_warning",
    "print_confirm_prompt",
    "print_context_compress",
    "print_final_response",
    "print_error",
    "print_info",
    "print_model_call",
    "print_blocked",
    "setup_logging",
    "get_logger",
]
