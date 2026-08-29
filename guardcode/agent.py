"""
GuardCode Agent 核心循环

这是 agent 的核心模块。以下代码提供了框架和接口参考，
标有 TODO 的部分需要你自己实现。

参考文档：c:\Users\Administrator\.trae-cn\work\6a912b0a30b254be79a400d8\agent_loop_guide.md
"""

import json
import sys
from typing import Any

from .config import Config, load_config
from .model import call_model
from .tools.base import execute_tool, get_tool_schemas
from .workspace import init_workspace


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
# Agent Loop
# ──────────────────────────────────────────────────────────

def run_agent_loop(
    task: str,
    config: Config | None = None,
    max_iterations: int = 50,
) -> str:
    """
    Agent 主循环。

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

    # TODO: 初始化你的计数器
    # iteration = 0
    # consecutive_failures = 0
    # MAX_CONSECUTIVE_FAILURES = 3

    # ── 2. 主循环 ──────────────────────────────────────────
    # TODO: 实现 while 循环
    # 提示：
    #   while iteration < max_iterations:
    #       # 2a. 检查上下文长度（Phase 3 再做，先跳过）
    #
    #       # 2b. 调用模型
    #       # response = call_model(messages, model_name=config.model, ...)
    #       # response 格式: {"content": str|None, "tool_calls": [{"id", "name", "arguments"}]}
    #
    #       # 2c. 把 assistant 回复加入消息历史
    #       #    需要构造 OpenAI 格式的 assistant message
    #       #    如果有 tool_calls，格式是：
    #       #    {"role": "assistant", "content": response["content"], "tool_calls": [...]}
    #       #    如果没有 tool_calls，格式是：
    #       #    {"role": "assistant", "content": response["content"]}
    #
    #       # 2d. 检查终止条件：没有 tool_calls → 任务完成
    #       #    if not response["tool_calls"]:
    #       #        return response["content"] or "Task completed."
    #
    #       # 2e. 有 tool_calls → 逐个执行
    #       #    for tool_call in response["tool_calls"]:
    #       #        # TODO: 在这里加 classify_risk 判定（Phase 2）
    #       #        # TODO: dangerous 时暂停等用户确认
    #       #        result = execute_tool(tool_call["name"], tool_call["arguments"])
    #       #
    #       #        # 把工具结果加入消息历史
    #       #        # 格式: {"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result)}
    #       #
    #       #        # TODO: 连续失败计数
    #       #        # if not result["success"]:
    #       #        #     consecutive_failures += 1
    #       #        # else:
    #       #        #     consecutive_failures = 0
    #       #        #
    #       #        # TODO: 连续失败超限 → 终止
    #       #        # if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
    #       #     return "Agent stopped: too many consecutive failures."
    #
    #       # 2f. iteration += 1

    # TODO: 达到 max_iterations 时的处理
    # return "Agent stopped: reached maximum iterations."

    pass  # 删除这行，替换为你的实现


# ──────────────────────────────────────────────────────────
# CLI 入口（可选，也可以放在 __main__.py 里）
# ──────────────────────────────────────────────────────────

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="GuardCode Agent")
    parser.add_argument("task", help="Programming task for the agent")
    parser.add_argument("--workspace", default=".", help="Workspace directory")
    parser.add_argument("--max-iterations", type=int, default=50, help="Max loop iterations")
    args = parser.parse_args()

    config = load_config(workspace=args.workspace)
    result = run_agent_loop(args.task, config=config, max_iterations=args.max_iterations)
    print(result)


if __name__ == "__main__":
    main()
