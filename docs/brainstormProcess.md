# (cursor claude-sonnet-4-6)
## prompt:
/add-plugin superpowers

我想构建一个编程智能体（coding agent），项目名叫 GuardCode Agent。

背景：这是南京大学软件学院预推免考核项目。要求从零自己实现一个编程智能体，
通过与大语言模型交互，能自主读写文件、执行命令，完成编程任务。
类似简化的 Claude Code / Codex / OpenCode。

硬性约束：
1. 不允许使用任何 agent 框架/SDK（LangChain、LlamaIndex、OpenAI Agents SDK、
   Claude Agent SDK、AutoGen、CrewAI 等）
2. 允许使用模型厂商的 API 客户端库和原生 tool calling 接口
3. 不得依赖 API 服务端托管的代码执行或文件工具
4. 以下逻辑必须自己实现：对话历史与上下文管理、工具定义与本地执行、
   模型输出解析、循环终止条件、错误处理

我的定位：面向可信软件开发的编程智能体，在基础代码生成之上加入：
- 安全检查（静态风险检测，轻量级规则匹配即可）
- 执行反馈（测试驱动修复，跑测试 → 看结果 → 修正）

我希望项目小而精：核心功能完整可用，不堆砌功能。编程语言用 Python。
API key 通过环境变量提供。

请帮我 brainstorm 这个项目的设计。

## answer:
我会先了解当前项目的已有约束和文档，再逐步收敛目标、边界与技术方案。这个阶段只做设计讨论，不修改代码；我会一次问一个关键问题。

我已经确认当前工作区主要包含 Superpowers 插件和一份尚未展开内容的设计流程文档；项目本身还没有 Python 实现。因此，我们可以从核心闭环开始设计，而不是迁就已有架构。

第一个需要确定的是模型接口范围。你希望 GuardCode Agent：

只支持一种模型 API，例如 OpenAI-compatible Chat Completions / Responses API，先把核心 agent loop 做扎实；
抽象一个统一模型接口，首期支持 OpenAI-compatible API，同时方便以后接入 Anthropic、Gemini 等；
首期直接支持两种模型厂商，从一开始验证多厂商适配。
我建议选 1：对于考核项目，小而精更重要，统一模型适配层可以作为一个很薄的内部接口，但不必首期实现多个厂商。你倾向哪个范围？

## prompt:
选 1。只支持 OpenAI-compatible Chat Completions API。把核心 agent loop 做扎实

## answer:
确定，首期只接入 OpenAI-compatible Chat Completions API，并把厂商客户端限制在普通 HTTP/API 调用层；模型适配接口保持很薄，避免引入多厂商抽象。下一步需要确定智能体一次任务的执行边界，这会直接影响工具设计和安全模型。你希望 GuardCode Agent 的任务工作区采用哪种方式？

显式指定工作目录
启动时传入 --workspace PATH，所有文件操作和命令执行都限制在该目录内。适合强调安全性和可控性。

当前目录作为工作区
Agent 启动后把当前目录作为根目录，只允许访问其内部文件。使用最自然，但需要处理路径逃逸、符号链接和命令工作目录问题。

临时隔离工作区
每次任务复制或创建一个临时目录，Agent 只在副本中修改，任务结束后由用户检查并决定是否应用变更。安全性最好，但实现和用户体验更复杂。

我建议选 2：交互简单，同时可以通过路径规范化、工作目录固定、命令超时和危险命令拦截实现足够清晰的安全边界。

## prompt:
选 1，但默认值为当前目录。

具体来说：启动时接受 --workspace PATH 参数，
不传则默认为 os.getcwd()。无论哪种方式，
启动时立即 resolve 成绝对路径（含 realpath 消解符号链接），
之后所有文件操作和命令执行都以这个 resolved path 作为安全边界。

理由：
1. 安全边界显式且唯一——resolve 一次，全程校验，不用处理
   "命令里 cd 了导致工作目录漂移"的问题
2. 对 GuardCode 的定位（可信软件开发）来说，
   显式 workspace 是更可辩护的安全模型
3. 实现反而更简单：一个 resolved path 做基准，
   所有路径用它校验，不需要动态跟踪当前目录
4. Claude Code、Codex 都是这么做的——显式项目目录

## answer:
确定工作区模型：

启动参数：--workspace PATH
缺省值：os.getcwd()
启动时执行一次 Path(path).resolve()，得到唯一的绝对、真实路径
后续文件工具和命令工具都以该路径为基准
文件路径必须经过规范化后确认位于 workspace 内，拒绝路径逃逸
命令统一以 resolved workspace 作为 cwd，不根据命令中的 cd 修改 Agent 的安全边界
符号链接需要按真实路径重新校验，避免通过链接访问 workspace 外部内容
这个边界很适合写进项目的核心安全不变量：Agent 可以操作 workspace 内的资源，但不能通过路径、符号链接或命令工作目录绕出 workspace。

下一个关键问题是工具调用的授权策略。对于 read_file、write_file、list_files、run_command，你希望采用哪种交互方式？

全部自动执行
Agent 获得任务后直接读写文件、运行命令。实现最简单，适合演示自主闭环，但安全性较弱。

按风险分级授权
读取和列目录自动执行；写文件和运行命令默认需要用户确认，或者只对被判定为低风险的操作自动放行。更符合可信软件开发定位。

默认自动执行，危险操作确认
普通写文件和测试命令自动执行；删除文件、安装依赖、版本控制写操作、可能破坏数据的命令需要确认。交互体验和安全性之间更平衡。

我建议选 3。它保留 coding agent 的连续工作体验，同时可以明确展示“命令风险识别 → 用户确认 → 执行”的可信控制点。

## prompt:
选 3。默认自动执行，危险操作需确认。

具体风险分级规则：

自动放行：
- read_file / list_files：始终自动
- write_file（新建或修改）：自动
- run_command 中的安全命令：自动
  安全命令白名单：pytest、python、ruff、flake8、mypy、
  git status、git diff、git log、ls、cat、echo

需要用户确认：
- delete_file：始终确认
- run_command 中的危险命令：确认
  危险命令模式：rm/del、git push、git reset --hard、
  pip install、npm install、sudo、chmod、curl/wget、mkfs、dd

实现方式：一个类似 classify_risk(operation) 这样的函数，
对命令做正则模式匹配，返回 safe / dangerous。

## answer:
我已经收敛到工作区和工具授权策略了。接下来我会把核心能力再压一层：是做成单轮工具调用，还是允许模型在一次任务里反复发起工具调用并迭代到结束。明白。现在核心约束已经清楚了：

工作区：--workspace PATH，默认 os.getcwd()，启动时 resolve() 成唯一边界
工具策略：读、列、写自动；安全命令自动；删除和危险命令确认
风险判定：classify_risk(operation) + 正则规则匹配，返回 safe / dangerous
下一步要决定 agent 的执行循环形式，这会决定对话管理和终止条件怎么做。你希望它是：

单轮工具调用
模型一次只产出一个 tool call，执行后把结果再送回模型，直到结束。实现最简单，调试也直观。

多轮连续工具调用
模型在一次消息里可以连续提出多个工具调用，agent 依次执行再回传结果。更像真实 coding agent，但循环控制更复杂。

有限步迭代
允许多轮连续工具调用，但设置最大步数、最大失败次数、以及无新工具请求时自动终止。最适合做成“能用且不失控”的核心 loop。

我建议选 3。它最符合你说的“核心 loop 做扎实”，而且终止条件、错误处理、上下文截断都能一起落地。

## prompt:
我没觉得2的循环控制有多复杂，在我看来不过是在for循环里顺次执行工具，遇到要判定操作安全级别的随时暂停询问用户，每个工具执行前做一次
workspace 路径校验防止逃逸。如果我说的没错，用2。
然后其实我希望用户能在设置里自定义放行一些每次都要问的操作classify_risk 的判定优先级变为类似这样的流程：
1. 命中 always_block → 直接拒绝
2. 命中 auto_approve → 自动放行
3. 命中内置 DANGEROUS_PATTERNS → 需确认
4. 命中内置 SAFE_PATTERNS → 自动放行
5. 以上都不匹配 → 默认需确认（保守策略）

## answer:
你说得对，我过度复杂化了。多轮连续工具调用在一次 response 里执行多个 tool calls，确实就是 for tool_call in response.tool_calls 的顺序执行，每个工具执行前做路径校验和风险判定，需要确认就暂停等待。

确定执行循环模型：

多轮连续工具调用：模型一次可以返回多个 tool_calls，依次执行
每个工具执行前：路径校验（文件工具）+ 风险判定（所有工具）
需要确认时：暂停循环，打印待执行操作，等待用户输入 y/n，拒绝则跳过该工具但继续后续工具
所有工具执行完毕后，将结果数组作为 tool role 消息送回模型
确定风险判定优先级：

def classify_risk(operation: dict) -> RiskLevel:
    # operation = {"tool": "run_command", "args": {"command": "..."}}
    
    # 1. always_block（用户配置）：直接拒绝
    if matches_user_block_list(operation):
        return RiskLevel.BLOCKED
    
    # 2. auto_approve（用户配置）：自动放行
    if matches_user_approve_list(operation):
        return RiskLevel.SAFE
    
    # 3. 内置 DANGEROUS_PATTERNS：需确认
    if matches_dangerous_patterns(operation):
        return RiskLevel.DANGEROUS
    
    # 4. 内置 SAFE_PATTERNS：自动放行
    if matches_safe_patterns(operation):
        return RiskLevel.SAFE
    
    # 5. 默认保守：需确认
    return RiskLevel.DANGEROUS
用户配置可以放在 ~/.guardcode/config.json 或 workspace 下的 .guardcode.json，包含 always_block 和auto_approve 两个命令/操作模式列表。

现在核心循环已经明确了，下一个问题是"测试驱动修复"的闭环怎么实现。你希望：

Agent 主动识别并运行测试
Agent 自己判断何时该跑测试（例如写完代码后），自动调用 run_command("pytest")，根据结果决定是否修复。

用户手动触发测试反馈
提供专门的工具 run_tests_and_fix()，用户在任务描述里说"写完后跑测试并修复"，或者 Agent 完成初版后用户手动触发。

测试作为普通命令，反馈靠 prompt 引导
测试就是 run_command("pytest")，没有专门工具；通过 system prompt 引导 Agent"写完代码后应该运行测试，失败了要修复"。

我建议选 3。测试只是命令，"测试驱动修复"是通过 prompt 引导的工作流，不需要单独工具。这样核心工具集保持简洁，同时你可以在 system prompt 里明确写"完成代码修改后应该运行相关测试，如果失败则分析输出并修复"。

## prompt:
选 3，但 system prompt 里的测试流程要更智能：
代码修改或落地前：
1. 检查有没有测试文件
2. 如果有，找到测试，代码落地后运行，拿到结果后决定下一轮迭代到什么状态（但是有轮次上线，并且支持用户自定义，单任务默认为5）
3. 如果没有，可以的话尽量使用 TDD（测试驱动开发）

关键：agent 自己判断该用哪种验证方式——有测试就跑测试，没测试就写测试或用替代验证。不需要专门工具，list_files + run_command 就够了，
智能行为来自 system prompt 的流程指令。

## answer:
确定测试驱动修复的实现方式：

测试即命令：通过 list_files 发现测试 + run_command 执行，不需要专门工具

System prompt 引导流程：

代码修改前/后的验证策略：
1. 使用 list_files 检查是否存在测试文件（test_*.py, *_test.py, tests/ 目录）
2. 如果有测试：
   - 代码落地后立即运行相关测试
   - 根据测试输出决定是否需要修复
   - 最多迭代 N 轮（默认 5，可通过 --max-iterations 配置）
3. 如果没有测试：
   - 优先采用 TDD：先写测试，再写实现，验证通过
   - 若不适合 TDD，则通过其他方式验证（如手动检查输出、简单执行）
修复循环终止条件：
- 测试全部通过
- 达到最大迭代次数
- 连续两轮输出无变化（检测到循环）
迭代控制：在 agent loop 层面记录当前任务的迭代次数，超过 --max-iterations（默认 5）后强制终止并报告状态

现在核心工作流已经完整了。最后一个关键问题是"安全检查"的实现边界。你说的"静态风险检测，轻量级规则匹配"，我需要确认范围：

代码级静态检查
在 write_file 写入代码文件（.py）时，对内容做模式匹配：检测 eval()、exec()、os.system() 等危险调用，匹配到则警告或阻止写入。

命令级风险检测
只在 run_command 时做风险判定（已经有了），不检查代码内容。代码是用户工作区的一部分，由用户自己审查。

两者都做
写代码时检查危险模式并警告；执行命令时做风险判定并确认。双重防护。

我建议选 1。"可信软件开发"的核心差异化就是代码内容的静态风险检测，而命令风险判定你已经有了。实现也简单：正则匹配几个危险 API 模式，写入前扫描并给出警告（允许用户选择忽略）。

## prompt:
你也说了2我已经做了，选1（其实也相当于选3）

## answer:
确定安全检查的实现：

代码级静态检查：在 write_file 写入 Python 文件时，对内容做模式匹配

检测规则（正则匹配）：

危险函数调用：eval(), exec(), compile(), __import__()
不安全的系统调用：os.system(), subprocess.call/run with shell=True
文件系统危险操作：os.remove(), shutil.rmtree(), pathlib.Path.unlink()
网络请求：urllib.request, requests.get/post（可选，看你想管多严）
处理流程：

write_file(path, content) →
  1. 路径校验（workspace 边界）
  2. 如果是 .py 文件：静态风险扫描
  3. 如果发现风险模式：
     - 打印警告信息（匹配到的模式 + 行号）
     - 询问用户：[c]ontinue / [m]odify / [a]bort
     - 用户确认后才写入
  4. 执行写入
配置化：风险模式可以放在配置文件里，用户可以调整严格程度或添加自定义规则

现在核心能力边界已经清晰了。我再确认一下整体架构的最后一个关键点：上下文管理和历史截断。

对话历史会快速增长（每轮工具调用 + 结果都要加入历史），你希望：

固定窗口截断
保留最近 N 条消息，超出后从头部删除。简单，但可能丢失任务上下文。

智能摘要压缩
当历史超长时，调用模型总结前面的对话，用摘要替换，保留最近几轮完整消息。更智能但增加复杂度和 API 调用。

Token 计数 + 渐进截断
用 tiktoken 估算 token 数，接近模型上下文窗口时触发截断；保留 system prompt + 最近 N 轮完整消息，中间部分做轻量摘要或直接丢弃。

我建议选 3。它在简单和实用之间平衡最好：tiktoken 估算成本低，保留最近消息确保当前任务上下文完整，首期可以先做直接截断，后续再优化成摘要。

## prompt:
用字符估算 + 三层处理：

1. 永留：system prompt + 第一条 user message（任务描述）
2. 智能压缩：中间旧消息调模型做摘要，用 2-3 句话替换
3. 保留：最近 K 条消息完整不动

触发条件：字符估算总量超过窗口 80% 时触发。
因为 128K 窗口很大，截断很少发生，摘要的 API 调用成本可接受。

摘要失败兜底：如果摘要 API 调用失败，退化为直接丢弃中间消息
+ 插入透明标记"[截断 N 条消息，摘要失败]"。
不因为摘要失败而阻塞 agent loop。

不用 tiktoken：兼容端点可能接 DeepSeek/Kimi，
tiktoken 对它们不准。字符估算模型无关，只用于判断何时触发。

## answer:
确定上下文管理策略：

三层结构：

永久保留：system prompt + 第一条 user message（任务描述）
智能压缩：中间旧消息调用模型摘要，用 2-3 句话替换一批消息
完整保留：最近 K 条消息（默认 10 条？）
触发条件：

字符估算：sum(len(json.dumps(msg)) for msg in messages)
阈值：总字符数超过 MAX_CONTEXT_CHARS * 0.8
对于 128K token 模型，字符阈值约为 128000 * 4 * 0.8 = 409600 字符（粗略估算）
压缩流程：

def compress_history(messages):
    permanent = messages[0:2]  # system + 第一条 user
    recent = messages[-K:]      # 最近 K 条
    middle = messages[2:-K]     # 中间部分
    
    if len(middle) > 0:
        summary = call_model_for_summary(middle)
        if summary:
            compressed = [{"role": "system", "content": f"[Earlier conversation summary]: {summary}"}]
        else:
            # 摘要失败兜底
            compressed = [{"role": "system", "content": f"[截断 {len(middle)} 条消息，摘要失败]"}]
    else:
        compressed = []
    
    return permanent + compressed + recent
摘要 prompt：

Summarize the following conversation history in 2-3 sentences, 
focusing on: completed tasks, current progress, and key decisions.
现在核心架构的所有关键决策点都确定了。让我整理一下完整的设计，然后确认是否还有遗漏的部分，之后我会呈现完整设计供你审阅。

在此之前，还有一个工程细节需要确认：错误处理和用户可见性。当工具执行失败（文件不存在、命令报错、权限拒绝）时，你希望：

工具返回错误给模型，让模型处理
工具执行失败时返回 {"success": false, "error": "..."} 给模型，模型看到错误后决定下一步（重试、换方案、告诉用户）。

记录日志 + 返回错误给模型
除了返回给模型，同时在终端打印错误日志（带时间戳和上下文），方便调试和事后分析。

三层可见性：模型 + 用户终端 + 日志文件
错误返回给模型；同时在终端实时打印；另外写入 ~/.guardcode/logs/ 持久化。

我建议选 2。终端实时输出对调试很重要，日志文件对首期不是必需（可以后续加），先保持简单。

## prompt:
选 3。三层可见性。

1. 模型层：工具返回 {"success": false, "error": "..."} 给模型，
   模型决定下一步（重试/换方案/告诉用户）
2. 终端层：实时打印 agent 的每一步动作——
   工具调用、参数、结果、错误、安全警告、确认提示
   用 rich 库做格式化（颜色、对齐）
3. 日志层：写入 ~/.guardcode/logs/agent.log，持久化记录
   格式：时间戳 + 级别 + 工具名 + 消息

日志兜底：写日志失败时不阻塞 agent loop，try/except 静默跳过。

不只是错误要可见——agent 的所有动作都要可见：
- 调了什么工具、传了什么参数
- 工具返回了什么结果
- 安全扫描发现了什么
- 风险判定结果（safe/dangerous）
- 用户确认提示
- 截断触发记录

## answer:
确定三层可见性机制：

1. 模型层：工具返回统一格式

{
    "success": True/False,
    "result": "..." if success else None,
    "error": "..." if not success else None
}
2. 终端层：实时打印所有 agent 动作（使用 rich 库）

工具调用：[blue]→ Tool:[/blue] {tool_name}({args})
工具结果：[green]✓ Result:[/green] {result} / [red]✗ Error:[/red] {error}
安全扫描：[yellow]⚠ Security:[/yellow] Found risky pattern: {pattern} at line {n}
风险判定：[yellow]🛡 Risk:[/yellow] {operation} → {SAFE/DANGEROUS}
用户确认：[magenta]❓ Confirm:[/magenta] {operation} [y/n]
上下文截断：[cyan]📊 Context:[/cyan] Compressed {n} messages, summary generated
模型调用：[dim]💬 Model:[/dim] Sending {n} messages, {chars} chars
3. 日志层：持久化到 ~/.guardcode/logs/agent.log

格式：{timestamp} | {level} | {tool} | {message}
示例：2024-01-15 10:23:45 | INFO | run_command | Executing: pytest tests/
      2024-01-15 10:23:46 | WARN | write_file | Risky pattern: eval() at line 42
      2024-01-15 10:23:47 | ERROR | write_file | Permission denied: /etc/passwd
实现细节：

使用 Python logging 模块 + rich.logging.RichHandler 统一处理
日志写入失败时 try/except 静默跳过，不阻塞主流程
日志文件按日期轮转（可选）：agent-{date}.log
现在所有关键决策点都确定了。让我整理完整的系统设计：

GuardCode Agent 完整设计
核心定位
面向可信软件开发的编程智能体，在代码生成基础上加入安全检查和测试驱动修复。

硬性约束
不使用任何 agent 框架/SDK
只用模型厂商 API 客户端库和原生 tool calling
自己实现：对话管理、工具执行、上下文管理、循环控制、错误处理
技术栈
语言：Python 3.10+
模型 API：OpenAI-compatible Chat Completions（支持 OpenAI / DeepSeek / Kimi 等兼容端点）
依赖库：
openai：模型 API 客户端
rich：终端格式化输出
标准库：pathlib, subprocess, logging, json, re
系统架构
guardcode/
├── __init__.py
├── __main__.py          # 入口：CLI 参数解析
├── agent.py             # 核心：Agent loop
├── tools/
│   ├── __init__.py
│   ├── base.py          # 工具基类和注册机制
│   ├── file_tools.py    # read_file, write_file, list_files, delete_file
│   └── command_tools.py # run_command
├── security/
│   ├── __init__.py
│   ├── risk_classifier.py  # classify_risk()
│   └── code_scanner.py     # 静态代码风险扫描
├── context/
│   ├── __init__.py
│   ├── manager.py       # 上下文管理和压缩
│   └── summarizer.py    # 调用模型做摘要
├── ui/
│   ├── __init__.py
│   └── console.py       # Rich 格式化输出
└── config.py            # 配置加载和管理
核心组件设计
1. 工作区（Workspace）
启动参数：--workspace PATH，默认 os.getcwd()
启动时执行：workspace = Path(path).resolve()（消解符号链接）
所有文件操作和命令执行以此为安全边界
路径校验：
def is_safe_path(target: Path, workspace: Path) -> bool:
    resolved = target.resolve()
    return resolved.is_relative_to(workspace)
2. 工具系统（Tools）
文件工具：

read_file(path: str) -> str
write_file(path: str, content: str) -> bool
list_files(directory: str = ".") -> list[str]
delete_file(path: str) -> bool
命令工具：

run_command(command: str, timeout: int = 30) -> dict
工具执行流程：

for tool_call in response.tool_calls:
    # 1. 解析工具和参数
    tool_name, args = parse_tool_call(tool_call)
    
    # 2. 路径校验（文件工具）
    if is_file_tool(tool_name):
        if not is_safe_path(args['path'], workspace):
            return error("Path outside workspace")
    
    # 3. 风险判定
    risk = classify_risk(tool_name, args)
    if risk == RiskLevel.BLOCKED:
        return error("Operation blocked by policy")
    if risk == RiskLevel.DANGEROUS:
        if not confirm_user(f"Execute {tool_name}({args})?"):
            continue  # 跳过此工具，继续执行后续
    
    # 4. 执行工具
    result = execute_tool(tool_name, args)
    
    # 5. 记录和可见性
    log_tool_execution(tool_name, args, result)
    print_to_console(tool_name, args, result)
3. 风险分级（Security）
classify_risk() 优先级：

def classify_risk(tool_name: str, args: dict) -> RiskLevel:
    operation = {"tool": tool_name, "args": args}
    
    # 1. always_block（用户配置）
    if matches(operation, config.always_block):
        return RiskLevel.BLOCKED
    
    # 2. auto_approve（用户配置）
    if matches(operation, config.auto_approve):
        return RiskLevel.SAFE
    
    # 3. 内置 DANGEROUS_PATTERNS
    if matches(operation, DANGEROUS_PATTERNS):
        return RiskLevel.DANGEROUS
    
    # 4. 内置 SAFE_PATTERNS
    if matches(operation, SAFE_PATTERNS):
        return RiskLevel.SAFE
    
    # 5. 默认保守
    return RiskLevel.DANGEROUS
安全命令白名单：

SAFE_PATTERNS = [
    r'^pytest\b',
    r'^python\s+',
    r'^ruff\b',
    r'^flake8\b',
    r'^mypy\b',
    r'^git\s+(status|diff|log)\b',
    r'^(ls|cat|echo|pwd|which)\b',
]
危险命令模式：

DANGEROUS_PATTERNS = [
    r'\brm\b.*-rf?\b',
    r'\bdel\b',
    r'^git\s+(push|reset\s+--hard)\b',
    r'\b(pip|npm|apt|yum)\s+install\b',
    r'\bsudo\b',
    r'\bchmod\b',
    r'\b(curl|wget)\b.*(\||>)',
    r'\b(mkfs|dd)\b',
]
代码级静态检查（write_file 时触发）：

CODE_RISK_PATTERNS = {
    'eval': r'\beval\s*\(',
    'exec': r'\bexec\s*\(',
    'compile': r'\bcompile\s*\(',
    'os.system': r'\bos\.system\s*\(',
    'subprocess_shell': r'subprocess\.(call|run|Popen).*shell\s*=\s*True',
    'file_delete': r'\b(os\.remove|shutil\.rmtree|Path.*\.unlink)\s*\(',
}
4. Agent Loop
def run_agent_loop(task: str, max_iterations: int = 5):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task}
    ]
    
    iteration = 0
    while iteration < max_iterations:
        # 1. 检查上下文长度，必要时压缩
        if should_compress(messages):
            messages = compress_history(messages)
        
        # 2. 调用模型
        response = call_model(messages)
        messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
        
        # 3. 如果没有工具调用，任务完成
        if not response.tool_calls:
            print_final_response(response.content)
            break
        
        # 4. 执行所有工具调用
        tool_results = []
        for tool_call in response.tool_calls:
            result = execute_tool_with_safety(tool_call)
            tool_results.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": json.dumps(result)
            })
        
        messages.extend(tool_results)
        iteration += 1
    
    if iteration >= max_iterations:
        print_warning(f"达到最大迭代次数 {max_iterations}")
5. 上下文管理
三层结构：

def compress_history(messages: list) -> list:
    permanent = messages[0:2]  # system + 第一条 user
    recent = messages[-K:]      # 最近 K 条（默认 10）
    middle = messages[2:-K]
    
    if len(middle) > 0:
        try:
            summary = call_model_for_summary(middle)
            compressed = [{"role": "system", "content": f"[Earlier conversation summary]: {summary}"}]
        except Exception:
            compressed = [{"role": "system", "content": f"[截断 {len(middle)} 条消息，摘要失败]"}]
    else:
        compressed = []
    
    return permanent + compressed + recent
触发条件：

def should_compress(messages: list) -> bool:
    total_chars = sum(len(json.dumps(msg)) for msg in messages)
    # 对于 128K token 模型，约 409600 字符触发
    return total_chars > MAX_CONTEXT_CHARS * 0.8
6. System Prompt
You are GuardCode Agent, a coding assistant focused on trustworthy software development.
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
- Use version control (git) when available
- Keep changes focused and incremental
7. 三层可见性
终端输出（Rich 格式化）：

from rich.console import Console
from rich.panel import Panel
console = Console()
# 工具调用
console.print("[blue]→ Tool:[/blue] write_file(path='main.py', ...)")
# 安全警告
console.print(Panel(
    "[yellow]⚠ Security Warning[/yellow]\n"
    "Found risky pattern: eval() at line 42\n"
    "[c]ontinue / [m]odify / [a]bort?",
    border_style="yellow"
))
# 结果
console.print("[green]✓ Result:[/green] File written successfully")
日志持久化：

import logging
from rich.logging import RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        RichHandler(rich_tracebacks=True),
        logging.FileHandler("~/.guardcode/logs/agent.log")
    ]
)
配置文件
~/.guardcode/config.json 或 {workspace}/.guardcode.json：

{
    "model": "gpt-4-turbo",
    "api_base": "https://api.openai.com/v1",
    "max_iterations": 5,
    "max_context_chars": 409600,
    "recent_messages_keep": 10,
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
CLI 接口
# 基本使用
guardcode "implement quicksort in Python with tests"
# 指定工作区
guardcode --workspace /path/to/project "fix the bug in main.py"
# 自定义迭代次数
guardcode --max-iterations 10 "refactor authentication module"
# 指定模型
guardcode --model gpt-4o "write a REST API server"
实现路线图
Phase 1：核心闭环（2-3 天）


 项目结构搭建

 工具系统：文件工具 + 命令工具

 Agent loop：模型调用 + 工具执行

 工作区边界：路径校验

 基础终端输出
Phase 2：安全机制（1-2 天）


 风险分级：classify_risk()

 代码静态扫描

 用户确认流程

 配置文件加载
Phase 3：智能化（1-2 天）


 上下文压缩和摘要

 System prompt 优化（TDD 流程引导）

 迭代终止条件完善
Phase 4：工程化（1 天）


 Rich 格式化输出

 日志持久化

 错误处理完善

 CLI 参数解析
这个设计涵盖了所有我们讨论的决策点。请审阅，看是否有需要调整或补充的地方？