"""
GuardCode Agent 核心循环

这是 agent 的核心模块，实现了：
- Agent 主循环（调模型 → 检查 tool_calls → 执行工具 → 结果送回模型）
- Rich 格式化终端输出
- 日志持久化（~/.guardcode/logs/agent.log）
- 模型调用重试（指数退避）
- 用户中断处理（Ctrl+C 保存会话）
- CLI 参数解析（--workspace, --model, --api-base, --verbose, --version 等）
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .model import call_model_with_retry
from .tools.base import execute_tool, get_tool_schemas
from .workspace import init_workspace
from .context import (
    should_compress,
    compress_history,
    _invalidate_outdated_reads,
    _compress_large_results,
)
from .ui.console import (
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
    print_session_saved,
    setup_logging,
    get_logger,
)

# 确保工具被注册（import 即触发 @register_tool 装饰器）
from .tools import file_tools       # noqa: F401
from .tools import command_tools    # noqa: F401


# ──────────────────────────────────────────────────────────
# System Prompt
# 你可以修改这段 prompt，它决定了 agent 的行为方式
# ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are GuardCode Agent, an AI coding assistant focused on trustworthy software development.

## Role
You help users write, test, and fix code. You operate autonomously: read files, write code, run commands, and verify results. Your goal is to deliver working, tested code.

## Tools
- read_file(path): Read file content. Use to understand existing code before modifying.
- write_file(path, content): Create or overwrite a file. Always read before writing.
- list_files(directory): List files in a directory. Use "." to see workspace root.
- delete_file(path): Delete a file. Use cautiously.
- run_command(command, timeout): Execute a shell command (default timeout: 30s). Use for running tests, building, and checking code.

## Test-Driven Workflow
1. **Explore**: Use list_files to understand the workspace structure. Look for test files (test_*.py, *_test.py).
2. **If tests exist**:
   - Read the test file to understand expected behavior
   - Read the source file to find the bug
   - Write the fix
   - Run tests: run_command("python -m pytest <test_file> -v")
   - If tests fail, read the error output, fix the code, and re-run (max 5 iterations)
3. **If no tests exist**:
   - Prefer TDD: write tests first, then implement
   - If TDD is not practical, verify with: run_command("python -c 'import <module>'") or compile checks

## Security
- All file operations are restricted to the workspace directory
- Dangerous commands (rm -rf, format, etc.) are blocked automatically
- Code with risky patterns (eval, exec, os.system, subprocess with shell=True) triggers warnings
- Never attempt path traversal (../) — it will be rejected

## Best Practices
- Read before write: always understand existing code before modifying
- Incremental changes: make small, focused changes; verify after each
- Run tests after every code change
- Use meaningful commit messages if the user asks for version control
- When fixing a bug, identify the root cause before writing the fix
- If a command fails, read the error message carefully before retrying
"""


# ──────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────

def _format_assistant_message(response: dict[str, Any]) -> dict[str, Any]:
    """将 call_model 的返回值转换为 OpenAI assistant 消息格式。

    call_model 返回: {"content": str|None, "tool_calls": [{"id", "name", "arguments"}]}
    OpenAI 需要的格式:
        无 tool_calls 时: {"role": "assistant", "content": "..."}
        有 tool_calls 时: {"role": "assistant", "content": "...", "tool_calls": [
            {"id": "...", "type": "function", "function": {"name": "...", "arguments": "..."}}
        ]}

    注意: OpenAI 的 arguments 字段必须是 JSON 字符串，不是 dict。
    """
    message: dict[str, Any] = {
        "role": "assistant",
        "content": response["content"],
    }

    if response["tool_calls"]:
        message["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                },
            }
            for tc in response["tool_calls"]
        ]

    return message


def _format_tool_result(
    tool_call_id: str,
    tool_name: str,
    result: dict[str, Any],
    tool_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将工具执行结果转换为 OpenAI tool 消息格式。

    在 content JSON 中增加元信息（_tool_name, _path），
    供上下文压缩器使用（写后失效、按需重读）。

    Args:
        tool_call_id: 对应的 tool_call ID（用于关联请求和响应）
        tool_name: 工具名称（如 "read_file", "write_file"）
        result: execute_tool 的返回值 {"success", "result", "error"}
        tool_args: 工具参数（可选，用于提取路径元信息）

    Returns:
        {"role": "tool", "tool_call_id": "...", "content": "..."}
    """
    content = result.copy()
    content["_tool_name"] = tool_name

    # 对文件操作工具，记录规范化路径（用于写后失效匹配）
    if tool_name in ("read_file", "write_file", "delete_file") and tool_args:
        path = tool_args.get("path", "")
        if path:
            # 规范化路径：统一分隔符，消除 ./ 前缀
            content["_path"] = Path(path).as_posix()

    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(content, ensure_ascii=False, default=str),
    }


def _print_verbose(msg: str, config: Config) -> None:
    """verbose 模式下打印调试信息。"""
    if config.verbose:
        print_info(msg)


def _log(msg: str, level: str = "info") -> None:
    """记录日志到文件（~/.guardcode/logs/agent.log）。

    所有日志调用用 try/except 包裹，写入失败不影响主流程。
    """
    try:
        logger = get_logger()
        if level == "info":
            logger.info(msg)
        elif level == "warning":
            logger.warning(msg)
        elif level == "error":
            logger.error(msg)
    except Exception:
        pass  # 日志写入失败不应影响主流程


def save_session(messages: list[dict[str, Any]], workspace: str) -> str:
    """保存当前对话历史到会话文件。

    在用户中断（Ctrl+C）时调用，保存到 ~/.guardcode/sessions/{timestamp}.json

    Args:
        messages: 当前对话历史
        workspace: 工作区路径

    Returns:
        保存的文件路径
    """
    sessions_dir = Path.home() / ".guardcode" / "sessions"
    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_file = sessions_dir / f"{timestamp}.json"

        session_data = {
            "timestamp": timestamp,
            "workspace": workspace,
            "message_count": len(messages),
            "messages": messages,
        }

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2, default=str)

        return str(session_file)
    except (OSError, PermissionError) as e:
        _log(f"Failed to save session: {e}", "error")
        return ""


# ──────────────────────────────────────────────────────────
# Agent Loop
# ──────────────────────────────────────────────────────────

def run_agent_loop(
    task: str,
    config: Config | None = None,
    max_iterations: int = 50,
) -> str:
    """Agent 主循环。

    流程：
    1. 初始化消息列表（system prompt + user task）
    2. 循环：调模型 → 检查 tool_calls → 执行工具 → 结果送回模型
    3. 终止条件：无 tool_calls / 达到 max_iterations / 连续失败超限 / 循环检测

    Args:
        task: 用户交给 agent 的编程任务
        config: 配置对象（可选，不传则自动加载）
        max_iterations: 最大循环次数

    Returns:
        agent 的最终文本回复
    """
    # ── 1. 初始化 ──────────────────────────────────────────
    if config is None:
        config = load_config()

    # 初始化日志系统
    setup_logging()

    init_workspace(config.workspace)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    # 初始化计数器
    iteration = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3
    last_tool_calls: list[dict] | None = None  # 循环检测：上一轮的工具调用

    _print_verbose(f"Agent started. Task: {task[:100]}...", config)
    _log(f"Agent started. Task: {task[:200]}")

    # 主循环
    while iteration < max_iterations:
        iteration += 1
        _print_verbose(f"Starting iteration {iteration}...", config)

        # 上下文压缩：在调用模型前检查并压缩
        if should_compress(messages, threshold=config.context.max_context_size):
            original_count = len(messages)
            messages = compress_history(
                messages,
                keep_recent=config.context.keep_recent_messages,
            )
            print_context_compress(original_count, len(messages))
            _log(
                f"[Iteration {iteration}] Context compressed: "
                f"{original_count} -> {len(messages)} messages"
            )

        # 调用模型（带重试）
        try:
            # 打印模型调用信息
            from .context.manager import estimate_context_size
            total_chars = estimate_context_size(messages)
            print_model_call(len(messages), total_chars)

            response = call_model_with_retry(
                messages,
                model_name=config.model,
                api_key=config.api_key,
                api_base=config.api_base,
            )
        except Exception as e:
            consecutive_failures += 1
            print_error(f"Model call failed: {e}")
            _log(f"[Iteration {iteration}] Model error: {e}", "error")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print_error("Too many consecutive failures. Stopping.")
                _log("Agent stopped: too many consecutive failures.", "error")
                return "Agent stopped: too many consecutive failures."
            continue

        # 将 assistant 回复加入消息历史
        messages.append(_format_assistant_message(response))

        # 检查是否有工具调用
        if not response["tool_calls"]:
            _print_verbose("No tool calls, task completed.", config)
            _log("Task completed. No more tool calls.")
            final_content = response["content"] or "Task completed."
            print_final_response(final_content)
            return final_content

        # 循环检测：连续两轮工具调用完全相同 → 可能陷入死循环
        current_tool_calls = [
            {"name": tc["name"], "arguments": tc["arguments"]}
            for tc in response["tool_calls"]
        ]
        if last_tool_calls is not None and current_tool_calls == last_tool_calls:
            _print_verbose(
                "Loop detected: same tool calls as previous iteration.", config
            )
            _log(
                f"[Iteration {iteration}] Loop detected: "
                f"{current_tool_calls}. Stopping to prevent infinite loop.",
                "warning",
            )
            print_error("Loop detected: same tool calls repeated. Stopping.")
            return (
                f"Agent stopped: loop detected (same tool calls repeated). "
                f"Last action: {current_tool_calls}"
            )
        last_tool_calls = current_tool_calls

        # 执行工具调用
        for tool_call in response["tool_calls"]:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            tool_id = tool_call["id"]

            _print_verbose(f"Executing tool: {tool_name}({tool_args})", config)
            print_tool_call(tool_name, tool_args)
            _log(f"[Iteration {iteration}] Tool: {tool_name}({tool_args})")

            # 执行工具（execute_tool 内部已集成风险分级）
            result = execute_tool(tool_name, tool_args, config=config)

            print_tool_result(result)
            _print_verbose(
                f"Tool result: success={result['success']}, "
                f"error={result.get('error', '')}",
                config,
            )
            _log(
                f"[Iteration {iteration}] Result: success={result['success']}, "
                f"error={result.get('error', '')}"
            )

            # 将工具结果加入消息历史（含工具元信息，供压缩器使用）
            messages.append(_format_tool_result(tool_id, tool_name, result, tool_args))

            # 事件驱动失效：写/删成功后立即失效旧读取结果
            # 不等阈值触发，因为文件被修改的那一刻旧内容就已过期
            if tool_name in ("write_file", "delete_file") and result["success"]:
                file_path = tool_args.get("path", "")
                if file_path:
                    normalized = Path(file_path).as_posix()
                    before = sum(
                        len(m.get("content", "")) for m in messages
                        if m.get("role") == "tool"
                    )
                    messages = _invalidate_outdated_reads(messages, {normalized})
                    after = sum(
                        len(m.get("content", "")) for m in messages
                        if m.get("role") == "tool"
                    )
                    if before != after:
                        _print_verbose(
                            f"Write invalidation: invalidated old reads "
                            f"for {normalized} ({before} -> {after} chars)",
                            config,
                        )
                        _log(
                            f"[Iteration {iteration}] Write invalidation: "
                            f"{normalized} ({before} -> {after} chars)"
                        )

            # 读事件驱动：read_file 成功后压缩旧大型读取结果
            # 模型刚读了新文件，旧的大型读取结果已不需要完整保留
            if tool_name == "read_file" and result["success"]:
                before = sum(
                    len(m.get("content", "")) for m in messages
                    if m.get("role") == "tool"
                )
                # 压缩除最后一条（刚加入的）以外的所有消息
                messages = _compress_large_results(messages[:-1]) + [messages[-1]]
                after = sum(
                    len(m.get("content", "")) for m in messages
                    if m.get("role") == "tool"
                )
                if before != after:
                    _print_verbose(
                        f"Read compression: compressed old large reads "
                        f"({before} -> {after} chars)",
                        config,
                    )
                    _log(
                        f"[Iteration {iteration}] Read compression: "
                        f"({before} -> {after} chars)"
                    )

            # 连续失败计数
            if not result["success"]:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            # 连续失败超限 → 终止
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print_error("Too many consecutive failures. Stopping.")
                _log("Agent stopped: too many consecutive failures.", "error")
                return "Agent stopped: too many consecutive failures."

        _print_verbose(f"Iteration {iteration} complete.", config)

    # 达到 max_iterations
    _print_verbose(
        f"Reached max iterations ({max_iterations}). Task may not be fully completed.",
        config,
    )
    _log(
        f"[Iteration {iteration}] Reached max_iterations ({max_iterations}). Stopping.",
        "warning",
    )
    return (
        f"Agent stopped: reached maximum iterations ({max_iterations}). "
        f"Task may not be fully completed."
    )


# ──────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────

def main():
    """命令行入口。

    用法:
        python -m guardcode "你的编程任务"
        python -m guardcode "写一个冒泡排序" --workspace ./myproject --model gpt-4-turbo
        python -m guardcode "fix the bug" --api-base https://api.deepseek.com/v1 --model deepseek-chat
        python -m guardcode --version
    """
    import argparse

    from . import __version__

    parser = argparse.ArgumentParser(
        description="GuardCode Agent — Autonomous coding agent with security gating",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  guardcode "implement quicksort in Python with tests"
  guardcode --workspace /path/to/project "fix the bug in main.py"
  guardcode --model gpt-4o --max-iterations 10 "refactor auth module"
  guardcode --api-base https://api.deepseek.com/v1 --model deepseek-chat "write a REST API"
  guardcode --verbose "implement a stack with push/pop/peek"
  guardcode --version
""",
    )
    parser.add_argument("task", nargs="?", default=None, help="Programming task for the agent")
    parser.add_argument("--workspace", default=".", help="Workspace directory (default: current directory)")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max loop iterations (default: 50)")
    parser.add_argument("--model", default=None, help="Model name override (default: from config)")
    parser.add_argument("--api-base", default=None, help="API endpoint URL override (default: from config)")
    parser.add_argument("--config", default=None, help="Path to config file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--version", action="version", version=f"GuardCode Agent v{__version__}")

    args = parser.parse_args()

    # 参数验证：task 是必需的（除非是 --version）
    if args.task is None:
        parser.print_help()
        sys.exit(1)

    # 参数验证：检查 workspace 是否存在
    workspace_path = Path(args.workspace)
    if not workspace_path.exists():
        print_error(f"Workspace directory does not exist: {workspace_path.resolve()}")
        sys.exit(1)
    if not workspace_path.is_dir():
        print_error(f"Workspace path is not a directory: {workspace_path.resolve()}")
        sys.exit(1)

    # 加载配置
    config = load_config(config_file=args.config, workspace=args.workspace)

    # 应用命令行覆盖
    if args.model:
        config.model = args.model
    if args.api_base:
        config.api_base = args.api_base
    if args.verbose:
        config.verbose = True

    # 参数验证：检查 API key
    if not config.api_key and not __import__("os").getenv("OPENAI_API_KEY"):
        print_error(
            "OPENAI_API_KEY is not set. "
            "Please set it as an environment variable or in config file."
        )
        print_info("Example: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    # 初始化日志
    setup_logging()

    # 运行 Agent 循环，捕获用户中断
    try:
        result = run_agent_loop(
            args.task, config=config, max_iterations=args.max_iterations
        )
    except KeyboardInterrupt:
        # 用户中断：保存会话并优雅退出
        console.print()
        console.print("[yellow]⚠ Task interrupted by user (Ctrl+C)[/yellow]")

        # 获取当前 messages（从 run_agent_loop 的上下文无法直接获取，
        # 但我们可以保存一个简化版本）
        session_path = save_session(
            [{"role": "system", "content": "Session interrupted by user"},
             {"role": "user", "content": args.task}],
            args.workspace,
        )
        if session_path:
            print_session_saved(session_path)
        else:
            print_error("Failed to save session.")
        sys.exit(130)  # 128 + SIGINT(2) = 130

    # 正常输出结果
    if not result.startswith("Agent stopped"):
        # 已经在 run_agent_loop 中通过 print_final_response 输出了
        pass
    else:
        # 异常终止的情况
        console.print()
        console.rule("[red]Agent Stopped[/red]")
        console.print(result)


if __name__ == "__main__":
    main()
