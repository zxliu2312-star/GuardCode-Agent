"""
GuardCode Agent API 适配层

将同步的 run_agent_loop 适配为事件驱动的 WebSocket 会话，
支持 4 种工作模式：PLAN / WORK / FEEDBACK / RESEARCH。

设计原则：后端零侵入——不修改 guardcode/ 下任何代码，
通过 monkey-patch + 事件队列接入。
"""

import builtins
import json
import threading
import uuid
from datetime import datetime
from queue import Queue, Empty
from typing import Any

from guardcode.config import load_config
from guardcode.workspace import init_workspace
from guardcode.tools.base import _tool_registry, execute_tool, get_tool_schemas
from guardcode.security.user_confirm import confirm_operation
from guardcode.model import call_model_stream

# 确保工具被注册
from guardcode.tools import file_tools  # noqa: F401
from guardcode.tools import command_tools  # noqa: F401

# 需要被 monkey-patch 的原始函数
import guardcode.ui.console as console_mod
import guardcode.tools.base as base_mod
import guardcode.tools.file_tools as file_tools_mod
import guardcode.security.user_confirm as user_confirm_mod
import guardcode.model as model_mod
import guardcode.agent as agent_mod


# ──────────────────────────────────────────────────────────
# 工作模式常量
# ──────────────────────────────────────────────────────────

MODE_PLAN = "PLAN"
MODE_WORK = "WORK"
MODE_FEEDBACK = "FEEDBACK"
MODE_RESEARCH = "RESEARCH"

# RESEARCH 模式下允许的工具（只读）
READONLY_TOOLS = {"read_file", "list_files"}

# FEEDBACK 模式下需要暂停的工具（写操作）
FEEDBACK_PAUSE_TOOLS = {"write_file", "delete_file", "run_command"}


def _timestamp() -> str:
    """生成 ISO 格式时间戳"""
    return datetime.now().isoformat()


# ──────────────────────────────────────────────────────────
# PLAN 模式：create_plan 工具
# ──────────────────────────────────────────────────────────

_plan_session_ref = None  # 当前使用 create_plan 的 AgentSession


def _create_plan_func(steps: list, summary: str = "") -> dict:
    """create_plan 工具的实现。

    Agent 调用此工具提交计划，工具会阻塞等待用户审批。
    """
    if _plan_session_ref is None:
        return {"success": False, "result": "", "error": "No active plan session"}

    plan = {"steps": steps, "summary": summary}

    # 推送计划到事件队列
    _plan_session_ref.event_queue.put({
        "type": "plan_created",
        "plan": plan,
        "timestamp": _timestamp(),
    })

    # 阻塞等待用户审批结果
    try:
        approval = _plan_session_ref.plan_queue.get(timeout=300)  # 5 分钟超时
    except Empty:
        return {"success": False, "result": "", "error": "Plan approval timeout"}

    if approval.get("rejected"):
        # 用户拒绝，Agent 需要重新规划
        feedback = approval.get("feedback", "")
        return {
            "success": True,
            "result": f"Plan rejected by user. Feedback: {feedback}. Please revise the plan.",
            "error": "",
        }

    # 用户批准（可能编辑了步骤）
    approved_plan = approval.get("plan", plan)
    _plan_session_ref.approved_plan = approved_plan

    # 推送模式切换事件
    _plan_session_ref.event_queue.put({
        "type": "mode_changed",
        "from": MODE_PLAN,
        "to": MODE_WORK,
        "timestamp": _timestamp(),
    })
    _plan_session_ref.mode = MODE_WORK

    return {
        "success": True,
        "result": f"Plan approved. Proceeding with {len(approved_plan.get('steps', []))} steps.",
        "error": "",
    }


def _register_plan_tool():
    """注册 create_plan 工具"""
    _tool_registry["create_plan"] = {
        "name": "create_plan",
        "description": "Submit a structured plan for user approval before executing. Use this in PLAN mode to break down complex tasks into steps.",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "Step number"},
                            "action": {"type": "string", "description": "Tool action: read_file, write_file, run_command, etc."},
                            "target": {"type": "string", "description": "Target file or command"},
                            "purpose": {"type": "string", "description": "Why this step is needed"},
                        },
                        "required": ["id", "action", "target", "purpose"],
                    },
                    "description": "List of planned steps",
                },
                "summary": {"type": "string", "description": "Brief summary of the plan"},
            },
            "required": ["steps", "summary"],
        },
        "function": _create_plan_func,
    }


def _unregister_plan_tool():
    """移除 create_plan 工具"""
    if "create_plan" in _tool_registry:
        del _tool_registry["create_plan"]


# ──────────────────────────────────────────────────────────
# AgentSession：核心适配器
# ──────────────────────────────────────────────────────────

class AgentSession:
    """将同步的 run_agent_loop 适配为事件驱动的 WebSocket 会话。"""

    def __init__(self, session_id: str, workspace: str, mode: str = MODE_WORK):
        self.session_id = session_id
        self.workspace = workspace
        self.mode = mode
        self.event_queue: Queue = Queue()
        self.confirm_queue: Queue = Queue()
        self._whitelist: list[str] = []
        self.plan_queue: Queue = Queue()
        self.feedback_queue: Queue = Queue()
        self.thread: threading.Thread | None = None
        self.is_running = False
        self.is_stopped = False
        self.messages: list[dict] = []
        self.approved_plan: dict | None = None
        self._original_functions: dict = {}
        self._original_system_prompt: str | None = None

    def start(self, task: str, model: str | None = None, api_base: str | None = None, api_key: str | None = None):
        """在后台线程启动 Agent loop。"""
        self.is_running = True
        self.is_stopped = False
        self.thread = threading.Thread(
            target=self._run_agent,
            args=(task, model, api_base, api_key),
            daemon=True,
        )
        self.thread.start()

    def _run_agent(self, task: str, model: str | None, api_base: str | None, api_key: str | None = None):
        """线程目标函数：运行 agent loop，事件推入队列。"""
        try:
            # 1. 加载配置
            config = load_config(workspace=self.workspace)
            # 显式设置 config.workspace，防止 agent.py 中的 init_workspace(config.workspace)
            # 使用默认值 "." 导致工作区逃逸到项目根目录
            config.workspace = self.workspace or "."
            if model:
                config.model = model
            if api_base:
                config.api_base = api_base
            if api_key:
                config.api_key = api_key

            # 2. 初始化工作区（仅在有工作区时）
            if self.workspace:
                init_workspace(self.workspace)

            # 3. 保存原始函数（只保存存在的）
            self._original_functions = {}
            if hasattr(console_mod, 'print_tool_call'):
                self._original_functions["print_tool_call"] = console_mod.print_tool_call
            if hasattr(console_mod, 'print_tool_result'):
                self._original_functions["print_tool_result"] = console_mod.print_tool_result
            if hasattr(console_mod, 'print_risk_warning'):
                self._original_functions["print_risk_warning"] = console_mod.print_risk_warning
            if hasattr(console_mod, 'print_confirm_prompt'):
                self._original_functions["print_confirm_prompt"] = console_mod.print_confirm_prompt
            if hasattr(console_mod, 'print_context_compress'):
                self._original_functions["print_context_compress"] = console_mod.print_context_compress
            if hasattr(console_mod, 'print_final_response'):
                self._original_functions["print_final_response"] = console_mod.print_final_response
            if hasattr(console_mod, 'print_error'):
                self._original_functions["print_error"] = console_mod.print_error
            if hasattr(console_mod, 'print_info'):
                self._original_functions["print_info"] = console_mod.print_info
            if hasattr(console_mod, 'print_model_call'):
                self._original_functions["print_model_call"] = console_mod.print_model_call
            if hasattr(console_mod, 'print_blocked'):
                self._original_functions["print_blocked"] = console_mod.print_blocked
            if hasattr(user_confirm_mod, 'confirm_operation'):
                self._original_functions["confirm_operation"] = user_confirm_mod.confirm_operation
            if hasattr(base_mod, 'confirm_operation'):
                self._original_functions["base_confirm_operation"] = base_mod.confirm_operation
            if hasattr(base_mod, 'execute_tool'):
                self._original_functions["execute_tool"] = base_mod.execute_tool
            if hasattr(base_mod, 'get_tool_schemas'):
                self._original_functions["get_tool_schemas"] = base_mod.get_tool_schemas
            self._original_functions["input"] = builtins.input

            # 4. Monkey-patch print 函数为事件发射器
            # 保存 agent_mod 上的直接导入引用（from .ui.console import ...）
            for fn_name in ['print_tool_call', 'print_tool_result', 'print_risk_warning',
                            'print_confirm_prompt', 'print_context_compress',
                            'print_final_response', 'print_error', 'print_info',
                            'print_model_call', 'print_blocked']:
                if hasattr(agent_mod, fn_name):
                    self._original_functions[f"agent_{fn_name}"] = getattr(agent_mod, fn_name)

            console_mod.print_tool_call = self._make_print_tool_call()
            console_mod.print_tool_result = self._make_print_tool_result()
            console_mod.print_risk_warning = self._make_print_risk_warning()
            console_mod.print_confirm_prompt = self._make_print_confirm_prompt()
            console_mod.print_context_compress = self._make_print_context_compress()
            console_mod.print_final_response = self._make_print_final_response()
            console_mod.print_error = self._make_print_error()
            console_mod.print_info = self._make_print_info()
            console_mod.print_model_call = self._make_print_model_call()
            console_mod.print_blocked = self._make_print_blocked()

            # 同步 patch agent_mod 上的引用（agent.py 通过 from import 导入了这些函数）
            for fn_name in ['print_tool_call', 'print_tool_result', 'print_risk_warning',
                            'print_confirm_prompt', 'print_context_compress',
                            'print_final_response', 'print_error', 'print_info',
                            'print_model_call', 'print_blocked']:
                if hasattr(console_mod, fn_name):
                    setattr(agent_mod, fn_name, getattr(console_mod, fn_name))

            # 5. Monkey-patch confirm_operation 为 WebSocket 交互
            user_confirm_mod.confirm_operation = self._make_confirm_operation()
            base_mod.confirm_operation = user_confirm_mod.confirm_operation

            # 6. Monkey-patch input 为自动继续（用于 file_tools 中的代码风险确认）
            builtins.input = self._make_input()

            # 7. Monkey-patch call_model_with_retry 为流式版本
            self._original_functions["call_model_with_retry"] = agent_mod.call_model_with_retry
            agent_mod.call_model_with_retry = self._make_streaming_model_call()

            # 7.5 无工作区模式：过滤掉所有工具，仅保留对话能力
            if not self.workspace:
                base_mod.get_tool_schemas = self._make_conversation_only_tool_schemas()
                agent_mod.get_tool_schemas = self._make_conversation_only_tool_schemas()

            # 8. 根据工作模式进行适配
            if self.mode == MODE_PLAN:
                # 注册 create_plan 工具
                global _plan_session_ref
                _plan_session_ref = self
                _register_plan_tool()
                # Monkey-patch execute_tool：create_plan 跳过风险检查直接执行
                # （classify_risk 对未知工具默认判为 DANGEROUS，会触发 confirm_operation 阻断流程）
                # 同时 patch base_mod 和 agent_mod（agent.py 通过 from import 导入了独立引用）
                plan_execute = self._make_plan_execute_tool()
                base_mod.execute_tool = plan_execute
                agent_mod.execute_tool = plan_execute

            elif self.mode == MODE_FEEDBACK:
                # Monkey-patch execute_tool 在写操作前暂停
                # 同时 patch base_mod 和 agent_mod
                feedback_execute = self._make_feedback_execute_tool()
                base_mod.execute_tool = feedback_execute
                agent_mod.execute_tool = feedback_execute

            elif self.mode == MODE_RESEARCH:
                # Monkey-patch get_tool_schemas 过滤写工具
                # 同时 patch agent.py 中导入的引用
                research_schemas = self._make_research_tool_schemas()
                base_mod.get_tool_schemas = research_schemas
                agent_mod.get_tool_schemas = research_schemas

            # 8. 运行 agent loop
            from guardcode.agent import run_agent_loop

            # 加载启用的规则并注入到 system prompt
            from api import database as db
            rules = db.list_rules()
            enabled_rules = [r for r in rules if r.get("is_enabled")]
            # 始终保存原始 prompt，以便后续模式注入和恢复
            self._original_system_prompt = agent_mod.SYSTEM_PROMPT
            new_prompt = agent_mod.SYSTEM_PROMPT
            if enabled_rules:
                rules_text = "\n\n".join(
                    f"## Rule: {r['name']}\n{r['content']}" for r in enabled_rules
                )
                new_prompt = f"## Additional Rules\n\n{rules_text}\n\n" + new_prompt
            if not self.workspace:
                new_prompt = (
                    "## CONVERSATION ONLY MODE\n"
                    "No workspace is selected. You CANNOT read, write, or execute files. "
                    "You can only have a conversation with the user, answer questions, "
                    "write code snippets, and provide guidance.\n\n"
                    + new_prompt
                )
            agent_mod.SYSTEM_PROMPT = new_prompt

            # RESEARCH 模式：修改 system prompt
            if self.mode == MODE_RESEARCH:
                agent_mod.SYSTEM_PROMPT = agent_mod.SYSTEM_PROMPT + (
                    "\n\n## RESEARCH MODE\n"
                    "You are in RESEARCH mode. You can only read files and list directories. "
                    "You CANNOT write, delete, or execute commands. "
                    "Your goal is to investigate and analyze the codebase, then provide a "
                    "detailed research report with findings and recommendations."
                )

            # PLAN 模式：修改 system prompt，强制 agent 先提交计划
            if self.mode == MODE_PLAN:
                agent_mod.SYSTEM_PROMPT = agent_mod.SYSTEM_PROMPT + (
                    "\n\n## PLAN MODE\n"
                    "You are in PLAN mode. Before executing any tools to modify the workspace, "
                    "you MUST first call the `create_plan` tool to submit a structured plan for "
                    "user approval.\n\n"
                    "Workflow:\n"
                    "1. If needed, use read-only tools (read_file, list_files) to investigate "
                    "the codebase and understand the task.\n"
                    "2. Call `create_plan` with a list of steps and a summary. Each step must "
                    "include: id (integer), action (tool name), target (file path or command), "
                    "and purpose (why this step is needed).\n"
                    "3. WAIT for user approval. The user may edit, approve, or reject the plan.\n"
                    "4. After approval, execute the approved steps using the available tools.\n"
                    "5. After all steps are complete, provide a summary of what was done.\n\n"
                    "IMPORTANT: Do NOT execute write_file, delete_file, or run_command before "
                    "the plan is approved. The create_plan call is mandatory."
                )

            result = run_agent_loop(task, config=config)

            # 如果是 done 事件还没发（run_agent_loop 返回但没调用 print_final_response）
            if self.is_running and not self.is_stopped:
                self.event_queue.put({
                    "type": "done",
                    "content": result,
                    "timestamp": _timestamp(),
                })

        except Exception as e:
            self.event_queue.put({
                "type": "error",
                "message": f"Agent error: {str(e)}",
                "timestamp": _timestamp(),
            })
        finally:
            # 恢复原始函数
            self._restore_functions()
            self.is_running = False

    def _restore_functions(self):
        """恢复所有 monkey-patch 的原始函数"""
        orig = self._original_functions
        if not orig:
            return

        if "print_tool_call" in orig:
            console_mod.print_tool_call = orig["print_tool_call"]
        if "print_tool_result" in orig:
            console_mod.print_tool_result = orig["print_tool_result"]
        if "print_risk_warning" in orig:
            console_mod.print_risk_warning = orig["print_risk_warning"]
        if "print_confirm_prompt" in orig:
            console_mod.print_confirm_prompt = orig["print_confirm_prompt"]
        if "print_context_compress" in orig:
            console_mod.print_context_compress = orig["print_context_compress"]
        if "print_final_response" in orig:
            console_mod.print_final_response = orig["print_final_response"]
        if "print_error" in orig:
            console_mod.print_error = orig["print_error"]
        if "print_info" in orig:
            console_mod.print_info = orig["print_info"]
        if "print_model_call" in orig:
            console_mod.print_model_call = orig["print_model_call"]
        if "print_blocked" in orig:
            console_mod.print_blocked = orig["print_blocked"]

        # 恢复 agent_mod 上的直接导入引用
        for fn_name in ['print_tool_call', 'print_tool_result', 'print_risk_warning',
                        'print_confirm_prompt', 'print_context_compress',
                        'print_final_response', 'print_error', 'print_info',
                        'print_model_call', 'print_blocked']:
            key = f"agent_{fn_name}"
            if key in orig:
                setattr(agent_mod, fn_name, orig[key])

        if "confirm_operation" in orig:
            user_confirm_mod.confirm_operation = orig["confirm_operation"]
        if "base_confirm_operation" in orig:
            base_mod.confirm_operation = orig["base_confirm_operation"]
        if "execute_tool" in orig:
            base_mod.execute_tool = orig["execute_tool"]
            # 同步恢复 agent_mod 上的直接导入引用
            agent_mod.execute_tool = orig["execute_tool"]
        if "get_tool_schemas" in orig:
            base_mod.get_tool_schemas = orig["get_tool_schemas"]
            # 同步恢复 agent_mod 上的直接导入引用
            agent_mod.get_tool_schemas = orig["get_tool_schemas"]
        if "input" in orig:
            builtins.input = orig["input"]

        # 恢复流式模型调用
        if "call_model_with_retry" in orig:
            agent_mod.call_model_with_retry = orig["call_model_with_retry"]

        # 恢复 system prompt（规则注入和 RESEARCH 模式修改）
        if self._original_system_prompt is not None:
            agent_mod.SYSTEM_PROMPT = self._original_system_prompt
            self._original_system_prompt = None

        # 移除 create_plan 工具
        _unregister_plan_tool()

        global _plan_session_ref
        _plan_session_ref = None

    # ──────────────────────────────────────────────────────────
    # 事件发射器工厂方法
    # ──────────────────────────────────────────────────────────

    def _make_print_tool_call(self):
        def patched(tool_name, args):
            self._last_tool_name = tool_name
            self.event_queue.put({
                "type": "tool_call",
                "tool": tool_name,
                "args": args,
                "risk_level": "safe",
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_tool_result(self):
        def patched(result):
            tool_name = getattr(self, '_last_tool_name', 'unknown')
            success = result.get("success", True) if isinstance(result, dict) else True
            error = result.get("error") if isinstance(result, dict) else None
            self.event_queue.put({
                "type": "tool_result",
                "tool": tool_name,
                "result": result,
                "success": success,
                "error": error,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_risk_warning(self):
        def patched(risks):
            if risks:
                self.event_queue.put({
                    "type": "risk_warning",
                    "risks": risks,
                    "timestamp": _timestamp(),
                })
        return patched

    def _make_print_confirm_prompt(self):
        def patched(tool_name, args):
            # confirm_request 事件由 _make_confirm_operation 发出
            pass
        return patched

    def _make_print_context_compress(self):
        def patched(original_count, new_count):
            self.event_queue.put({
                "type": "context_compress",
                "original_count": original_count,
                "compressed_count": new_count,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_final_response(self):
        def patched(content):
            self.event_queue.put({
                "type": "done",
                "content": content,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_error(self):
        def patched(message):
            self.event_queue.put({
                "type": "error",
                "message": message,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_info(self):
        def patched(message):
            self.event_queue.put({
                "type": "info",
                "message": message,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_model_call(self):
        def patched(message_count, total_chars):
            self.event_queue.put({
                "type": "model_call",
                "message_count": message_count,
                "total_chars": total_chars,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_print_blocked(self):
        def patched(tool_name, args):
            self.event_queue.put({
                "type": "blocked",
                "tool": tool_name,
                "args": args,
                "timestamp": _timestamp(),
            })
        return patched

    def _make_input(self):
        """Monkey-patch input() 为 WebSocket 交互（用于 file_tools 中的代码风险确认）"""
        def patched(prompt=""):
            request_id = str(uuid.uuid4())[:8]
            self.event_queue.put({
                "type": "confirm_request",
                "request_id": request_id,
                "tool": "write_file",
                "args": {"prompt": prompt},
                "message": "检测到代码安全风险，是否继续写入？",
                "timestamp": _timestamp(),
            })
            try:
                response = self.confirm_queue.get(timeout=300)
                if response.get("approved"):
                    return "c"  # continue
                else:
                    return "a"  # abort
            except Empty:
                return "a"  # 超时自动中止
        return patched

    def _make_streaming_model_call(self):
        """Monkey-patch call_model_with_retry 为流式版本，发射打字机事件"""
        original_call = self._original_functions.get("call_model_with_retry")

        def patched(messages, model_name=None, api_key=None, api_base=None, max_retries=3):
            """流式调用模型，逐块发射事件"""
            import time
            last_error = None

            for attempt in range(max_retries):
                try:
                    # 发射模型开始事件
                    self.event_queue.put({
                        "type": "llm_start",
                        "model": model_name or "unknown",
                        "message_count": len(messages),
                        "timestamp": _timestamp(),
                    })

                    full_content = ""
                    tool_calls = []
                    finish_reason = None

                    # 使用流式 API
                    for chunk in call_model_stream(
                        messages,
                        model_name=model_name,
                        api_key=api_key,
                        api_base=api_base,
                    ):
                        if self.is_stopped:
                            break

                        if chunk["type"] == "content":
                            content_piece = chunk["content"]
                            full_content += content_piece
                            # 发射打字机事件
                            self.event_queue.put({
                                "type": "llm_chunk",
                                "content": content_piece,
                                "timestamp": _timestamp(),
                            })
                        elif chunk["type"] == "done":
                            finish_reason = chunk["finish_reason"]
                            tool_calls = chunk.get("tool_calls", [])

                    # 发射模型完成事件
                    self.event_queue.put({
                        "type": "llm_done",
                        "content": full_content,
                        "tool_calls": tool_calls,
                        "finish_reason": finish_reason,
                        "timestamp": _timestamp(),
                    })

                    return {
                        "content": full_content if full_content else None,
                        "tool_calls": tool_calls,
                        "finish_reason": finish_reason,
                    }

                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        self.event_queue.put({
                            "type": "info",
                            "message": f"模型调用失败（第{attempt + 1}次），{wait_time}秒后重试...",
                            "timestamp": _timestamp(),
                        })
                        time.sleep(wait_time)

            raise last_error

        return patched

    def _make_confirm_operation(self):
        """Monkey-patch confirm_operation 为 WebSocket 交互"""
        def patched(tool_name, args):
            # 检查白名单：命中则自动放行
            if self._is_in_whitelist(tool_name, args):
                return True
            request_id = str(uuid.uuid4())[:8]
            self.event_queue.put({
                "type": "confirm_request",
                "request_id": request_id,
                "tool": tool_name,
                "args": args,
                "risk_level": "dangerous",
                "message": f"确认执行 {tool_name}？",
                "timestamp": _timestamp(),
            })
            try:
                response = self.confirm_queue.get(timeout=300)
                approved = response.get("approved", False)
                if approved and response.get("whitelist"):
                    self._add_to_whitelist(tool_name, args)
                return approved
            except Empty:
                return False
        return patched

    def _get_whitelist_pattern(self, tool_name: str, args: dict) -> str:
        """生成白名单匹配模式"""
        if tool_name in ("run_command", "execute_command"):
            cmd = args.get("command", "")
            # 取命令的第一个词作为模式（如 "git" from "git push"）
            parts = cmd.split()
            return parts[0] if parts else cmd
        return tool_name

    def _is_in_whitelist(self, tool_name: str, args: dict) -> bool:
        """检查是否在白名单中"""
        pattern = self._get_whitelist_pattern(tool_name, args)
        return pattern in self._whitelist

    def _add_to_whitelist(self, tool_name: str, args: dict):
        """将工具调用模式加入白名单"""
        pattern = self._get_whitelist_pattern(tool_name, args)
        if pattern and pattern not in self._whitelist:
            self._whitelist.append(pattern)

    def _make_plan_execute_tool(self):
        """PLAN 模式：create_plan 直接执行，写工具在计划批准前被拒绝。

        - create_plan：跳过风险检查直接执行（否则会被判为 DANGEROUS 阻断流程）
        - 只读工具（read_file, list_files 等）：正常执行，允许 agent 调查代码库
        - 写工具（write_file, delete_file, run_command 等）：计划批准前拒绝，
          返回错误提醒 agent 先调用 create_plan 提交计划
        """
        original_execute = self._original_functions["execute_tool"]
        # PLAN 模式下允许的只读工具
        readonly_tools = {"read_file", "list_files", "list_directory",
                          "search_files", "grep", "glob"}

        def patched(name, args, config=None):
            if name == "create_plan":
                # 直接执行 create_plan，不经过风险分级
                tool_func = _tool_registry[name]["function"]
                try:
                    result = tool_func(**args)
                    if isinstance(result, dict) and "success" in result:
                        return result
                    return {"success": True, "result": result, "error": ""}
                except Exception as e:
                    return {"success": False, "result": None, "error": str(e)}

            # 计划已批准，恢复正常执行
            if self.approved_plan is not None:
                return original_execute(name, args, config)

            # 只读工具允许执行（用于调查代码库）
            if name in readonly_tools:
                return original_execute(name, args, config)

            # 写工具在计划批准前被拒绝
            return {
                "success": False,
                "result": None,
                "error": (
                    f"工具 '{name}' 在 PLAN 模式下被拒绝。"
                    "你必须先调用 create_plan 工具提交计划，"
                    "等待用户审批后才能执行写操作。"
                    "请先调查代码库（使用 read_file, list_files 等只读工具），"
                    "然后调用 create_plan 提交计划。"
                ),
            }

        return patched

    def _make_feedback_execute_tool(self):
        """FEEDBACK 模式：在写操作前暂停等待反馈"""
        original_execute = self._original_functions["execute_tool"]

        def patched(name, args, config=None):
            if name in FEEDBACK_PAUSE_TOOLS and not self.is_stopped:
                request_id = str(uuid.uuid4())[:8]
                self.event_queue.put({
                    "type": "feedback_request",
                    "request_id": request_id,
                    "tool": name,
                    "args": args,
                    "message": f"即将执行 {name}",
                    "timestamp": _timestamp(),
                })
                # 阻塞等待用户反馈
                try:
                    response = self.feedback_queue.get(timeout=300)
                except Empty:
                    return {
                        "success": False,
                        "result": "",
                        "error": "Feedback timeout",
                    }

                action = response.get("action", "continue")
                if action == "stop":
                    self.is_stopped = True
                    return {
                        "success": False,
                        "result": "",
                        "error": "Operation stopped by user",
                    }
                elif action == "adjust":
                    # 用户提供了反馈，Agent 需要重新考虑
                    feedback = response.get("feedback", "")
                    return {
                        "success": False,
                        "result": "",
                        "error": f"User feedback: {feedback}. Please adjust and retry.",
                    }
                # action == "continue"，继续执行

            return original_execute(name, args, config)
        return patched

    def _make_research_tool_schemas(self):
        """RESEARCH 模式：过滤写工具"""
        original_get_schemas = self._original_functions["get_tool_schemas"]

        def patched():
            all_schemas = original_get_schemas()
            return [
                s for s in all_schemas
                if s["function"]["name"] in READONLY_TOOLS
            ]
        return patched

    def _make_conversation_only_tool_schemas(self):
        """无工作区模式：返回空工具列表，仅对话"""
        def patched():
            return []
        return patched

    # ──────────────────────────────────────────────────────────
    # 用户响应方法（由 WebSocket 路由调用）
    # ──────────────────────────────────────────────────────────

    def confirm(self, request_id: str, approved: bool, whitelist: bool = False):
        """响应用户确认请求"""
        self.confirm_queue.put({"request_id": request_id, "approved": approved, "whitelist": whitelist})

    def approve_plan(self, plan: dict):
        """批准计划（PLAN 模式）"""
        self.plan_queue.put({"rejected": False, "plan": plan})

    def reject_plan(self, feedback: str = ""):
        """拒绝计划（PLAN 模式）"""
        self.plan_queue.put({"rejected": True, "feedback": feedback})

    def feedback(self, request_id: str, action: str, feedback_text: str = ""):
        """反馈响应（FEEDBACK 模式）"""
        self.feedback_queue.put({
            "request_id": request_id,
            "action": action,
            "feedback": feedback_text,
        })

    def stop(self):
        """停止 agent"""
        self.is_stopped = True
        self.is_running = False
        # 向所有队列推入停止信号
        self.confirm_queue.put({"approved": False})
        self.plan_queue.put({"rejected": True, "feedback": "Stopped by user"})
        self.feedback_queue.put({"action": "stop", "feedback": ""})
        self.event_queue.put({"type": "stopped", "timestamp": _timestamp()})

    def get_events(self) -> list[dict]:
        """非阻塞获取所有待处理事件"""
        events = []
        while True:
            try:
                event = self.event_queue.get_nowait()
                events.append(event)
            except Empty:
                break
        return events


# ──────────────────────────────────────────────────────────
# 全局会话管理
# ──────────────────────────────────────────────────────────

_sessions: dict[str, AgentSession] = {}


def create_session(workspace: str, mode: str = MODE_WORK) -> AgentSession:
    """创建新的 Agent 会话"""
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    session = AgentSession(session_id, workspace, mode)
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> AgentSession | None:
    """获取会话"""
    return _sessions.get(session_id)


def list_sessions() -> list[dict]:
    """列出所有会话"""
    return [
        {
            "session_id": s.session_id,
            "workspace": s.workspace,
            "mode": s.mode,
            "is_running": s.is_running,
        }
        for s in _sessions.values()
    ]
