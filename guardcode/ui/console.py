"""
Rich 终端格式化输出模块

提供彩色输出、Panel 显示和日志系统。
所有用户可见的输出都通过此模块，确保格式统一。

日志系统：
- RichHandler：终端彩色输出
- FileHandler：持久化到 ~/.guardcode/logs/agent.log
- 格式：{timestamp} | {level} | {name} | {message}
- 兜底：日志写入失败用 try/except 静默跳过
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.logging import RichHandler
from rich.text import Text
from rich.table import Table

# ──────────────────────────────────────────────────────────
# 全局 Console 实例
# ──────────────────────────────────────────────────────────

console = Console()


# ──────────────────────────────────────────────────────────
# 日志系统
# ──────────────────────────────────────────────────────────

_LOG_DIR = Path.home() / ".guardcode" / "logs"
_LOG_FILE = _LOG_DIR / "agent.log"
_logger: logging.Logger | None = None


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = False,
) -> logging.Logger:
    """配置并返回 GuardCode Agent 的 logger。

    使用 RichHandler 做终端输出（彩色 + traceback），
    FileHandler 做文件持久化。

    所有日志调用用 try/except 包裹，写入失败不影响主流程。

    Args:
        level: 日志级别（默认 INFO）
        log_to_file: 是否写入文件（默认 True）
        log_to_console: 是否在终端输出日志（默认 False，
                       因为终端已有 Rich 格式化输出，日志主要写文件）

    Returns:
        配置好的 Logger 实例
    """
    global _logger

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("guardcode")
    _logger.setLevel(level)

    # Clear any existing handlers (handles re-initialization after reset)
    _logger.handlers.clear()

    # 文件 Handler（始终启用，除非显式关闭）
    if log_to_file:
        try:
            _LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                _LOG_FILE, encoding="utf-8"
            )
            file_handler.setLevel(level)
            file_formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            _logger.addHandler(file_handler)
        except (OSError, PermissionError):
            # 日志目录创建或文件写入失败，静默跳过
            pass

    # 终端 Handler（RichHandler，可选）
    if log_to_console:
        try:
            rich_handler = RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=False,
            )
            rich_handler.setLevel(level)
            _logger.addHandler(rich_handler)
        except Exception:
            pass

    # 防止日志传播到 root logger
    _logger.propagate = False

    return _logger


def get_logger() -> logging.Logger:
    """获取已配置的 logger，如果未配置则自动配置。"""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


# ──────────────────────────────────────────────────────────
# Rich 格式化输出函数
# ──────────────────────────────────────────────────────────

def print_tool_call(tool_name: str, args: Dict[str, Any]) -> None:
    """打印工具调用信息（蓝色，带 → 图标）。

    Args:
        tool_name: 工具名称
        args: 工具参数
    """
    # 格式化参数，截断过长的值
    parts = []
    for key, value in args.items():
        val_str = repr(value)
        if len(val_str) > 80:
            val_str = val_str[:80] + "..."
        parts.append(f"{key}={val_str}")
    args_str = ", ".join(parts)

    console.print(f"[blue]→ Tool:[/blue] {tool_name}({args_str})")

    # 日志记录
    try:
        get_logger().info(f"Tool: {tool_name}({args})")
    except Exception:
        pass


def print_tool_result(result: Dict[str, Any]) -> None:
    """打印工具执行结果（绿色 ✓ 或红色 ✗）。

    Args:
        result: 工具执行结果 {"success", "result", "error"}
    """
    if result["success"]:
        output = str(result.get("result", ""))
        if len(output) > 200:
            output = output[:200] + "..."
        console.print(f"[green]✓ Result:[/green] {output}")
    else:
        error = result.get("error", "Unknown error")
        console.print(f"[red]✗ Error:[/red] {error}")

    # 日志记录
    try:
        if result["success"]:
            get_logger().info(f"Result: success=True, result={str(result.get('result', ''))[:200]}")
        else:
            get_logger().error(f"Result: success=False, error={result.get('error', '')}")
    except Exception:
        pass


def print_risk_warning(risks: List[Dict[str, Any]]) -> None:
    """打印代码风险警告（黄色 Panel）。

    Args:
        risks: scan_python_code 返回的风险列表
    """
    if not risks:
        return

    # 构建风险表格
    table = Table(show_header=True, header_style="yellow", border_style="yellow")
    table.add_column("Pattern", style="yellow")
    table.add_column("Line", style="yellow", justify="right")
    table.add_column("Content", style="white")

    for risk in risks:
        table.add_row(
            risk["pattern"],
            str(risk["line"]),
            risk["content"],
        )

    panel = Panel(
        table,
        title="[yellow]⚠ Security Warning[/yellow]",
        border_style="yellow",
        expand=False,
    )
    console.print(panel)

    # 日志记录
    try:
        for risk in risks:
            get_logger().warning(
                f"Risk: {risk['pattern']} at line {risk['line']}: {risk['content']}"
            )
    except Exception:
        pass


def print_confirm_prompt(tool_name: str, args: Dict[str, Any]) -> None:
    """打印用户确认提示（紫色 ❓）。

    Args:
        tool_name: 工具名称
        args: 工具参数
    """
    # 格式化参数
    lines = []
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 100:
            display_value = value[:100] + "..."
        elif isinstance(value, (dict, list)):
            display_value = json.dumps(value, indent=2, ensure_ascii=False)
        else:
            display_value = str(value)
        lines.append(f"  {key}: {display_value}")

    content = f"Tool: {tool_name}\n\nArguments:\n" + "\n".join(lines)

    panel = Panel(
        content,
        title="[magenta]🛡 Dangerous Operation[/magenta]",
        border_style="magenta",
        expand=False,
    )
    console.print(panel)
    console.print("[magenta]❓ Confirm:[/magenta] Do you want to proceed? (y/n)", end=" ")

    # 日志记录
    try:
        get_logger().info(f"Confirm prompt: {tool_name}({args})")
    except Exception:
        pass


def print_context_compress(original_count: int, new_count: int) -> None:
    """打印上下文压缩通知（青色 📊）。

    Args:
        original_count: 压缩前的消息数
        new_count: 压缩后的消息数
    """
    console.print(
        f"[cyan]📊 Context:[/cyan] Compressed {original_count} -> {new_count} messages"
    )

    # 日志记录
    try:
        get_logger().info(
            f"Context compressed: {original_count} -> {new_count} messages"
        )
    except Exception:
        pass


def print_final_response(content: str) -> None:
    """打印最终响应（正常格式，带分隔线）。

    Args:
        content: 模型的最终文本回复
    """
    console.print()
    console.rule("[bold]Final Response[/bold]")
    console.print(content)
    console.rule()

    # 日志记录
    try:
        get_logger().info(f"Final response: {content[:200]}")
    except Exception:
        pass


def print_error(message: str) -> None:
    """打印错误信息（红色）。

    Args:
        message: 错误信息
    """
    console.print(f"[red]✗ Error:[/red] {message}")

    try:
        get_logger().error(message)
    except Exception:
        pass


def print_info(message: str) -> None:
    """打印普通信息。

    Args:
        message: 信息内容
    """
    console.print(f"[dim]ℹ {message}[/dim]")

    try:
        get_logger().info(message)
    except Exception:
        pass


def print_model_call(message_count: int, total_chars: int) -> None:
    """打印模型调用信息（暗色 💬）。

    Args:
        message_count: 发送的消息数
        total_chars: 总字符数
    """
    console.print(
        f"[dim]💬 Model:[/dim] Sending {message_count} messages, {total_chars} chars"
    )

    try:
        get_logger().info(
            f"Model call: {message_count} messages, {total_chars} chars"
        )
    except Exception:
        pass


def print_blocked(tool_name: str, args: Dict[str, Any]) -> None:
    """打印操作被阻止的信息（红色 Panel）。

    Args:
        tool_name: 工具名称
        args: 工具参数
    """
    parts = [f"Tool: {tool_name}", "\nArguments:"]
    for key, value in args.items():
        if isinstance(value, str) and len(value) > 100:
            display_value = value[:100] + "..."
        else:
            display_value = str(value)
        parts.append(f"  {key}: {display_value}")

    panel = Panel(
        "\n".join(parts),
        title="[red]🚫 Operation Blocked[/red]",
        border_style="red",
        expand=False,
    )
    console.print(panel)

    try:
        get_logger().warning(f"Blocked: {tool_name}({args})")
    except Exception:
        pass


def print_session_saved(session_path: str) -> None:
    """打印会话保存通知。

    Args:
        session_path: 保存的会话文件路径
    """
    console.print()
    console.print(
        f"[yellow]⚠ Task interrupted. Conversation history saved to:[/yellow]"
    )
    console.print(f"  [dim]{session_path}[/dim]")
    console.print()

    try:
        get_logger().info(f"Session saved: {session_path}")
    except Exception:
        pass
