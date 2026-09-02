# GuardCode Agent

> 面向可信软件开发的 AI 编程智能体 — 自主读写文件、执行命令，内置上下文压缩和安全防护机制。
> 支持命令行与 Web 双模式，提供 PLAN / WORK / FEEDBACK / RESEARCH 四种工作模式。

## 项目定位

GuardCode Agent 是一款从零实现的编程智能体，核心解决两个痛点：
- **长对话 token 消耗过快** — 事件驱动 + 阈值驱动混合压缩策略，平均节省 35.4% token
- **误执行危险脚本风险** — 三层防护体系，命令分级 100% 准确，代码扫描零误报

## 特色功能

### 1. 上下文压缩机制

针对长对话 token 快速消耗的痛点，实现三种自创压缩策略：

| 策略 | 触发时机 | 效果 |
|------|----------|------|
| **写后失效** | write_file/delete_file 成功后立即失效旧 read_file 结果（事件驱动） | 过期内容立即释放 |
| **按需重读** | 大型结果（>500 字符）压缩为元信息占位符（阈值驱动） | 保留 success/error 状态，模型需要时重新读取 |
| **工作集保留** | 最近 5 轮消息完整保留，不压缩 | 确保上下文连续性 |

量化实验显示：平均压缩率 **35.4%**，文件密集场景最高 **65.2%**，压缩耗时仅 **0.26ms**。

### 2. 安全防护机制

三层防护体系，层层递进：

1. **路径校验** — 所有文件操作限制在 workspace 内，消解符号链接，防止目录穿越
2. **命令风险分级** — SAFE / DANGEROUS / BLOCKED 三级，支持黑白名单配置
3. **代码静态扫描** — 检测 eval / exec / os.system / subprocess shell=True 等危险模式

量化实验显示：命令分级 **100% 准确率**（23 危险全拦、25 安全全放），代码扫描精确率 **100%**（零误报）。

### 3. 四种工作模式

| 模式 | 核心特征 | 适用场景 |
|------|----------|----------|
| **PLAN** | 先生成结构化计划，用户审批后执行（支持自由编辑计划） | 复杂任务、需要确认方案 |
| **WORK** | 自主执行，危险操作需确认 | 日常开发、bug 修复 |
| **FEEDBACK** | 关键决策点暂停等待反馈 | 需要人工指导的任务 |
| **RESEARCH** | 只读调查，不修改文件 | 代码理解、技术调研 |

### 4. 任务管理

- Web 界面支持按工作区（workspace）分类管理任务
- 列表视图 / 分组视图切换
- 任务持久化到 SQLite，支持历史回溯

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（Web 界面）

### 命令行模式

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API key
export OPENAI_API_KEY="your-key-here"

# 运行任务
python -m guardcode "implement quicksort in Python with tests"

# 指定工作目录和模型
python -m guardcode --workspace ./myproject --model gpt-4o "fix the bug in main.py"

# 使用自定义 API 端点（如 DeepSeek）
python -m guardcode --api-base https://api.deepseek.com/v1 --model deepseek-chat "refactor auth module"
```

### Web 界面模式

```bash
# 启动后端 API
python -m api.server

# 启动前端（新终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用 Web 界面。

## 技术亮点

### 三层架构设计

```
┌──────────────────────────────────────────────┐
│  Layer 1: Execution State（当前轮）          │
│  - response["tool_calls"] 执行源             │
│  - 绝对不可压缩                              │
└──────────────────────────────────────────────┘
                    ↓ 执行完成后入栈
┌──────────────────────────────────────────────┐
│  Layer 2: Context（历史消息）                │
│  - 对话历史（易失性记忆）                     │
│  - 可压缩：写后失效、按需重读                 │
└──────────────────────────────────────────────┘
                    ↓ Source of Truth
┌──────────────────────────────────────────────┐
│  Layer 3: Workspace（文件系统）              │
│  - 真实文件内容                              │
│  - 每次 read_file 都从磁盘读取               │
└──────────────────────────────────────────────┘
```

核心思想：**Workspace 是 Source of Truth，历史消息是易失性记忆，重新读取优于大上下文。**

### 事件驱动 + 阈值驱动混合压缩

- **写操作立即失效旧读取** — 文件被修改的那一刻旧内容就已过期，不等阈值触发
- **读操作压缩旧大型读取** — 模型刚读了新文件，旧的大型读取结果不需要完整保留
- **阈值驱动兜底** — 上下文接近上限时全量压缩

### 零误报安全策略

- **设计哲学**：宁可漏报，不可误报
- **精确率 100%**：不会误拦正常开发操作
- **高危代码检测率 100%**：eval、exec、os.system 等全覆盖
- **保守扩展**：新增规则前需验证不引入误报

## 量化数据

| 指标 | 数据 |
|------|------|
| 测试通过率 | **100%** (31/31) |
| 上下文压缩率（平均） | **35.4%** |
| 上下文压缩率（最高，文件密集场景） | **65.2%** |
| 压缩耗时（平均） | **0.26ms** |
| 命令防护准确率 | **100%** |
| 代码扫描精确率 | **100%**（零误报） |
| 代码扫描准确率 | **85.7%** |

## 项目结构

```
guardcode/              # 核心 Agent 代码
├── agent.py            # Agent 主循环
├── model.py            # OpenAI 兼容模型适配器（含流式）
├── config.py           # 配置管理
├── workspace.py        # 工作区管理 & 路径校验
├── tools/
│   ├── base.py         # 工具注册与执行
│   ├── file_tools.py   # 文件操作工具
│   └── command_tools.py # 命令执行工具
├── security/
│   ├── risk_classifier.py  # 风险分级
│   ├── code_scanner.py     # 代码静态扫描
│   └── user_confirm.py     # 用户确认交互
├── context/
│   ├── manager.py      # 上下文大小估算
│   └── compressor.py   # 两级上下文压缩
└── ui/
    └── console.py      # Rich 终端输出

api/                    # 后端 API 服务（FastAPI）
├── server.py           # API 入口
├── agent_adapter.py    # Agent 适配器
├── database.py         # SQLite 持久化
└── routes/             # 路由：sessions / files / ws / config

frontend/               # 前端 Web 界面（React + TypeScript）
├── src/
│   ├── components/     # 组件（ChatPanel / FileTree / CodeEditor / Terminal 等）
│   ├── store/          # Zustand 状态管理
│   ├── services/       # WebSocket 服务
│   └── api/            # REST API 客户端
└── ...

experiments/            # 实验模块
├── context_compression_benchmark.py
├── security_accuracy_benchmark.py
├── compression_scenarios.py
└── results/            # 实验结果数据

tetris/                 # 演示用例：俄罗斯方块（TDD 实现）

docs/                   # 设计文档
├── SPEC.md             # 规格说明书
├── PLAN.md             # 实现计划
├── TASKS.md            # 任务清单
├── FRONTEND_SPEC.md    # 前端规格
├── review_log.md       # 设计决策与评审记录
└── brainstormProcess.md # 头脑风暴过程
```

## 开发历程

这个项目源于我之前的研究（CodeAgent Bench，一作在投）和软工三课设的积累。日常使用 agent 时发现两个核心痛点：token 耗量太快但新开对话又会丧失记忆降智；以及可能误执行危险脚本。

开发流程参考 Superpowers 的方法：先用 brainstorm 功能落地详细设计文档（778 行 SPEC.md），然后按 task 逐步开发。工具和模板由 AI 完成，核心逻辑（如 agent 循环）由我写出想法框架，AI 补充完善。压缩策略是我针对痛点自己设计的（事件驱动 + 阈值驱动混合触发），代码扫描选择轻量方案（工程需要时可引入 CodeQL、Semgrep 等成熟工具）。

过程中对架构有多次调整，对 AI 建议也有反驳（详见 `docs/review_log.md`）。前端设计受 TRAE 启发。完整 brainstorm 过程见 `docs/brainstormProcess.md`。

## 配置说明

### 配置文件加载顺序（后者覆盖前者）

1. **默认配置** — 内置默认值
2. **全局配置** — `~/.guardcode/config.json`
3. **环境变量** — `OPENAI_API_KEY`、`OPENAI_API_BASE` 等
4. **项目配置** — `{workspace}/.guardcode.json`
5. **命令行指定** — `--config PATH`（最高优先级）

### 示例配置

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4-turbo",
  "max_iterations": 10,
  "security": {
    "always_block": ["rm -rf /", "format c:", "dd if=/dev/zero"],
    "auto_approve": ["ls", "pwd", "cat", "echo", "pytest"]
  },
  "context": {
    "max_context_size": 100000,
    "keep_recent_messages": 5
  },
  "verbose": false
}
```

## CLI 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `task` | 编程任务（必填） | — |
| `--workspace PATH` | 工作区目录 | 当前目录 |
| `--model NAME` | 模型名称 | 配置文件或 `gpt-4-turbo` |
| `--api-base URL` | API 端点 | 配置文件或 OpenAI |
| `--max-iterations N` | 最大迭代次数 | 50 |
| `--config PATH` | 配置文件路径 | 自动发现 |
| `--verbose` | 详细输出 | 关闭 |

## 设计文档

- [SPEC.md](docs/SPEC.md) — 设计规格说明书
- [PLAN.md](docs/PLAN.md) — 实现计划
- [TASKS.md](docs/TASKS.md) — 任务清单
- [FRONTEND_SPEC.md](docs/FRONTEND_SPEC.md) — 前端规格
- [review_log.md](docs/review_log.md) — 设计决策与评审记录

## 致谢

- **TRAE** — 提供界面设计灵感
- **Superpowers** — 提供开发流程指导

## License

MIT
