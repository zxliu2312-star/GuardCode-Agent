# GuardCode Agent - 设计规格说明

## 1. 项目概述

### 1.1 项目定位
GuardCode Agent 是一个面向可信软件开发的编程智能体，通过与大语言模型交互，自主完成代码生成、安全检查和测试驱动修复。

### 1.2 核心差异化
- **安全检查**：静态代码风险扫描，检测危险 API 调用
- **执行反馈**：测试驱动修复循环（运行测试 → 分析结果 → 自动修复）
- **可信控制**：命令风险分级，危险操作需用户确认

### 1.3 项目背景
南京大学软件学院预推免考核项目。要求从零实现编程智能体，类似简化版的 Claude Code / Codex。

---

## 2. 硬性约束

### 2.1 技术限制
1. **禁止使用 Agent 框架/SDK**：不得使用 LangChain、LlamaIndex、OpenAI Agents SDK、Claude Agent SDK、AutoGen、CrewAI 等
2. **允许使用**：模型厂商的 API 客户端库（如 `openai`）和原生 tool calling 接口
3. **禁止依赖服务端工具**：不得使用 API 服务端托管的代码执行或文件操作能力
4. **必须自己实现**：
   - 对话历史与上下文管理
   - 工具定义与本地执行
   - 模型输出解析
   - 循环终止条件
   - 错误处理

### 2.2 范围约束
- **小而精**：核心功能完整可用，不堆砌功能
- **单模型支持**：首期只支持 OpenAI-compatible Chat Completions API
- **Python 实现**：使用 Python 3.10+
- **环境变量配置**：API key 通过环境变量提供

---

## 3. 系统架构

### 3.1 技术栈
- **语言**：Python 3.10+
- **模型 API**：OpenAI-compatible Chat Completions（支持 OpenAI / DeepSeek / Kimi 等）
- **核心依赖**：
  - `openai`：模型 API 客户端
  - `rich`：终端格式化输出
  - 标准库：`pathlib`, `subprocess`, `logging`, `json`, `re`

### 3.2 目录结构
```
guardcode/
├── __init__.py
├── __main__.py              # CLI 入口
├── agent.py                 # Agent 核心循环
├── tools/
│   ├── __init__.py
│   ├── base.py              # 工具基类和注册
│   ├── file_tools.py        # 文件操作工具
│   └── command_tools.py     # 命令执行工具
├── security/
│   ├── __init__.py
│   ├── risk_classifier.py   # 风险分级
│   └── code_scanner.py      # 代码静态扫描
├── context/
│   ├── __init__.py
│   ├── manager.py           # 上下文大小估算
│   └── compressor.py        # 两级上下文压缩
├── ui/
│   ├── __init__.py
│   └── console.py           # Rich 输出
└── config.py                # 配置管理
```

### 3.3 三层架构
```
┌──────────────────────────────────────────────────┐
│ Layer 1: Execution State (Current Turn)          │
│ - response["tool_calls"] ← 执行来源              │
│ - 绝对不可压缩                                    │
│ - ✅ 当前已正确实现                               │
└──────────────────────────────────────────────────┘
                    ↓ 执行完成后
┌──────────────────────────────────────────────────┐
│ Layer 2: Context (messages list)                 │
│ - 对话历史（易失性记忆）                          │
│ - 可压缩策略：                                    │
│   ✓ 写后失效：write_file 后旧 read_file 失效     │
│   ✓ 按需重读：旧 read_file 压缩为元信息          │
│   ✓ 保留工作集：最近 N 轮完整保留                 │
│   ✓ 两级压缩：规则压缩 + LLM 摘要（可选）         │
└──────────────────────────────────────────────────┘
                    ↓ Source of Truth
┌──────────────────────────────────────────────────┐
│ Layer 3: Workspace (file system)                 │
│ - 真实文件内容                                    │
│ - ✅ 已正确实现                                   │
│ - read_file 每次直接读磁盘                        │
└──────────────────────────────────────────────────┘
```

关键决策：
- **无 File Cache 层**：避免一致性问题，依赖操作系统页缓存
- **read_file 每次直接读磁盘**：依赖操作系统页缓存自动优化
- **压缩只修改内存中的 messages**：不触碰 Workspace

---

## 4. 核心功能设计

### 4.1 工作区（Workspace）

#### 4.1.1 定义
- 启动参数：`--workspace PATH`
- 默认值：`os.getcwd()`
- 初始化：`workspace = Path(path).resolve()`（消解符号链接）

#### 4.1.2 安全边界
所有文件操作和命令执行必须限制在 workspace 内。路径校验逻辑：

```python
def is_safe_path(target: Path, workspace: Path) -> bool:
    """检查目标路径是否在工作区内"""
    resolved = target.resolve()  # 消解符号链接
    return resolved.is_relative_to(workspace)
```

#### 4.1.3 安全不变量
**Agent 可以操作 workspace 内的资源，但不能通过路径、符号链接或命令工作目录绕出 workspace。**

---

### 4.2 工具系统（Tools）

#### 4.2.1 工具清单

**文件操作工具**：
- `read_file(path: str) -> str`：读取文件内容
- `write_file(path: str, content: str) -> bool`：创建或覆盖文件
- `list_files(directory: str = ".") -> list[str]`：列出目录内容
- `delete_file(path: str) -> bool`：删除文件（需确认）

**命令执行工具**：
- `run_command(command: str, timeout: int = 30) -> dict`：执行 shell 命令

#### 4.2.2 工具返回格式
统一格式：
```python
{
    "success": True/False,
    "result": "..." if success else None,
    "error": "..." if not success else None
}
```

#### 4.2.3 工具执行流程
```
for tool_call in response.tool_calls:
    1. 解析工具名和参数
    2. 路径校验（文件工具）
    3. 风险判定（所有工具）
    4. 用户确认（危险操作）
    5. 执行工具
    6. 记录和可见性输出
```

---

### 4.3 安全机制

#### 4.3.1 风险分级（Risk Classification）

**优先级流程**：
```python
def classify_risk(tool_name: str, args: dict) -> RiskLevel:
    # 1. always_block（用户配置）→ BLOCKED
    # 2. auto_approve（用户配置）→ SAFE
    # 3. 内置 DANGEROUS_PATTERNS → DANGEROUS
    # 4. 内置 SAFE_PATTERNS → SAFE
    # 5. 默认保守 → DANGEROUS
```

**风险等级**：
- `BLOCKED`：直接拒绝执行
- `DANGEROUS`：需要用户确认
- `SAFE`：自动执行

#### 4.3.2 命令风险规则

**安全命令白名单**（自动放行）：
```python
SAFE_PATTERNS = [
    r'^pytest\b',              # 测试运行
    r'^python\s+',             # Python 执行
    r'^(ruff|flake8|mypy)\b',  # 代码检查
    r'^git\s+(status|diff|log)\b',  # Git 只读操作
    r'^(ls|cat|echo|pwd|which)\b',  # 基础命令
]
```

**危险命令模式**（需要确认）：
```python
DANGEROUS_PATTERNS = [
    r'\brm\b.*-rf?\b',         # 递归删除
    r'\bdel\b',                # Windows 删除
    r'^git\s+(push|reset\s+--hard)\b',  # Git 写操作
    r'\b(pip|npm|apt)\s+install\b',     # 包安装
    r'\bsudo\b',               # 提权
    r'\bchmod\b',              # 权限修改
    r'\b(curl|wget)\b.*(\||>)',        # 管道/重定向
    r'\b(mkfs|dd)\b',          # 磁盘操作
]
```

#### 4.3.3 代码静态扫描

在 `write_file` 写入 `.py` 文件时触发：

**检测规则**：
```python
CODE_RISK_PATTERNS = {
    'eval': r'\beval\s*\(',
    'exec': r'\bexec\s*\(',
    'compile': r'\bcompile\s*\(',
    '__import__': r'\b__import__\s*\(',
    'os.system': r'\bos\.system\s*\(',
    'subprocess_shell': r'subprocess\.(call|run|Popen).*shell\s*=\s*True',
    'file_delete': r'\b(os\.remove|shutil\.rmtree|Path.*\.unlink)\s*\(',
}
```

**处理流程**：
```
write_file(path, content) →
  1. 路径校验
  2. 如果是 .py 文件：静态扫描
  3. 如果发现风险：
     - 打印警告（模式 + 行号）
     - 询问用户：[c]ontinue / [m]odify / [a]bort
     - 确认后才写入
  4. 执行写入
```

---

### 4.4 Agent 循环（Agent Loop）

#### 4.4.1 执行流程
```python
def run_agent_loop(task: str, max_iterations: int = 5):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task}
    ]
    
    iteration = 0
    while iteration < max_iterations:
        # 1. 上下文压缩（下一轮开始前）
        if should_compress(messages):
            messages = compress_history(messages, keep_recent=5)
        
        # 2. 调用模型
        response = call_model(messages)
        
        # 3. Execution State 独立提取
        tool_calls = response["tool_calls"]
        messages.append(_format_assistant_message(response))
        
        # 4. 无工具调用 → 任务完成
        if not tool_calls:
            print_final_response(response["content"])
            break
        
        # 5. 执行所有工具调用（使用独立的 tool_calls，不受压缩影响）
        for tc in tool_calls:
            result = execute_tool_with_safety(tc)
            messages.append(_format_tool_result(tc["id"], tc["name"], result))
        
        iteration += 1
```

#### 4.4.2 终止条件
- 模型不再发起工具调用
- 达到最大迭代次数（默认 5）
- 用户手动中断（Ctrl+C）

#### 4.4.3 多轮工具调用
模型在一次响应中可以返回多个 `tool_calls`，Agent 依次执行：
- 每个工具执行前：路径校验 + 风险判定
- 需要确认时：暂停等待用户输入
- 用户拒绝：跳过该工具，继续执行后续工具
- 所有工具执行完毕后：将结果作为 `tool` role 消息送回模型

---

### 4.5 上下文管理

#### 4.5.1 设计原则
- **Workspace 是 Source of Truth**：文件系统为准，read_file 每次直接读磁盘
- **历史是易失性记忆**：messages 列表可压缩，不保留冗余内容
- **重新读取优于大上下文**：模型需要具体内容时可重新调 read_file

#### 4.5.2 两级压缩架构

**Level 1: 规则压缩（Rule-Based Compression，必须）**

分区结构：
```python
def compress_history(messages, keep_recent=5, use_llm_summary=False):
    # 分区
    permanent = messages[0:2]  # system prompt + 第一条 user task
    middle = messages[2:-keep_recent]  # 可压缩的中间区
    recent = messages[-keep_recent:]  # 工作集：最近 N 条完整保留
    
    if not middle:
        return messages
    
    # Level 1 规则压缩
    compressed_middle = middle
    compressed_middle = _invalidate_outdated_reads(compressed_middle)
    compressed_middle = _compress_large_results(compressed_middle)
    compressed_middle = _compress_tool_call_arguments(compressed_middle)
    
    # Level 2（可选）：如果压缩率不足
    if use_llm_summary:
        original_size = estimate_context_size(middle)
        compressed_size = estimate_context_size(compressed_middle)
        if original_size > 0 and compressed_size / original_size > 0.5:
            summary = _summarize_with_llm(compressed_middle)
            compressed_middle = [{
                "role": "user",
                "content": f"[Previous conversation summary]: {summary}"
            }]
    
    return permanent + compressed_middle + recent
```

**规则 1：写后失效（Write/Delete Invalidation）— 事件驱动**

当文件被 `write_file` 或 `delete_file` 修改后，自动将该文件之前的所有 `read_file` 结果标记为过期。

**与规则 2-4 不同，写后失效是事件驱动的**：在写/删操作成功后立即执行，不等阈值触发。因为文件被修改的那一刻旧内容就已过期，延迟清理只会浪费 token。

```python
# 原始 read_file 结果
{
    "success": True,
    "result": "<50KB 文件内容>",
    "path": "src/main.py"
}

# 压缩后（该文件后续被修改）
{
    "success": True,
    "result": "<file src/main.py was modified later, content outdated>",
    "path": "src/main.py",
    "compressed": True
}
```

**规则 2：按需重读（Lazy Re-reading）**

未被修改的文件，若内容超过阈值（如 500 字符），压缩为元信息：

```python
# 原始 read_file 结果
{
    "success": True,
    "result": "<大型文件内容>",
    "error": ""
}

# 压缩后
{
    "success": True,
    "result": "<content: 12345 chars>",
    "error": "",
    "compressed": True
}
```

**规则 3：压缩大型 tool_calls**

`assistant` 消息中 `write_file` 的大型 `content` 参数压缩为占位符：

```python
# 原始 tool_call
{
    "id": "call-123",
    "function": {
        "name": "write_file",
        "arguments": '{"path": "app.py", "content": "<10KB 代码>"}'
    }
}

# 压缩后
{
    "id": "call-123",
    "function": {
        "name": "write_file",
        "arguments": '{"path": "app.py", "content": "<10240 chars>"}'
    }
}
```

**规则 4：工作集保留（Working Set）**

最近 N 轮（默认 5）的消息完整保留，不压缩。这是模型当前正在处理的热数据。

**Level 2: LLM 摘要（Optional Enhancement）**

当 Level 1 规则压缩释放的空间仍不足时，可选调用 LLM 生成摘要：

```python
# 仅在压缩率不足时启用
if compressed_size / original_size > 0.5:
    summary = _summarize_with_llm(compressed_middle)
    compressed_middle = [{
        "role": "user",
        "content": f"[Previous conversation summary]: {summary}"
    }]
```

**摘要 Prompt（禁止脑补）**：
```
Summarize the following conversation history in 2-3 sentences.
Focus ONLY on:
- What tasks were completed
- What files were read/written
- What commands were executed
- Current progress and state

Do NOT add:
- New suggestions
- Future plans
- Unexecuted steps
```

#### 4.5.3 触发条件
```python
def should_compress(messages: list) -> bool:
    if len(messages) <= 4:
        return False
    
    total_chars = sum(len(json.dumps(msg)) for msg in messages)
    # 对于 128K token 模型，约 409600 字符（粗略估算）
    return total_chars > MAX_CONTEXT_CHARS * 0.8
```

#### 4.5.4 压缩时机

压缩分为两类：**事件驱动**（写后失效）和**阈值驱动**（按需重读、压缩大型 tool_calls、工作集保留）。

```python
# agent.py 主循环
while iteration < max_iterations:
    # ✅ 阈值驱动：在调用模型前检查并压缩
    if should_compress(messages):
        messages = compress_history(messages, keep_recent=config.context.keep_recent_messages)
    
    # 调用模型
    response = call_model(messages)
    
    # ✅ Execution State 独立：tool_calls 从 response 提取
    tool_calls = response["tool_calls"]
    messages.append(_format_assistant_message(response))
    
    # 执行工具（使用独立的 tool_calls，不受压缩影响）
    for tc in tool_calls:
        result = execute_tool(tc["name"], tc["arguments"], config)
        messages.append(_format_tool_result(tc["id"], tc["name"], result, tc["arguments"]))
        
        # ✅ 事件驱动：写/删成功后立即失效旧读取结果
        # 不等阈值触发，因为文件被修改的那一刻旧内容就已过期
        if tc["name"] in ("write_file", "delete_file") and result["success"]:
            path = Path(tc["arguments"].get("path", "")).as_posix()
            if path:
                messages = _invalidate_outdated_reads(messages, {path})

        # ✅ 事件驱动：read_file 成功后压缩旧大型读取结果
        # 模型刚读了新文件，旧的大型读取结果已不需要完整保留
        if tc["name"] == "read_file" and result["success"]:
            messages = _compress_large_results(messages[:-1]) + [messages[-1]]
```

**三类触发机制**：

| 类型 | 触发条件 | 执行操作 | 目的 |
|------|---------|---------|------|
| 写事件驱动 | write_file/delete_file 成功后立即 | `_invalidate_outdated_reads()` | 语义失效，防止模型用过期内容 |
| 读事件驱动 | read_file 成功后立即 | `_compress_large_results()` | 体积压缩，旧大型读取压缩为元信息 |
| 阈值驱动 | `should_compress()` 返回 True | `compress_history()`（全部规则） | 体积压缩，释放上下文空间 |

**关键保证**：
- 事件驱动失效只修改内存中的 `messages`，不触碰 Workspace
- 阈值驱动压缩发生在下一轮开始前
- 当前轮的 `response["tool_calls"]` 已经提取完毕，独立存储
- 三类触发都不影响当前轮的工具执行

#### 4.5.5 幂等性保证

已压缩的消息通过 `"compressed": True` 标记，避免重复压缩：

```python
def _compress_large_results(messages: list) -> list:
    compressed = []
    for msg in messages:
        if msg["role"] == "tool":
            content = json.loads(msg["content"])
            
            # 跳过已压缩的
            if content.get("compressed"):
                compressed.append(msg)
                continue
            
            # 压缩逻辑...
    
    return compressed
```

#### 4.5.6 前置修改：工具结果元信息

当前 tool 消息只有 `tool_call_id` 和 `content`，压缩时需要知道工具名和路径。
解决方案：修改 `_format_tool_result()` 增加元信息：

```python
def _format_tool_result(tool_call_id: str, tool_name: str, result: dict) -> dict:
    """增加 tool_name 参数，在 content 中记录元信息"""
    content = result.copy()
    content["_tool_name"] = tool_name  # 增加元信息
    
    # 对文件操作工具，记录规范化路径
    if tool_name in ("read_file", "write_file", "delete_file"):
        # path 已在 result 中，确保是规范化路径
        pass
    
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(content, ensure_ascii=False, default=str),
    }
```

---

### 4.6 测试驱动修复

#### 4.6.1 设计原则
测试驱动修复通过 System Prompt 引导，不需要专门工具。Agent 使用 `list_files` + `run_command` 实现测试发现和执行。

#### 4.6.2 System Prompt 指令
```markdown
**Core Workflow:**
1. Understand the task and workspace structure
2. Before writing code, check for existing tests using list_files
3. If tests exist:
   - Write/modify code
   - Run relevant tests using run_command
   - If tests fail, analyze output and fix (max 5 iterations by default)
4. If no tests exist:
   - Prefer TDD: write tests first, then implementation
   - Or use alternative verification methods

**Test-Driven Repair Loop:**
- After code changes, immediately run relevant tests
- Analyze test output for failures
- Fix issues based on error messages
- Re-run tests to verify
- Terminate when tests pass or max iterations reached
```

#### 4.6.3 修复循环终止条件
- 所有测试通过
- 达到最大迭代次数（`--max-iterations`，默认 5）
- 连续两轮输出无变化（检测到循环）

---

### 4.7 三层可见性

#### 4.7.1 模型层
工具返回统一格式：
```python
{
    "success": True/False,
    "result": "...",
    "error": "..." if not success else None
}
```

#### 4.7.2 终端层（Rich 格式化）
实时打印所有 Agent 动作：
- 工具调用：`[blue]→ Tool:[/blue] {tool_name}({args})`
- 工具结果：`[green]✓ Result:[/green] {result}`
- 工具错误：`[red]✗ Error:[/red] {error}`
- 安全警告：`[yellow]⚠ Security:[/yellow] Found risky pattern: {pattern} at line {n}`
- 风险判定：`[yellow]🛡 Risk:[/yellow] {operation} → {SAFE/DANGEROUS}`
- 用户确认：`[magenta]❓ Confirm:[/magenta] {operation} [y/n]`
- 上下文压缩：`[cyan]📊 Context:[/cyan] Compressed {n} messages`
- 模型调用：`[dim]💬 Model:[/dim] Sending {n} messages, {chars} chars`

#### 4.7.3 日志层
持久化到 `~/.guardcode/logs/agent.log`：
```
格式：{timestamp} | {level} | {tool} | {message}
示例：
2024-01-15 10:23:45 | INFO | run_command | Executing: pytest tests/
2024-01-15 10:23:46 | WARN | write_file | Risky pattern: eval() at line 42
2024-01-15 10:23:47 | ERROR | write_file | Permission denied: /etc/passwd
```

实现：
```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        RichHandler(rich_tracebacks=True),
        logging.FileHandler(Path.home() / ".guardcode/logs/agent.log")
    ]
)
```

**兜底**：日志写入失败时不阻塞 Agent loop，`try/except` 静默跳过。

---

## 5. 配置系统

### 5.1 配置文件位置
- 全局：`~/.guardcode/config.json`
- 项目：`{workspace}/.guardcode.json`（优先级更高）

### 5.2 配置格式
```json
{
    "model": "gpt-4-turbo",
    "api_base": "https://api.openai.com/v1",
    "max_iterations": 5,
    "max_context_chars": 409600,
    "recent_messages_keep": 5,
    "security": {
        "always_block": [
            "rm -rf /",
            "sudo rm"
        ],
        "auto_approve": [
            "pytest --version",
            "git status"
        ]
    }
}
```

### 5.3 配置项说明
- `model`：模型名称
- `api_base`：API 端点 URL
- `max_iterations`：单任务最大迭代次数
- `max_context_chars`：触发上下文压缩的字符阈值
- `recent_messages_keep`：压缩时保留最近消息数量
- `security.always_block`：强制拒绝的操作列表
- `security.auto_approve`：自动放行的操作列表

---

## 6. CLI 接口

### 6.1 基本用法
```bash
# 基本使用（当前目录作为 workspace）
guardcode "implement quicksort in Python with tests"

# 指定工作区
guardcode --workspace /path/to/project "fix the bug in main.py"

# 自定义迭代次数
guardcode --max-iterations 10 "refactor authentication module"

# 指定模型
guardcode --model gpt-4o "write a REST API server"

# 组合使用
guardcode --workspace ~/projects/myapp --model gpt-4-turbo --max-iterations 8 \
  "add user registration endpoint with validation"
```

### 6.2 参数说明
- `task`：任务描述（位置参数，必需）
- `--workspace PATH`：工作区路径（默认：当前目录）
- `--model NAME`：模型名称（默认：配置文件或 `gpt-4-turbo`）
- `--max-iterations N`：最大迭代次数（默认：5）
- `--api-base URL`：API 端点 URL（默认：配置文件或 OpenAI）
- `--config PATH`：指定配置文件路径

### 6.3 环境变量
- `OPENAI_API_KEY`：OpenAI API 密钥（必需）
- `GUARDCODE_CONFIG`：默认配置文件路径
- `GUARDCODE_LOG_LEVEL`：日志级别（DEBUG/INFO/WARNING/ERROR）

---

## 7. 错误处理

### 7.1 工具执行错误
- 文件不存在 → 返回 `{"success": false, "error": "File not found: {path}"}`
- 权限拒绝 → 返回 `{"success": false, "error": "Permission denied: {path}"}`
- 命令超时 → 返回 `{"success": false, "error": "Command timeout after {n}s"}`
- 路径逃逸 → 返回 `{"success": false, "error": "Path outside workspace: {path}"}`

所有错误返回给模型，由模型决定下一步（重试、换方案、告诉用户）。

### 7.2 模型调用错误
- API 请求失败 → 重试 3 次（指数退避）
- 3 次后仍失败 → 打印错误信息，退出程序
- 上下文摘要失败 → 使用兜底策略（直接截断 + 标记）

### 7.3 用户中断
- Ctrl+C → 捕获 `KeyboardInterrupt`
- 保存当前对话历史到 `~/.guardcode/sessions/{timestamp}.json`
- 打印：任务已中断，对话历史已保存
- 优雅退出

---

## 8. 全局约束

### 8.1 安全约束
1. 所有文件操作必须在 workspace 内
2. 所有命令执行的 `cwd` 必须是 workspace
3. 危险操作必须经过用户确认
4. 代码中的危险模式必须警告用户

### 8.2 性能约束
1. 命令执行默认超时 30 秒
2. 单次模型调用不超过 60 秒
3. 上下文压缩触发阈值：窗口 80%

### 8.3 可用性约束
1. 所有用户交互必须有清晰提示
2. 错误信息必须包含原因和建议
3. 终端输出必须格式化（颜色、对齐）
4. 日志写入失败不影响主流程

---

## 9. 非功能需求

### 9.1 可维护性
- 代码模块化，单一职责
- 工具注册机制支持扩展
- 配置系统支持覆盖

### 9.2 可测试性
- 工具执行逻辑可单独测试
- 风险分级逻辑可单独测试
- 提供测试工具集（mock 模型调用、mock 用户确认）

### 9.3 可扩展性
- 工具系统支持插件化扩展
- 风险规则支持用户自定义
- 上下文管理策略可替换

---

## 10. 术语表

- **Workspace**：Agent 可以操作的文件系统根目录
- **Tool Call**：模型发起的工具调用请求
- **Risk Level**：操作的风险等级（SAFE / DANGEROUS / BLOCKED）
- **Context Compression**：对话历史压缩，保留关键信息
- **Write Invalidation**：写后失效，文件被修改后旧读取结果标记过期
- **Lazy Re-reading**：按需重读，大型结果压缩为元信息，需要时重新读取
- **Working Set**：工作集，最近 N 轮消息完整保留
- **Test-Driven Repair**：运行测试 → 分析失败 → 修复代码的循环
- **Static Code Scan**：对代码内容做正则匹配，检测危险模式
