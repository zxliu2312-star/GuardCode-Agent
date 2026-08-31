"""
GuardCode Agent 核心循环

这是 agent 的核心模块。框架已实现辅助函数和整体结构，
标有 # TODO 的部分需要你参照参考文档完成实现。

参考文档：agent_loop_guide.md（位于项目根目录）
"""

import json
import sys
from typing import Any

from .config import Config, load_config
from .model import call_model
from .tools.base import execute_tool, get_tool_schemas
from .workspace import init_workspace
from .context.compressor import compress_round, truncate_compressed
from .context.manager import should_compress

# 确保工具被注册（import 即触发 @register_tool 装饰器）
from .tools import file_tools       # noqa: F401
from .tools import command_tools    # noqa: F401


# ──────────────────────────────────────────────────────────
# System Prompt
# 你可以修改这段 prompt，它决定了 agent 的行为方式
# ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are GuardCode Agent, a coding assistant focused on trustworthy software development.

**Core Workflow:**
1. Understand the task and workspace structure
2. Before writing code, check for existing tests using list_files
3. If tests exist:
   - Write/modify code
   - Run relevant tests using run_command("pytest <test_path>")
   - If tests fail, analyze output and fix (max 5 iterations)
4. If no tests exist:
   - Prefer TDD: write tests first, then implementation
   - Or use alternative verification methods (compile, lint, run)

**Tools Available:**
- read_file(path): Read file content
- write_file(path, content): Create or overwrite file
- list_files(directory): List files in directory
- delete_file(path): Delete file (requires confirmation)
- run_command(command, timeout): Execute shell command

**Security Guidelines:**
- All operations are restricted to workspace directory
- Dangerous operations require user confirmation
- Code containing risky patterns (eval, exec, os.system, etc.) triggers warnings

**Best Practices:**
- Test after every code change
- Read existing code before modifying
- Keep changes focused and incremental
"""


# ──────────────────────────────────────────────────────────
# Helper Functions（已实现，不需要修改）
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


def _format_tool_result(tool_call_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """将工具执行结果转换为 OpenAI tool 消息格式。

    Args:
        tool_call_id: 对应的 tool_call ID（用于关联请求和响应）
        result: execute_tool 的返回值 {"success", "result", "error"}

    Returns:
        {"role": "tool", "tool_call_id": "...", "content": "..."}
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, ensure_ascii=False, default=str),
    }


def _print_verbose(msg: str, config: Config) -> None:
    """verbose 模式下打印调试信息到 stderr。"""
    if config.verbose:
        print(f"[agent] {msg}", file=sys.stderr)


def _print_tool_call(name: str, args: dict) -> None:
    """打印工具调用信息（始终可见）。"""
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"[Tool] {name}({args_str})")


def _print_tool_result(result: dict[str, Any]) -> None:
    """打印工具执行结果（始终可见）。"""
    if result["success"]:
        output = str(result["result"])
        if len(output) > 200:
            output = output[:200] + "..."
        print(f"[Result] {output}")
    else:
        print(f"[Error] {result.get('error', 'Unknown error')}")


def _log_to_file(msg: str, config: Config) -> None:
    """将日志写入配置的日志文件（如果设置了 log_file）。"""
    if config.log_file:
        try:
            with open(config.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError:
            pass  # 日志写入失败不应影响主流程


# ──────────────────────────────────────────────────────────
# Agent Loop（核心部分 — 需要你实现 TODO 标记的代码）
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
    3. 终止条件：无 tool_calls / 达到 max_iterations / 连续失败超限

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

    init_workspace(config.workspace)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    # 初始化计数器
    iteration = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3

    _print_verbose(f"Agent started. Task: {task[:100]}...", config)

    # 主循环
    while iteration < max_iterations:
        iteration += 1
        _print_verbose(f"Starting iteration {iteration}...", config)

        # 调用模型
        try:
            response = call_model(
                messages,
                model_name=config.model,
                api_key=config.api_key,
                api_base=config.api_base
            )
        except Exception as e:
            consecutive_failures += 1
            _print_verbose(f"Model call failed: {e}", config)
            _log_to_file(f"[Iteration {iteration}] Model error: {e}", config)
            
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _print_verbose("Too many consecutive failures.", config)
                return "Agent stopped: too many consecutive failures."
            continue

        # 将 assistant 回复加入消息历史
        messages.append(_format_assistant_message(response))

        # 检查是否有工具调用
        if not response["tool_calls"]:
            _print_verbose("No tool calls, task completed.", config)
            return response["content"] or "Task completed."

        # 执行工具调用
        for tool_call in response["tool_calls"]:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            tool_id = tool_call["id"]

            _print_verbose(f"Executing tool: {tool_name}({tool_args})", config)
            _print_tool_call(tool_name, tool_args)
            _log_to_file(f"[Iteration {iteration}] Tool: {tool_name}({tool_args})", config)

            # TODO (Phase 2): 在这里加 classify_risk 判定
            result = execute_tool(tool_name, tool_args, config=config)

            _print_tool_result(result)
            _print_verbose(
                f"Tool result: success={result['success']}, "
                f"error={result.get('error', '')}",
                config,
            )
            _log_to_file(
                f"[Iteration {iteration}] Result: {result}",
                config
            )

            # 将工具结果加入消息历史
            messages.append(_format_tool_result(tool_id, result))

            # 连续失败计数
            if not result["success"]:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            # 连续失败超限 → 终止
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _print_verbose("Too many consecutive failures.", config)
                return "Agent stopped: too many consecutive failures."

        # 逐轮上下文压缩：保留最近 2 轮工具消息完整，压缩更早的
        messages = compress_round(messages, keep_recent=2)

        # 兜底：极端长对话下逐轮压缩仍不够，做最终截断
        if should_compress(messages, threshold=config.context.max_context_size):
            messages = truncate_compressed(
                messages, keep_recent=config.context.keep_recent_messages
            )
            _print_verbose(
                f"Context truncated to {len(messages)} messages", config
            )

        _print_verbose(f"Iteration {iteration} complete.", config)

    # 达到 max_iterations
    _print_verbose(f"Reached max iterations ({max_iterations}).", config)
    return "Agent stopped: reached maximum iterations."


# ──────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────

def main():
    """命令行入口。

    用法:
        python -m guardcode "你的编程任务"
        python -m guardcode "写一个冒泡排序" --workspace ./myproject --model gpt-4-turbo
    """
    import argparse

    parser = argparse.ArgumentParser(description="GuardCode Agent")
    parser.add_argument("task", help="Programming task for the agent")
    parser.add_argument("--workspace", default=".", help="Workspace directory")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max loop iterations")
    parser.add_argument("--model", default=None, help="Model name override (default: from config)")
    parser.add_argument("--config", default=None, help="Path to config file")
    args = parser.parse_args()

    config = load_config(config_file=args.config, workspace=args.workspace)
    if args.model:
        config.model = args.model
    result = run_agent_loop(args.task, config=config, max_iterations=args.max_iterations)
    print(result)


if __name__ == "__main__":
    main()
