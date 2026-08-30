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
- [ ] 修改 `execute_tool()` 函数
  - [ ] 执行前调用 `classify_risk()`
  - [ ] 如果是 BLOCKED，返回错误
  - [ ] 如果是 DANGEROUS，调用 `confirm_operation()`
  - [ ] 如果用户拒绝，返回错误或跳过
  - [ ] 如果是 SAFE，直接执行

### 2.5 代码静态扫描
- [ ] 实现 `security/code_scanner.py`
  - [ ] 定义 `CODE_RISK_PATTERNS`（dict，模式名 → 正则）
  - [ ] 实现 `scan_python_code(content: str) -> list[dict]`
    - [ ] 逐行匹配正则
    - [ ] 返回发现的风险列表：`[{"pattern": str, "line": int, "content": str}]`

### 2.6 集成代码扫描到 write_file
- [ ] 修改 `write_file()` 函数
  - [ ] 检查文件扩展名是否为 `.py`
  - [ ] 如果是，调用 `scan_python_code(content)`
  - [ ] 如果发现风险，打印警告
  - [ ] 询问用户：[c]ontinue / [a]bort
  - [ ] 根据用户选择决定是否写入

### 2.7 配置文件扩展
- [ ] 扩展配置格式，添加 `security` 字段
  - [ ] `security.always_block`（字符串列表）
  - [ ] `security.auto_approve`（字符串列表）
- [ ] 更新配置加载逻辑
  - [ ] 支持全局配置：`~/.guardcode/config.json`
  - [ ] 支持项目配置：`{workspace}/.guardcode.json`
  - [ ] 合并配置（项目覆盖全局）

### 2.8 验收测试
- [ ] 测试危险命令：`guardcode "delete all .pyc files using rm -rf"`
  - [ ] 应该触发确认提示
- [ ] 测试代码风险：`guardcode "write a script that uses eval()"`
  - [ ] 应该显示风险警告
- [ ] 测试自定义规则：配置 `auto_approve: ["rm *.pyc"]`，再执行删除
  - [ ] 应该自动放行

---

## Phase 3：智能化（1-2 天）

### 3.1 上下文估算
- [ ] 实现 `context/manager.py`
  - [ ] `estimate_context_size(messages: list) -> int`
    - [ ] 使用 `json.dumps()` 序列化每条消息
    - [ ] 累加字符数
  - [ ] `should_compress(messages: list, threshold: int) -> bool`
    - [ ] 比较总字符数与阈值

### 3.2 摘要生成
- [ ] 实现 `context/summarizer.py`
  - [ ] `summarize_messages(messages: list) -> str`
    - [ ] 构造摘要 prompt
    - [ ] 调用模型（使用 gpt-3.5-turbo 节省成本）
    - [ ] 返回摘要内容
    - [ ] 异常处理：返回兜底消息

### 3.3 上下文压缩
- [ ] 实现 `compress_history(messages: list, config: dict) -> list`
  - [ ] 提取永久消息：`messages[0:2]`
  - [ ] 提取最近消息：`messages[-K:]`（K 从配置读取）
  - [ ] 提取中间消息：`messages[2:-K]`
  - [ ] 如果中间消息不为空，调用 `summarize_messages()`
  - [ ] 构造摘要消息：`{"role": "system", "content": "[摘要]: ..."}`
  - [ ] 返回：永久 + 摘要 + 最近

### 3.4 集成上下文压缩到 Agent Loop
- [ ] 修改 `run_agent_loop()`
  - [ ] 在每次调用模型前，检查 `should_compress()`
  - [ ] 如果需要压缩，调用 `compress_history()`
  - [ ] 打印压缩提示（可选）

### 3.5 System Prompt 优化
- [ ] 编写完整的 System Prompt
  - [ ] 角色定位：GuardCode Agent，专注可信软件开发
  - [ ] 工具说明：列出每个工具及其用途
  - [ ] 测试驱动流程：
    - [ ] 使用 list_files 检查测试
    - [ ] 如果有测试：修改代码 → 运行测试 → 修复
    - [ ] 如果无测试：优先 TDD（先写测试）
  - [ ] 安全注意事项：所有操作限制在 workspace 内
  - [ ] 最佳实践：增量修改、读取后再修改、使用版本控制

### 3.6 迭代终止条件
- [ ] 完善循环终止逻辑
  - [ ] 达到 `max_iterations`：打印警告并退出
  - [ ] 无工具调用：正常结束
  - [ ] 循环检测（可选）：连续两轮工具调用相同

### 3.7 验收测试
- [ ] 测试长对话：构造需要多次迭代的任务，观察是否触发压缩
- [ ] 测试测试驱动修复：`guardcode "fix the bug in calculator.py, tests are in test_calculator.py"`
  - [ ] 观察是否：list_files → read → write → run pytest → 修复 → 再测试
- [ ] 测试 TDD 流程：`guardcode "implement a stack with push/pop/peek"`
  - [ ] 观察是否先写测试

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
- [ ] `tests/test_context.py`
  - [ ] 测试 `estimate_context_size`
  - [ ] 测试 `compress_history`：边界情况（消息数 < K）
  - [ ] 测试摘要生成（使用 mock）

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
