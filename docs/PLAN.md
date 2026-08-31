# GuardCode Agent - 实施计划

## 1. 项目目标

从零实现一个面向可信软件开发的编程智能体，满足以下核心要求：
- 自主读写文件、执行命令
- 代码级安全检查
- 测试驱动修复循环
- 不依赖任何 Agent 框架/SDK

---

## 2. 实施策略

### 2.1 开发原则
- **小步快跑**：每个 Phase 完成后验证可用性
- **核心优先**：先实现 Agent loop，再添加安全和智能化
- **最小依赖**：只使用必要的第三方库
- **测试驱动**：关键组件编写单元测试

### 2.2 验证标准
每个 Phase 完成后，通过以下方式验证：
- **Phase 1**：能完成简单的文件读写和命令执行任务
- **Phase 2**：危险操作会触发确认，代码风险会警告
- **Phase 3**：长对话能自动压缩，测试失败能自动修复
- **Phase 4**：输出格式清晰，日志完整可追溯

---

## 3. 分阶段实施

### Phase 1：核心闭环（2-3 天）

**目标**：实现最小可用的 Agent loop，能完成基础的文件操作和命令执行。

#### 1.1 项目结构搭建
```
guardcode/
├── __init__.py
├── __main__.py
├── agent.py
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── file_tools.py
│   └── command_tools.py
├── config.py
└── tests/
    └── test_tools.py
```

#### 1.2 工具系统实现
- 文件工具：read_file, write_file, list_files, delete_file
- 命令工具：run_command
- 工具注册机制：@register_tool 装饰器
- 自动生成 OpenAI tool schema

#### 1.3 Agent 核心循环
基础循环：消息管理 → 调用模型 → 解析工具调用 → 执行工具 → 返回结果

#### 1.4 工作区边界实现
- 启动时解析 --workspace 参数
- Path(workspace).resolve() 获取绝对路径
- 所有文件工具调用 validate_path(path, workspace)
- 命令工具使用 subprocess.run(cwd=workspace)

#### 1.5 验收标准
测试任务：
- 创建文件
- 生成 Python 函数
- 列出目录文件

---

### Phase 2：安全机制（1-2 天）

**目标**：实现风险分级和代码静态扫描，确保可信控制。

#### 2.1 风险分级系统
- 实现 classify_risk(tool_name, args)
- 检查优先级：always_block → auto_approve → DANGEROUS_PATTERNS → SAFE_PATTERNS → 默认
- 定义安全命令白名单：pytest, python, ruff, git status/diff/log, ls, cat
- 定义危险命令模式：rm -rf, git push, pip install, sudo, curl/wget

#### 2.2 用户确认流程
- 实现 confirm_operation() 询问用户
- 格式化显示待执行操作
- 支持 y/n 响应

#### 2.3 代码静态扫描
- 实现 scan_python_code(content)
- 检测模式：eval(), exec(), os.system(), subprocess shell=True
- 集成到 write_file：扫描 → 警告 → 确认 → 写入

#### 2.4 配置文件加载
- 支持全局配置：~/.guardcode/config.json
- 支持项目配置：{workspace}/.guardcode.json
- 配置合并：项目覆盖全局

#### 2.5 验收标准
测试任务：
- 危险命令触发确认
- 代码风险警告
- 自定义规则生效

---

### Phase 3：智能化（1-2 天）

**目标**：实现两级上下文压缩和测试驱动修复引导。

**核心原则**：
- Workspace 是 Source of Truth（文件系统为准）
- 历史是易失性记忆（messages 可压缩）
- 重新读取优于大上下文（read_file 每次直接读磁盘）

#### 3.1 上下文估算（已完成）
- 字符计数估算：sum(len(json.dumps(msg)) for msg in messages)
- 阈值判断：should_compress() 比较总字符数与阈值
- 已完成：context/manager.py

#### 3.2 Context Compression - Level 1（规则压缩，必须）
**设计理念**：纯规则压缩，无需额外模型调用，零成本零延迟。

三层架构：
- **Layer 1: Execution State**（当前轮，不可压缩）— response["tool_calls"] 独立提取
- **Layer 2: Context**（messages 列表，易失性记忆）— 可压缩
- **Layer 3: Workspace**（文件系统，Source of Truth）— read_file 每次直接读磁盘

四条压缩规则（三类触发机制）：
1. **写后失效（写事件驱动）**：write_file/delete_file 成功后立即失效同路径旧 read_file，不等阈值
2. **按需重读（读事件驱动 + 阈值驱动）**：read_file 成功后压缩旧大型读取；阈值触发时压缩所有大型 result 为 `<content: N chars>`
3. **压缩大型 tool_calls（阈值驱动）**：assistant 消息中 write_file 的大型 content 参数压缩为占位符
4. **工作集保留（阈值驱动）**：最近 N 轮（默认 5）完整保留，不压缩

前置修改：
- 修改 `_format_tool_result()` 增加 `tool_name` 参数，在 content 中记录 `_tool_name` 和规范化路径

#### 3.3 Context Compression - Level 2（LLM 摘要，可选）
- 仅在 Level 1 压缩率不足时启用（压缩后仍 > 原始 50%）
- 使用较次模型生成 2-3 句话摘要
- 禁止脑补 Prompt：只记录已执行的操作，不添加未执行的计划
- Phase 1 默认关闭

#### 3.4 集成到 Agent Loop
- 写事件驱动：write/delete 成功后立即调用 `_invalidate_outdated_reads()`，不等阈值
- 读事件驱动：read_file 成功后立即调用 `_compress_large_results()`，压缩旧大型读取
- 阈值驱动：下一轮调用模型前检查 should_compress()
- 当前轮的 response["tool_calls"] 已独立提取，不受压缩影响
- 压缩只修改内存中的 messages，不触碰 Workspace

#### 3.5 System Prompt 优化
编写完整的 system prompt：
- Agent 角色定位
- 工具使用说明
- 测试驱动开发流程指引
- 安全注意事项

#### 3.6 迭代终止条件完善
- 最大迭代次数：--max-iterations 配置
- 循环检测：连续两轮无工具调用或工具调用相同
- 测试通过：run_command 返回 exit code 0

#### 3.7 验收标准
测试任务：
- 长对话触发压缩，任务仍能正确完成
- 写后失效：write_file 后旧 read_file 结果被标记过期
- 测试驱动修复（发现测试 → 修改代码 → 运行测试 → 修复）
- TDD 流程（先写测试，再写实现）

---

### Phase 4：工程化（1 天）

**目标**：完善输出格式、日志系统和错误处理。

#### 4.1 Rich 格式化输出
- 安装 rich 库
- 实现彩色输出：工具调用、结果、错误、警告
- 使用图标：→ ✓ ✗ ⚠ 🛡 ❓ 📊 💬
- Panel 显示重要提示

#### 4.2 日志持久化
- 配置 logging 模块 + RichHandler
- 日志目录：~/.guardcode/logs/agent.log
- 格式：{timestamp} | {level} | {name} | {message}
- 关键位置添加日志：工具调用、风险检测、错误

#### 4.3 错误处理完善
- 模型调用重试：3 次，指数退避
- 用户中断处理：捕获 KeyboardInterrupt，保存会话
- 日志写入兜底：try/except 静默跳过

#### 4.4 CLI 参数解析
使用 argparse 实现完整 CLI：
- task（位置参数）
- --workspace, --model, --max-iterations, --api-base, --config

#### 4.5 验收标准
测试任务：
- 格式化输出清晰美观
- 日志文件记录完整
- 错误恢复（断网重试）
- 用户中断保存会话

---

## 4. 技术细节

### 4.1 OpenAI API 集成
```python
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")
response = openai.ChatCompletion.create(
    model="gpt-4-turbo",
    messages=messages,
    tools=get_tool_schemas()
)
```

### 4.2 路径校验实现
```python
def validate_path(path_str: str, workspace: Path) -> Path:
    target = workspace / path_str if not Path(path_str).is_absolute() else Path(path_str)
    resolved = target.resolve()
    if not resolved.is_relative_to(workspace):
        raise ValueError(f"Path outside workspace: {path_str}")
    return resolved
```

### 4.3 命令执行实现
```python
def run_command(command: str, timeout: int = 30) -> dict:
    result = subprocess.run(
        command, shell=True, cwd=workspace,
        capture_output=True, text=True, timeout=timeout
    )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
```

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型调用超时/失败 | Agent 无法工作 | 实现重试机制，指数退避 |
| 上下文窗口溢出 | 长对话无法继续 | 两级压缩：规则压缩 + LLM 摘要（可选） |
| 路径遍历攻击 | 访问 workspace 外文件 | resolve() + is_relative_to() 严格校验 |
| 命令注入 | 执行恶意命令 | 风险分级 + 用户确认 |
| 代码注入 | 写入恶意代码 | 静态扫描 + 警告确认 |

---

## 6. 测试策略

### 6.1 单元测试
- tests/test_tools.py：测试每个工具的基础功能
- tests/test_security.py：测试风险分级逻辑
- tests/test_context.py：测试上下文压缩逻辑（写后失效、按需重读、工作集保留、幂等性）
- 使用 pytest + unittest.mock

### 6.2 集成测试
准备测试任务集：简单文件操作、代码生成、测试驱动修复、危险操作确认

### 6.3 端到端测试
真实场景任务：
- "implement a todo CLI app with tests"
- "fix the security vulnerability in auth.py"
- "refactor the database module"

---

## 7. 交付清单

### 7.1 代码交付
- guardcode/ 源代码目录
- tests/ 测试代码
- requirements.txt 依赖列表
- setup.py 或 pyproject.toml 包配置

### 7.2 文档交付
- README.md 使用说明
- docs/SPEC.md 设计规格
- docs/PLAN.md 实施计划
- docs/TASKS.md 任务清单

### 7.3 配置交付
- .guardcode.json 示例配置
- .gitignore Git 忽略规则

---

## 8. 时间表

| Phase | 任务 | 预计时间 | 交付物 |
|-------|------|----------|--------|
| Phase 1 | 核心闭环 | 2-3 天 | 可运行的 Agent，能完成基础任务 |
| Phase 2 | 安全机制 | 1-2 天 | 风险分级 + 代码扫描 |
| Phase 3 | 智能化 | 1-2 天 | 上下文压缩 + TDD 引导 |
| Phase 4 | 工程化 | 1 天 | Rich 输出 + 日志 + 错误处理 |
| **总计** | | **5-8 天** | 完整可用的 GuardCode Agent |

---

## 9. 后续优化方向

完成核心功能后，可以考虑以下优化（不在首期范围内）：

1. **多模型支持**：抽象模型接口，支持 Anthropic、Gemini 等
2. **会话恢复**：保存和恢复中断的对话
3. **代码审查模式**：生成代码后展示 diff，等待用户确认
4. **插件系统**：支持用户自定义工具
5. **Web UI**：提供浏览器界面，替代 CLI
6. **性能优化**：并行工具执行、模型响应流式输出
7. **高级扫描**：集成 Bandit、Semgrep 等专业工具
8. **代码补全**：支持增量编辑，而非整文件重写
