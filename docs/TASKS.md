# GuardCode Agent - 任务清单

## Phase 1：核心闭环（2-3 天）

### 1.1 项目初始化
- [x] 创建项目目录结构
- [x] 初始化 Git 仓库
- [x] 创建 `requirements.txt`
  - `openai>=1.0.0`
  - `rich>=13.0.0`
- [x] 创建 `.gitignore`
- [x] 创建 `README.md` 基础框架

### 1.2 配置系统
- [x] 实现 `config.py`
  - [x] 定义配置数据结构（dataclass 或 dict）
  - [x] 实现配置文件加载（JSON）
  - [x] 支持环境变量覆盖
  - [x] 提供默认配置
- [x] 创建示例配置文件 `.guardcode.json`

### 1.3 工作区管理
- [x] 实现工作区初始化逻辑
  - [x] 解析 `--workspace` 参数
  - [x] `Path.resolve()` 获取绝对路径
  - [x] 存储为全局状态或传递给工具
- [x] 实现路径校验函数 `validate_path()`
  - [x] 支持相对路径和绝对路径
  - [x] 消解符号链接
  - [x] 检查是否在 workspace 内
  - [x] 返回规范化的 Path 对象

### 1.4 工具系统基础设施
- [x] 实现 `tools/base.py`
  - [x] 定义工具注册装饰器 `@register_tool`
  - [x] 实现工具注册表（dict）
  - [x] 实现 `generate_tool_schema()` 自动生成 OpenAI schema
  - [x] 实现 `get_tool_schemas()` 返回所有工具的 schema
  - [x] 实现 `execute_tool(name, args)` 调用对应工具函数

### 1.5 文件操作工具
- [x] 实现 `tools/file_tools.py`
  - [x] `read_file(path: str) -> dict`
    - [x] 路径校验
    - [x] 读取文件内容
    - [x] 返回统一格式 `{"success": bool, "result": str, "error": str}`
  - [x] `write_file(path: str, content: str) -> dict`
    - [x] 路径校验
    - [x] 创建父目录（如果不存在）
    - [x] 写入文件
    - [x] 返回统一格式
  - [x] `list_files(directory: str = ".") -> dict`
    - [x] 路径校验
    - [x] 列出文件和目录
    - [x] 返回相对路径列表
  - [x] `delete_file(path: str) -> dict`
    - [x] 路径校验
    - [x] 删除文件
    - [x] 返回统一格式

### 1.6 命令执行工具
- [x] 实现 `tools/command_tools.py`
  - [x] `run_command(command: str, timeout: int = 30) -> dict`
    - [x] 设置 `cwd=workspace`
    - [x] 设置 `shell=True`
    - [x] 捕获 stdout 和 stderr
    - [x] 处理超时异常
    - [x] 返回统一格式（包含 exit_code）

### 1.7 模型 API 集成
- [x] 实现模型调用函数（在 `agent.py` 或单独模块）
  - [x] 从环境变量读取 `OPENAI_API_KEY`
  - [x] 配置 `openai.api_base`（支持兼容端点）
  - [x] 实现 `call_model(messages: list) -> response`
  - [x] 解析响应中的 `tool_calls`
  - [x] 处理异常（网络错误、API 错误）

### 1.8 Agent 核心循环
- [x] 实现 `agent.py` 的 `run_agent_loop()`
  - [x] 初始化消息列表（system prompt + user task）
  - [x] 实现主循环（最多 `max_iterations` 次）
  - [x] 调用模型
  - [x] 检查是否有 `tool_calls`
  - [x] 如果没有工具调用，返回最终响应
  - [x] 如果有工具调用，依次执行
  - [x] 将工具结果添加到消息历史
  - [x] 继续下一轮循环
- [x] 编写基础 System Prompt
  - [x] 描述 Agent 角色
  - [x] 列出可用工具
  - [x] 说明工作区限制

### 1.9 CLI 入口
- [x] 实现 `__main__.py`
  - [x] 使用 `argparse` 解析命令行参数
    - [x] `task`（位置参数，必需）
    - [x] `--workspace`（默认：当前目录）
    - [x] `--max-iterations`（默认：50）
    - [x] `--model`（默认：从配置读取）
    - [x] `--config`（配置文件路径）
  - [x] 加载配置
  - [x] 初始化工作区
  - [x] 调用 `run_agent_loop()`
  - [x] 打印最终结果

### 1.10 基础输出
- [x] 实现简单的打印输出
  - [x] 打印工具调用：`[Tool] {name}({args})`
  - [x] 打印工具结果：`[Result] {result}`
  - [x] 打印错误：`[Error] {error}`

### 1.11 验收测试
- [x] 测试任务 1：`guardcode "create a file hello.txt with content 'Hello World'"`
- [x] 测试任务 2：`guardcode "write a Python function to calculate fibonacci in fib.py"`
- [x] 测试任务 3：`guardcode "list all Python files in current directory"`

---

## Phase 2：安全机制（1-2 天）

### 2.1 风险分级规则定义
- [x] 在 `security/risk_classifier.py` 中定义规则
  - [x] `SAFE_PATTERNS`（正则表达式列表）
  - [x] `DANGEROUS_PATTERNS`（正则表达式列表）
  - [x] `RiskLevel` 枚举（SAFE, DANGEROUS, BLOCKED）

### 2.2 风险分级实现
- [x] 实现 `classify_risk(tool_name: str, args: dict, config: dict) -> RiskLevel`
  - [x] 检查 `config.security.always_block`
  - [x] 检查 `config.security.auto_approve`
  - [x] 对于 `run_command`，匹配 `DANGEROUS_PATTERNS`
  - [x] 对于 `run_command`，匹配 `SAFE_PATTERNS`
  - [x] 对于 `delete_file`，始终返回 DANGEROUS
  - [x] 对于其他文件工具，返回 SAFE
  - [x] 默认返回 DANGEROUS（保守策略）

### 2.3 用户确认流程
- [x] 实现 `confirm_operation(tool_name: str, args: dict) -> bool`
  - [x] 打印警告信息
  - [x] 格式化显示工具名和参数
  - [x] 提示用户输入 y/n
  - [x] 返回布尔值

### 2.4 集成风险判定到工具执行
- [x] 修改 `execute_tool()` 函数
  - [x] 执行前调用 `classify_risk()`
  - [x] 如果是 BLOCKED，返回错误
  - [x] 如果是 DANGEROUS，调用 `confirm_operation()`
  - [x] 如果用户拒绝，返回错误或跳过
  - [x] 如果是 SAFE，直接执行

### 2.5 代码静态扫描
- [x] 实现 `security/code_scanner.py`
  - [x] 定义 `CODE_RISK_PATTERNS`（dict，模式名 → 正则）
  - [x] 实现 `scan_python_code(content: str) -> list[dict]`
    - [x] 逐行匹配正则
    - [x] 返回发现的风险列表：`[{"pattern": str, "line": int, "content": str}]`

### 2.6 集成代码扫描到 write_file
- [x] 修改 `write_file()` 函数
  - [x] 检查文件扩展名是否为 `.py`
  - [x] 如果是，调用 `scan_python_code(content)`
  - [x] 如果发现风险，打印警告
  - [x] 询问用户：[c]ontinue / [a]bort
  - [x] 根据用户选择决定是否写入

### 2.7 配置文件扩展
- [x] 扩展配置格式，添加 `security` 字段
  - [x] `security.always_block`（字符串列表）
  - [x] `security.auto_approve`（字符串列表）
- [x] 更新配置加载逻辑
  - [x] 支持全局配置：`~/.guardcode/config.json`
  - [x] 支持项目配置：`{workspace}/.guardcode.json`
  - [x] 合并配置（项目覆盖全局）

### 2.8 验收测试
- [x] 测试危险命令：`guardcode "delete all .pyc files using rm -rf"`
  - [x] 应该触发确认提示
- [x] 测试代码风险：`guardcode "write a script that uses eval()"`
  - [x] 应该显示风险警告
- [x] 测试自定义规则：配置 `auto_approve: ["rm *.pyc"]`，再执行删除
  - [x] 应该自动放行

---

## Phase 3：智能化（1-2 天）

### 3.1 上下文估算
- [x] 实现 `context/manager.py`
  - [x] `estimate_context_size(messages: list) -> int`
    - [x] 使用 `json.dumps()` 序列化每条消息
    - [x] 累加字符数
  - [x] `should_compress(messages: list, threshold: int) -> bool`
    - [x] 比较总字符数与阈值

### 3.2 前置修改：工具结果元信息
- [x] 修改 `_format_tool_result()` 增加 `tool_name` 参数
  - [x] 函数签名改为 `_format_tool_result(tool_call_id, tool_name, result, tool_args)`
  - [x] 在 content JSON 中增加 `_tool_name` 字段
  - [x] 在 content JSON 中增加规范化路径 `_path`（对 read_file/write_file/delete_file）
  - [x] 修改 agent.py 中所有调用点

### 3.3 Context Compression - Level 1（规则压缩）
- [x] 实现 `context/compressor.py`
  - [x] `_find_modified_paths(messages: list) -> set[str]`
    - [x] 扫描历史，找出所有被 write_file/delete_file 成功修改的路径
    - [x] 使用规范化路径匹配（解决 `./src/main.py` vs `src/main.py` 问题）
  - [x] `_invalidate_outdated_reads(messages: list, modified_paths: set) -> list`
    - [x] 遍历 tool 消息，识别 read_file 结果
    - [x] 如果路径在 modified_paths 中，替换为过期标记
    - [x] 添加 `"compressed": True` 标记
    - [x] 跳过已标记 `compressed` 的消息
  - [x] `_compress_large_results(messages: list, threshold: int = 500) -> list`
    - [x] 遍历 tool 消息，识别大型 result
    - [x] 替换为 `<content: N chars>` 元信息
    - [x] 保留 success/error 状态
    - [x] 添加 `"compressed": True` 标记
    - [x] 跳过已标记 `compressed` 的消息
  - [x] `_compress_tool_call_arguments(messages: list, threshold: int = 500) -> list`
    - [x] 遍历 assistant 消息中的 tool_calls
    - [x] 压缩 write_file 的大型 content 参数为 `<N chars>` 占位符
    - [x] 保留工具名和其他小参数
  - [x] `compress_history(messages: list, keep_recent: int = 5, use_llm_summary: bool = False) -> list`
    - [x] 分区：permanent = messages[0:2], middle = messages[2:-keep_recent], recent = messages[-keep_recent:]
    - [x] 消息数不足时直接返回
    - [x] Level 1 规则压缩：依次调用上述四个函数
    - [x] Level 2（可选）：如果压缩率不足 50%，调用 `_summarize_with_llm()`
    - [x] 返回：permanent + compressed_middle + recent

### 3.4 Context Compression - Level 2（LLM 摘要，可选）
- [x] 实现 `_summarize_with_llm(messages: list) -> str`
  - [x] 构造摘要 prompt（禁止脑补：只记录已执行操作，不添加未执行计划）
  - [x] 调用较次模型（如 gpt-3.5-turbo）节省成本
  - [x] 返回摘要内容
  - [x] 异常处理：返回兜底消息 `[Summarization failed]`

### 3.5 集成到 Agent Loop
- [x] 修改 `run_agent_loop()`
  - [x] 阈值驱动：在主循环开始前（调用模型前）检查 `should_compress()`
  - [x] 如果需要压缩，调用 `compress_history()`
  - [x] 打印压缩提示（压缩了多少消息，释放了多少空间）
  - [x] 写事件驱动：write_file/delete_file 成功后立即调用 `_invalidate_outdated_reads()`
  - [x] 确认当前轮的 `response["tool_calls"]` 已独立提取，不受压缩影响
  - [x] 读事件驱动：read_file 后压缩旧的大型读取结果（按需重读提前化）
    - [x] read_file 成功后，对之前的旧 read_file 结果调用 `_compress_large_results()`
    - [x] 保留最新一轮 read_file 完整内容
    - [x] 模型需要旧内容时可重新 read_file

### 3.6 System Prompt 优化
- [x] 编写完整的 System Prompt
  - [x] 角色定位：GuardCode Agent，专注可信软件开发
  - [x] 工具说明：列出每个工具及其用途
  - [x] 测试驱动流程：
    - [x] 使用 list_files 检查测试
    - [x] 如果有测试：修改代码 → 运行测试 → 修复
    - [x] 如果无测试：优先 TDD（先写测试）
  - [x] 安全注意事项：所有操作限制在 workspace 内
  - [x] 最佳实践：增量修改、读取后再修改、使用版本控制

### 3.7 迭代终止条件
- [x] 完善循环终止逻辑
  - [x] 达到 `max_iterations`：打印警告并退出
  - [x] 无工具调用：正常结束
  - [x] 循环检测：连续两轮工具调用相同 → 终止

### 3.8 验收测试
- [x] 测试写后失效：write_file 后旧 read_file 结果被标记过期
- [x] 测试按需重读：大型 result 被压缩为元信息
- [x] 测试工作集保留：最近 N 条消息完整保留
- [x] 测试幂等性：已压缩消息不重复压缩
- [x] 测试压缩不影响执行：当前轮工具执行不受压缩影响
- [x] 测试事件驱动失效：write/delete 成功后立即失效（不等阈值）
- [x] 测试失败写不触发失效
- [x] 测试读事件驱动：read_file 后旧大型读取被压缩
- [x] 测试循环检测：连续两轮相同工具调用 → 终止
- [x] 测试长对话：构造需要多次迭代的任务，观察压缩效果（需真实 API）
- [x] 测试测试驱动修复：`guardcode "fix the bug in calculator.py, tests are in test_calculator.py"`（需真实 API）
  - [x] 观察是否：list_files → read → write → run pytest → 修复 → 再测试
- [x] 测试 TDD 流程：`guardcode "implement a stack with push/pop/peek"`（需真实 API）
  - [x] 观察是否先写测试

---

## Phase 4：工程化（1 天）

### 4.1 Rich 输出模块
- [ ] 创建 `ui/console.py`
  - [ ] 导入 `rich.console.Console` 和 `rich.panel.Panel`
  - [ ] 创建全局 `console` 实例
  - [ ] `print_tool_call(tool_name, args)`：蓝色，带 → 图标
  - [ ] `print_tool_result(result)`：绿色 ✓ 或红色 ✗
  - [ ] `print_risk_warning(risks)`：黄色 Panel，显示风险列表
  - [ ] `print_confirm_prompt(message)`：紫色 ❓
  - [ ] `print_context_compress(count)`：青色 📊
  - [ ] `print_final_response(content)`：正常格式

### 4.2 集成 Rich 输出
- [ ] 替换所有 `print()` 调用为 Rich 函数
  - [ ] Agent loop 中的工具调用和结果
  - [ ] 风险警告和确认提示
  - [ ] 上下文压缩通知
  - [ ] 最终响应输出

### 4.3 日志系统
- [ ] 配置 `logging` 模块
  - [ ] 创建日志目录：`~/.guardcode/logs/`
  - [ ] 配置 `RichHandler`（终端输出）
  - [ ] 配置 `FileHandler`（文件输出）
  - [ ] 设置格式：`{timestamp} | {level} | {name} | {message}`
- [ ] 添加日志记录
  - [ ] 工具调用：`logger.info(f"Tool: {tool_name}({args})")`
  - [ ] 工具结果：`logger.info(f"Result: {result}")`
  - [ ] 风险检测：`logger.warning(f"Risk: {pattern}")`
  - [ ] 用户确认：`logger.info(f"User confirmed: {decision}")`
  - [ ] 错误：`logger.error(f"Error: {error}")`
  - [ ] 上下文压缩：`logger.info(f"Compressed {n} messages")`
- [ ] 日志写入兜底：所有日志调用用 `try/except` 包裹

### 4.4 错误处理
- [ ] 模型调用重试
  - [ ] 实现 `call_model_with_retry(messages, max_retries=3)`
  - [ ] 使用 `time.sleep(2 ** attempt)` 指数退避
  - [ ] 捕获网络错误和 API 错误
  - [ ] 重试 3 次后仍失败，抛出异常
- [ ] 用户中断处理
  - [ ] 在 `__main__.py` 中捕获 `KeyboardInterrupt`
  - [ ] 实现 `save_session(messages, workspace)`
    - [ ] 保存到 `~/.guardcode/sessions/{timestamp}.json`
  - [ ] 打印提示：任务已中断，对话历史已保存
  - [ ] 优雅退出

### 4.5 CLI 完善
- [ ] 扩展 `argparse` 参数
  - [ ] 添加 `--api-base`（API 端点 URL）
  - [ ] 添加 `--version`（显示版本号）
  - [ ] 添加 `--verbose`（详细输出模式）
- [ ] 参数验证
  - [ ] 检查 `OPENAI_API_KEY` 是否设置
  - [ ] 检查 workspace 是否存在
  - [ ] 检查配置文件格式是否正确

### 4.6 文档完善
- [ ] 更新 `README.md`
  - [ ] 项目介绍
  - [ ] 安装说明
  - [ ] 使用示例
  - [ ] 配置说明
  - [ ] 常见问题
- [ ] 创建 `requirements.txt`
  - [ ] `openai>=1.0.0`
  - [ ] `rich>=13.0.0`
- [ ] 创建 `.gitignore`
  - [ ] `__pycache__/`
  - [ ] `*.pyc`
  - [ ] `.env`
  - [ ] `*.log`
  - [ ] `.guardcode/`（本地配置和日志）

### 4.7 验收测试
- [ ] 测试格式化输出：执行任意任务，检查输出是否清晰美观
- [ ] 测试日志记录：检查 `~/.guardcode/logs/agent.log` 是否完整
- [ ] 测试错误恢复：断网状态下执行任务，观察重试和错误提示
- [ ] 测试用户中断：Ctrl+C 中断任务，检查会话是否保存

---

## 单元测试（贯穿各 Phase）

### 工具测试
- [ ] `tests/test_file_tools.py`
  - [ ] 测试 `read_file`：正常读取、文件不存在、路径逃逸
  - [ ] 测试 `write_file`：正常写入、创建父目录、路径逃逸
  - [ ] 测试 `list_files`：正常列出、目录不存在、路径逃逸
  - [ ] 测试 `delete_file`：正常删除、文件不存在、路径逃逸
- [ ] `tests/test_command_tools.py`
  - [ ] 测试 `run_command`：正常执行、命令失败、超时

### 安全测试
- [ ] `tests/test_security.py`
  - [ ] 测试 `classify_risk`：各种命令模式匹配
  - [ ] 测试 `scan_python_code`：各种代码风险模式
  - [ ] 测试配置规则：always_block、auto_approve

### 上下文测试
- [x] `tests/test_context_compressor.py`
  - [x] 测试写后失效：write_file 后旧 read_file 结果被标记过期
  - [x] 测试路径规范化匹配：`./src/main.py` vs `src/main.py`
  - [x] 测试按需重读：大型 result 被压缩为 `<content: N chars>`
  - [x] 测试压缩大型 tool_calls：write_file 的 content 参数被压缩
  - [x] 测试工作集保留：最近 N 条消息完整保留
  - [x] 测试幂等性：已压缩消息不重复压缩
  - [x] 测试 `compress_history`：分区逻辑、边界情况
  - [x] 测试 `estimate_context_size` 和 `should_compress`
- [x] `tests/test_agent.py`：事件驱动失效集成测试
  - [x] write_file 成功后立即失效旧 read_file（不等阈值）
  - [x] delete_file 成功后立即失效旧 read_file
  - [x] 失败的 write_file 不触发失效
  - [x] 无旧读取时无副作用
  - [x] read_file 成功后压缩旧大型读取
  - [x] 最新一轮 read_file 保持完整
  - [x] 循环检测：连续两轮相同工具调用 → 终止

---

## 集成测试

### 端到端场景
- [ ] 场景 1：简单文件操作
  - [ ] 任务："create a file notes.txt with my TODO list"
  - [ ] 验证：文件创建成功，内容合理
- [ ] 场景 2：代码生成
  - [ ] 任务："implement bubble sort in Python in sort.py"
  - [ ] 验证：代码正确，格式规范
- [ ] 场景 3：测试驱动修复
  - [ ] 准备：有 bug 的代码 + 失败的测试
  - [ ] 任务："fix the bugs in calculator.py"
  - [ ] 验证：代码修复，测试通过
- [ ] 场景 4：危险操作
  - [ ] 任务："delete all temporary files"
  - [ ] 验证：触发确认提示
- [ ] 场景 5：代码风险
  - [ ] 任务："write a script that dynamically evaluates code"
  - [ ] 验证：触发风险警告

---

## 交付前检查

### 代码质量
- [ ] 运行代码格式化工具（black 或 ruff）
- [ ] 运行 linter（flake8 或 ruff）
- [ ] 运行类型检查（mypy，可选）
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过

### 文档完整性
- [ ] README.md 包含所有必要信息
- [ ] docs/SPEC.md 完整
- [ ] docs/PLAN.md 完整
- [ ] docs/TASKS.md 完整
- [ ] 代码中关键函数有 docstring

### 配置和环境
- [ ] requirements.txt 包含所有依赖
- [ ] .gitignore 覆盖所有临时文件
- [ ] 示例配置文件 .guardcode.json 正确
- [ ] 环境变量说明清晰

### 功能验收
- [ ] 核心 Agent loop 工作正常
- [ ] 文件操作工具可用
- [ ] 命令执行工具可用
- [ ] 风险分级生效
- [ ] 代码扫描生效
- [ ] 用户确认流程完整
- [ ] 上下文压缩工作
- [ ] Rich 输出美观
- [ ] 日志记录完整
- [ ] 错误处理健壮

---

## 可选增强（时间充裕时）

- [ ] 会话恢复功能：`guardcode --resume {session_id}`
- [ ] 代码 diff 预览：修改文件前显示差异
- [ ] 并行工具执行：独立工具调用可并行
- [ ] 流式输出：模型响应实时显示
- [ ] 更多测试：增加边界情况和异常情况的测试
- [ ] 性能优化：减少不必要的文件读写
- [ ] 国际化：支持中文输出（可选）
