# GuardCode Agent — 前端设计规格

> 本文档独立于原有 `SPEC.md`，专注于 Web 前端界面的设计。
> 原有后端（Agent 核心、工具系统、安全机制、上下文压缩）已全部通过测试，不修改。

---

## 1. 概述

### 1.1 目标

为已有的 GuardCode Agent CLI 后端构建 TRAE 式 Web 前端界面，实现：

- 代码编辑器（Monaco Editor，语法高亮、diff 视图）
- 文件树浏览器（目录展开/折叠/搜索）
- AI 聊天面板（流式输出、工具调用可视化、用户确认交互）
- 内嵌终端（命令执行输出实时展示）
- 实时通信（WebSocket 推送 Agent 状态）

### 1.2 设计原则

- **后端零侵入**：不修改 `guardcode/` 目录下任何已有代码，通过适配层（Adapter）接入
- **快速交付**：技术选型优先成熟生态和开箱即用组件
- **单用户工具**：不需要多用户认证，本地运行，面向开发者本人

### 1.3 与后端的关系

```
┌─────────────────────────────────────────────────┐
│  前端 (React + Vite)                             │
│  - Monaco Editor / File Tree / Chat / Terminal  │
└──────────────────────┬──────────────────────────┘
                       │ WebSocket + REST
┌──────────────────────▼──────────────────────────┐
│  API 适配层 (FastAPI)          ← 新增           │
│  - REST: 文件操作、会话管理                      │
│  - WebSocket: Agent 事件流                      │
│  - AgentSession 适配器：线程 + 事件队列           │
└──────────────────────┬──────────────────────────┘
                       │ 直接调用（Python import）
┌──────────────────────▼──────────────────────────┐
│  GuardCode Agent 核心 (已有，不修改)              │
│  - agent.py: run_agent_loop()                    │
│  - tools/: file_tools, command_tools             │
│  - security/: risk_classifier, code_scanner      │
│  - context/: compressor, manager                │
└─────────────────────────────────────────────────┘
```

---

## 2. 技术栈

### 2.1 后端 API 层

| 技术 | 用途 | 选择理由 |
|------|------|----------|
| FastAPI | Web 框架 | 原生 async + WebSocket，自动 OpenAPI 文档 |
| uvicorn | ASGI 服务器 | FastAPI 标配 |
| threading | Agent 后台执行 | 现有 `run_agent_loop` 是同步的，用线程包装 |
| asyncio.Queue | 事件传递 | 线程→async WebSocket 的桥梁 |

### 2.2 前端

| 技术 | 用途 | 选择理由 |
|------|------|----------|
| React 18 + TypeScript | UI 框架 | 生态最成熟，AI 生成代码质量最高 |
| Vite | 构建工具 | 极速 HMR，零配置 |
| Tailwind CSS | 样式 | 原子化 CSS，快速布局 |
| Monaco Editor | 代码编辑器 | VS Code 同款，API 成熟 |
| xterm.js | 终端模拟 | 行业标准 |
| Zustand | 状态管理 | 轻量，无 boilerplate |
| lucide-react | 图标 | 轻量美观 |

### 2.3 依赖清单

**后端新增 (`requirements.txt` 追加）：**
```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
websockets>=12.0
```

**前端 (`frontend/package.json`）：**
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@monaco-editor/react": "^4.6.0",
    "@xterm/xterm": "^5.5.0",
    "@xterm/addon-fit": "^0.10.0",
    "zustand": "^4.5.0",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  }
}
```

---

## 3. 目录结构

```
GuardCode Agent/
├── guardcode/              # 已有后端，不修改
├── api/                    # 新增：FastAPI 适配层
│   ├── __init__.py
│   ├── server.py           # FastAPI 应用入口
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── sessions.py     # 会话管理 REST
│   │   ├── files.py        # 文件操作 REST
│   │   └── ws.py           # WebSocket 端点
│   └── agent_adapter.py   # Agent 核心适配器
├── frontend/              # 新增：React 前端
│   ├── src/
│   │   ├── App.tsx         # 主布局
│   │   ├── main.tsx        # 入口
│   │   ├── components/
│   │   │   ├── FileTree.tsx
│   │   │   ├── CodeEditor.tsx
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── Terminal.tsx
│   │   │   ├── ToolCallCard.tsx
│   │   │   └── ConfirmDialog.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useSession.ts
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── store/
│   │   │   └── appStore.ts
│   │   └── types/
│   │       └── index.ts
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── tsconfig.json
├── tests/                 # 已有测试
├── docs/                  # 已有文档 + 新增前端文档
└── requirements.txt       # 追加 fastapi/uvicorn
```

---

## 4. 后端 API 设计

### 4.1 Agent 适配器（核心）

现有 `run_agent_loop()` 是同步阻塞函数，通过 **线程 + 事件队列** 适配为事件驱动：

```python
# api/agent_adapter.py

import asyncio
import threading
from queue import Queue, Empty
from typing import Any

from guardcode.agent import run_agent_loop
from guardcode.config import load_config
from guardcode.workspace import init_workspace


class AgentSession:
    """将同步的 run_agent_loop 适配为事件驱动的 WebSocket 会话。"""

    def __init__(self, session_id: str, workspace: str):
        self.session_id = session_id
        self.workspace = workspace
        self.event_queue: Queue = Queue()
        self.confirm_queue: Queue = Queue()  # 用户确认响应
        self.thread: threading.Thread | None = None
        self.is_running = False
        self.messages: list[dict] = []

    def start(self, task: str):
        """在后台线程启动 Agent loop。"""
        self.is_running = True
        self.thread = threading.Thread(
            target=self._run_agent, args=(task,), daemon=True
        )
        self.thread.start()

    def _run_agent(self, task: str):
        """线程目标函数：运行 agent loop，事件推入队列。"""
        try:
            config = load_config(workspace=self.workspace)

            # 注入事件回调（monkey-patch print 函数）
            import guardcode.agent as agent_mod
            original_print_tool_call = agent_mod._print_tool_call
            original_print_tool_result = agent_mod._print_tool_result

            def event_print_tool_call(name, args):
                self.event_queue.put({
                    "type": "tool_call",
                    "tool": name,
                    "args": args,
                })
                original_print_tool_call(name, args)

            def event_print_tool_result(result):
                self.event_queue.put({
                    "type": "tool_result",
                    "result": result,
                })
                original_print_tool_result(result)

            agent_mod._print_tool_call = event_print_tool_call
            agent_mod._print_tool_result = event_print_tool_result

            # 运行 agent
            result = run_agent_loop(task, config=config)

            # 恢复原始函数
            agent_mod._print_tool_call = original_print_tool_call
            agent_mod._print_tool_result = original_print_tool_result

            self.event_queue.put({
                "type": "done",
                "content": result,
            })
        except Exception as e:
            self.event_queue.put({
                "type": "error",
                "message": str(e),
            })
        finally:
            self.is_running = False

    def send_message(self, content: str):
        """向 agent 发送新消息（用于多轮对话）。"""
        self.event_queue.put({
            "type": "user_message",
            "content": content,
        })

    def confirm(self, tool_call_id: str, approved: bool):
        """响应用户确认请求。"""
        self.confirm_queue.put({"tool_call_id": tool_call_id, "approved": approved})

    def stop(self):
        """停止 agent。"""
        self.is_running = False
        self.event_queue.put({"type": "stopped"})

    def get_events(self) -> list[dict]:
        """非阻塞获取所有待处理事件。"""
        events = []
        while True:
            try:
                event = self.event_queue.get_nowait()
                events.append(event)
            except Empty:
                break
        return events
```

### 4.2 REST API 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/sessions` | 创建会话（传入 workspace 路径） |
| GET | `/api/sessions` | 列出所有会话 |
| GET | `/api/sessions/{id}` | 获取会话状态 |
| GET | `/api/files` | 列出/读取文件（`?path=...`） |
| PUT | `/api/files` | 写入文件 |
| DELETE | `/api/files` | 删除文件 |
| POST | `/api/command` | 执行命令（带风险判定） |

**创建会话：**
```http
POST /api/sessions
Content-Type: application/json

{
  "workspace": "/path/to/project"
}

→ 201
{
  "session_id": "sess-abc123",
  "workspace": "/path/to/project",
  "files": [...]
}
```

**列出文件：**
```http
GET /api/files?path=.

→ 200
{
  "type": "directory",
  "path": ".",
  "entries": [
    {"name": "src", "type": "directory"},
    {"name": "main.py", "type": "file", "size": 1024}
  ]
}
```

**读取文件：**
```http
GET /api/files?path=src/main.py

→ 200
{
  "type": "file",
  "path": "src/main.py",
  "content": "...",
  "size": 1024
}
```

**写入文件：**
```http
PUT /api/files
Content-Type: application/json

{
  "path": "src/main.py",
  "content": "print('hello')"
}

→ 200
{
  "success": true,
  "path": "src/main.py"
}
```

### 4.3 WebSocket 协议

**连接：**
```
ws://localhost:8000/api/sessions/{session_id}/ws
```

**Server → Client 事件：**

```typescript
// 工具调用开始
{
  type: "tool_call",
  tool: "read_file",
  args: { path: "src/main.py" },
  timestamp: "2026-09-01T10:00:00Z"
}

// 工具执行结果
{
  type: "tool_result",
  tool: "read_file",
  result: { success: true, result: "..." },
  timestamp: "2026-09-01T10:00:01Z"
}

// 风险警告（危险操作检测到）
{
  type: "risk_warning",
  tool: "run_command",
  args: { command: "rm -rf temp" },
  risk_level: "DANGEROUS",
  patterns_matched": ["rm -rf"],
  timestamp: "2026-09-01T10:00:02Z"
}

// 用户确认请求（需要用户 y/n）
{
  type: "confirm_request",
  tool_call_id: "tc-123",
  tool: "delete_file",
  args: { path: "temp.txt" },
  message: "确认删除文件 temp.txt？",
  timestamp: "2026-09-01T10:00:03Z"
}

// 代码风险扫描结果
{
  type: "code_scan",
  path: "script.py",
  risks: [
    { pattern: "eval", line: 5, content: "eval(user_input)" }
  ],
  timestamp: "2026-09-01T10:00:04Z"
}

// 上下文压缩通知
{
  type: "context_compress",
  original_count": 15,
  compressed_count": 8,
  freed_chars": 12000,
  timestamp: "2026-09-01T10:00:05Z"
}

// Agent 完成
{
  type: "done",
  content: "Task completed. Created fib.py with tests.",
  timestamp: "2026-09-01T10:00:06Z"
}

// 错误
{
  type: "error",
  message: "Model API call failed: timeout",
  timestamp: "2026-09-01T10:00:07Z"
}
```

**Client → Server 事件：**

```typescript
// 发送任务/消息
{
  type: "start",
  task: "implement quicksort in Python with tests"
}

// 用户确认响应
{
  type: "confirm_response",
  tool_call_id: "tc-123",
  approved: true
}

// 停止 agent
{
  type: "stop"
}
```

---

## 5. 前端组件设计

### 5.1 整体布局

```
┌─────────────────────────────────────────────────────────────┐
│  TopBar: GuardCode | Session: my-project | ● Running        │
├──────────┬────────────────────────────┬─────────────────────┤
│          │                            │                     │
│ FileTree │    Code Editor (Monaco)    │   AI Chat Panel     │
│          │                            │                     │
│ 📁 src   │  1  import os              │  ┌─ User ────────┐ │
│  📄 main │  2  def hello():           │  │ implement...  │ │
│  📄 util │  3      print("hi")        │  └────────────────┘ │
│ 📁 tests │  4                        │  ┌─ Agent ───────┐ │
│  📄 test │  5  hello()               │  │ 🔧 read_file  │ │
│          │                            │  │ ✓ src/main.py │ │
│          │                            │  │ 🔧 write_file │ │
│          │                            │  │ ✓ done        │ │
│          │                            │  └────────────────┘ │
│          │                            │  ┌─ Input ──────┐ │
│          │                            │  │ [Send]        │ │
├──────────┴────────────────────────────┴─────────────────────┤
│  Terminal (xterm.js)                                         │
│  $ pytest tests/ -v                                          │
│  ===== 2 passed in 0.05s =====                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 组件清单

#### 5.2.1 App.tsx — 主布局

- 三栏布局：FileTree | CodeEditor | ChatPanel
- 底部可折叠 Terminal
- 顶部 TopBar（会话状态、停止按钮）
- 使用 `react-resizable-panels` 实现可拖拽调整

#### 5.2.2 FileTree.tsx — 文件树

```typescript
interface FileTreeProps {
  workspace: string;
  onFileSelect: (path: string) => void;
}

// 功能：
// - 递归渲染目录树
// - 点击文件夹展开/折叠
// - 点击文件触发 onFileSelect
// - 右键菜单：新建文件/文件夹、删除、重命名
// - 文件图标按扩展名区分
```

#### 5.2.3 CodeEditor.tsx — 代码编辑器

```typescript
interface CodeEditorProps {
  filePath: string | null;
  content: string;
  onContentChange: (content: string) => void;
  onSave: () => void;
}

// 功能：
// - Monaco Editor 集成
// - 按文件扩展名自动切换语言模式
// - Ctrl+S 保存（调用 PUT /api/files）
// - Agent 修改文件后自动刷新（通过 WebSocket 事件）
// - Diff 视图：Agent 修改前后对比
```

#### 5.2.4 ChatPanel.tsx — AI 聊天面板

```typescript
interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (content: string) => void;
  onStop: () => void;
}

// 消息类型：
type ChatMessage =
  | { role: "user"; content: string; timestamp: string }
  | { role: "assistant"; content: string; timestamp: string }
  | { role: "tool_call"; tool: string; args: Record<string, any>; timestamp: string }
  | { role: "tool_result"; tool: string; result: any; success: boolean; timestamp: string }
  | { role: "system"; content: string; type: "compress" | "error" | "warning"; timestamp: string };

// 功能：
// - 消息列表滚动展示
// - 工具调用以卡片形式展示（可折叠参数和结果）
// - 流式输出（assistant 消息逐字显示）
// - 底部输入框 + 发送按钮
// - Agent 运行时显示停止按钮
// - 自动滚动到最新消息
```

#### 5.2.5 Terminal.tsx — 终端

```typescript
interface TerminalProps {
  output: TerminalOutput[];
}

// 功能：
// - xterm.js 集成
// - 展示 run_command 的 stdout/stderr
// - 命令执行时实时追加输出
// - 支持颜色（ANSI 转义）
// - 可折叠/展开
```

#### 5.2.6 ToolCallCard.tsx — 工具调用卡片

```typescript
interface ToolCallCardProps {
  tool: string;
  args: Record<string, any>;
  result?: any;
  success?: boolean;
  timestamp: string;
}

// 功能：
// - 工具名 + 图标 + 参数摘要
// - 可折叠展开查看完整参数和结果
// - 成功显示绿色 ✓，失败显示红色 ✗
// - read_file 结果可点击"在编辑器中打开"
// - write_file 结果可点击"查看 diff"
```

#### 5.2.7 ConfirmDialog.tsx — 确认对话框

```typescript
interface ConfirmDialogProps {
  tool: string;
  args: Record<string, any>;
  message: string;
  onConfirm: (approved: boolean) => void;
}

// 功能：
// - 模态弹窗，显示待执行操作详情
// - 风险等级颜色标识（DANGEROUS=红，BLOCKED=灰）
// - "确认执行" / "拒绝" 按钮
// - 倒计时自动拒绝（可选，默认 30s）
```

### 5.3 状态管理（Zustand）

```typescript
// store/appStore.ts

interface AppState {
  // 会话
  sessionId: string | null;
  workspace: string;
  isRunning: boolean;

  // 文件
  fileTree: FileNode[];
  currentFile: string | null;
  fileContent: string;
  unsavedChanges: boolean;

  // 聊天
  messages: ChatMessage[];

  // 终端
  terminalOutput: TerminalOutput[];

  // 确认请求
  pendingConfirm: ConfirmRequest | null;

  // Actions
  setSession: (id: string, workspace: string) => void;
  setRunning: (running: boolean) => void;
  setFileTree: (tree: FileNode[]) => void;
  openFile: (path: string, content: string) => void;
  addMessage: (msg: ChatMessage) => void;
  addTerminalOutput: (output: TerminalOutput) => void;
  setPendingConfirm: (req: ConfirmRequest | null) => void;
}
```

### 5.4 WebSocket Hook

```typescript
// hooks/useWebSocket.ts

function useWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const store = useAppStore();

  useEffect(() => {
    if (!sessionId) return;

    const url = `ws://localhost:8000/api/sessions/${sessionId}/ws`;
    ws.current = new WebSocket(url);

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case "tool_call":
          store.addMessage({ role: "tool_call", ...data });
          break;
        case "tool_result":
          store.addMessage({ role: "tool_result", ...data });
          // 如果是 write_file，刷新文件树
          if (data.tool === "write_file" || data.tool === "delete_file") {
            refreshFileTree();
          }
          break;
        case "confirm_request":
          store.setPendingConfirm(data);
          break;
        case "context_compress":
          store.addMessage({
            role: "system",
            content: `上下文压缩：${data.original_count} → ${data.compressed_count} 条消息`,
            type: "compress",
            timestamp: data.timestamp,
          });
          break;
        case "done":
          store.setRunning(false);
          store.addMessage({
            role: "assistant",
            content: data.content,
            timestamp: data.timestamp,
          });
          break;
        case "error":
          store.setRunning(false);
          store.addMessage({
            role: "system",
            content: data.message,
            type: "error",
            timestamp: data.timestamp,
          });
          break;
      }
    };

    return () => ws.current?.close();
  }, [sessionId]);
}
```

---

## 6. 关键交互流程

### 6.1 用户提交任务

```
用户输入 "implement quicksort with tests"
  → POST /api/sessions  (创建会话)
  → WebSocket 连接
  → { type: "start", task: "implement quicksort with tests" }
  ← { type: "tool_call", tool: "list_files", args: { directory: "." } }
  ← { type: "tool_result", tool: "list_files", result: { ... } }
  ← { type: "tool_call", tool: "write_file", args: { path: "sort.py", content: "..." } }
  ← { type: "tool_result", tool: "write_file", result: { success: true } }
  ← { type: "tool_call", tool: "run_command", args: { command: "pytest" } }
  ← { type: "tool_result", tool: "run_command", result: { stdout: "..." } }
  ← { type: "done", content: "Created sort.py with tests. All tests pass." }
```

### 6.2 危险操作确认

```
Agent 检测到危险命令
  ← { type: "risk_warning", tool: "run_command", args: { command: "rm -rf temp" } }
  ← { type: "confirm_request", tool_call_id: "tc-123", message: "确认执行 rm -rf temp？" }
  → 前端弹出 ConfirmDialog
  → 用户点击"确认执行"
  → { type: "confirm_response", tool_call_id: "tc-123", approved: true }
  ← { type: "tool_result", tool: "run_command", result: { ... } }
```

### 6.3 文件编辑保存

```
用户在编辑器中修改代码
  → Ctrl+S
  → PUT /api/files { path: "src/main.py", content: "..." }
  ← 200 { success: true }
  → 前端显示保存成功提示
```

### 6.4 Agent 修改文件后编辑器刷新

```
Agent 执行 write_file("src/main.py", "新内容")
  ← { type: "tool_result", tool: "write_file", result: { success: true } }
  → 前端检测到当前打开的文件被修改
  → GET /api/files?path=src/main.py
  ← 200 { content: "新内容" }
  → 编辑器更新内容
  → 显示 "文件被 Agent 修改，已刷新" 提示
```

---

## 7. 安全考虑

### 7.1 本地运行安全

- API 服务器仅监听 `127.0.0.1`，不暴露到外网
- 不需要用户认证（单用户本地工具）
- CORS 仅允许 `localhost:5173`（Vite dev server）

### 7.2 路径安全

- 所有 REST API 文件操作复用后端 `validate_path()` 函数
- WebSocket 不直接暴露文件操作，通过 Agent 间接操作

### 7.3 命令执行安全

- `POST /api/command` 端点复用后端 `classify_risk()` 函数
- 危险命令通过 WebSocket `confirm_request` 事件请求用户确认
- 用户确认通过 WebSocket `confirm_response` 事件回传

---

## 8. 启动方式

### 8.1 开发模式

```bash
# 终端 1：启动后端 API
cd "GuardCode Agent"
python -m api.server  # uvicorn 运行在 :8000

# 终端 2：启动前端 dev server
cd frontend
npm run dev  # Vite 运行在 :5173
```

### 8.2 生产模式（可选）

```bash
# 构建前端
cd frontend && npm run build

# FastAPI 直接 serve 静态文件
python -m api.server  # 访问 http://localhost:8000
```

### 8.3 API 服务器入口

```python
# api/server.py

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import sessions, files, ws

app = FastAPI(title="GuardCode Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(ws.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

---

## 9. 工作模式设计

### 9.1 模式概览

| 模式 | 名称 | 自主性 | 可修改文件 | 用户介入 |
|------|------|--------|-----------|---------|
| PLAN | 规划模式 | 先规划后自主 | ✅（批准后） | 计划审批（可编辑步骤） |
| WORK | 工作模式 | 全自主 | ✅ | 危险操作确认 |
| FEEDBACK | 反馈模式 | 关键点暂停 | ✅ | 关键决策点反馈 |
| RESEARCH | 研究模式 | 全自主（只读） | ❌ | 无 |

### 9.2 PLAN 模式 — 先规划后执行

**流程**：
```
用户提交任务 + 选择 PLAN 模式
  ↓
Agent 分析任务，调用 create_plan 工具生成结构化计划
  计划格式：
  {
    "steps": [
      {"id": 1, "action": "read_file", "target": "auth.py", "purpose": "了解当前实现"},
      {"id": 2, "action": "write_file", "target": "oauth_handler.py", "purpose": "创建 OAuth 处理器"},
      {"id": 3, "action": "modify_file", "target": "auth.py", "purpose": "集成 OAuth"},
      {"id": 4, "action": "write_file", "target": "test_oauth.py", "purpose": "编写测试"},
      {"id": 5, "action": "run_command", "target": "pytest test_oauth.py", "purpose": "运行测试"}
    ],
    "summary": "重构认证模块以支持 OAuth 2.0"
  }
  ↓
WebSocket 推送 plan_created 事件
  ← { type: "plan_created", plan: { steps: [...], summary: "..." } }
  ↓
前端显示计划编辑器
  用户可以：
  - ✅ 批准部分步骤（勾选）
  - ❌ 拒绝部分步骤（取消勾选）
  - ✏️ 修改步骤内容
  - ➕ 新增步骤
  - 🔀 调整步骤顺序（拖拽）
  - ✅ 整体批准
  - ❌ 整体拒绝（Agent 重新规划）
  ↓
用户提交审批结果
  → { type: "plan_approved", plan: { steps: [...编辑后的...] } }
  ↓
Agent 按批准的计划执行（自动转为 WORK 模式）
  每完成一步，WebSocket 推送 plan_step_completed 事件
  ← { type: "plan_step_completed", step_id: 1, status: "completed" }
```

**技术实现**：
- 新增 `create_plan` 工具：Agent 调用后，将计划推入事件队列，线程阻塞等待审批结果
- `AgentSession` 新增 `plan_queue`：用户审批结果通过此队列传回线程
- 前端新增 `PlanEditor` 组件：展示步骤列表，支持编辑/排序/批准/拒绝

### 9.3 WORK 模式 — 当前模式增强

**流程**：
```
用户提交任务 + 选择 WORK 模式
  ↓
Agent 自主执行（与当前 run_agent_loop 一致）
  ↓
危险操作（delete_file, 危险命令）→ confirm_request → 用户确认
  ↓
完成 → done 事件
```

**增强点**：
- 进度追踪：WebSocket 推送 `iteration_update` 事件
- 完成摘要：done 事件包含执行摘要

### 9.4 FEEDBACK 模式 — 关键决策点暂停

**流程**：
```
用户提交任务 + 选择 FEEDBACK 模式
  ↓
Agent 自主执行只读操作（read_file, list_files）
  ↓
遇到关键决策点（write_file / delete_file / run_command 前）
  ← { type: "feedback_request", tool: "write_file", args: {...}, message: "即将写入 sort.py" }
  ↓
前端显示反馈选项
  用户选择：
  - ✅ 继续：Agent 执行此操作
  - ✏️ 调整：用户输入反馈文字，Agent 根据反馈调整
  - ⏹️ 停止：Agent 停止执行
  ↓
  → { type: "feedback_response", action: "continue" | "adjust" | "stop", feedback: "可选反馈文字" }
  ↓
Agent 根据反馈继续或停止
```

**关键决策点定义**：
- `write_file`：写入文件前
- `delete_file`：删除文件前
- `run_command`：执行命令前（所有命令，不仅限于危险命令）

**技术实现**：
- Monkey-patch `execute_tool`：在执行写操作前，检查模式是否为 FEEDBACK
- 如果是，推入 `feedback_request` 事件，线程阻塞等待 `feedback_response`

### 9.5 RESEARCH 模式 — 只读调查

**流程**：
```
用户提交任务 + 选择 RESEARCH 模式
  ↓
Agent 只能使用只读工具：
  ✅ read_file, list_files
  ❌ write_file, delete_file, run_command（从工具列表中移除）
  ↓
Agent 自主调查，输出分析结果
  ← { type: "done", content: "研究报告内容..." }
```

**技术实现**：
- 过滤 `get_tool_schemas()` 返回值，移除写操作工具
- Agent 的 system prompt 追加研究模式指令
- Agent loop 正常运行，但无法调用写操作工具

### 9.6 模式切换

- 创建任务时选择模式
- PLAN 模式：计划批准后自动转为 WORK 模式执行
- 其他模式：执行过程中不可切换
- WebSocket 事件：`mode_changed`（PLAN → WORK 自动切换时推送）

### 9.7 WebSocket 事件扩展（工作模式）

**Server → Client 新增事件**：

```typescript
// PLAN 模式：计划已创建
{
  type: "plan_created",
  plan: {
    steps: [
      { id: 1, action: "read_file", target: "auth.py", purpose: "了解当前实现" },
      { id: 2, action: "write_file", target: "oauth.py", purpose: "创建 OAuth 处理器" }
    ],
    summary: "重构认证模块以支持 OAuth"
  },
  timestamp: "..."
}

// PLAN 模式：步骤完成
{
  type: "plan_step_completed",
  step_id: 1,
  status: "completed" | "failed" | "skipped",
  timestamp: "..."
}

// FEEDBACK 模式：关键决策点暂停
{
  type: "feedback_request",
  request_id: "fr-123",
  tool: "write_file",
  args: { path: "sort.py", content: "..." },
  message: "即将写入文件 sort.py",
  timestamp: "..."
}

// 模式切换通知
{
  type: "mode_changed",
  from: "PLAN",
  to: "WORK",
  timestamp: "..."
}

// WORK 模式：进度更新
{
  type: "iteration_update",
  iteration: 3,
  max_iterations: 50,
  timestamp: "..."
}
```

**Client → Server 新增事件**：

```typescript
// PLAN 模式：用户审批计划
{
  type: "plan_approved",
  plan: {
    steps: [
      { id: 1, action: "read_file", target: "auth.py", purpose: "了解当前实现", approved: true },
      { id: 2, action: "write_file", target: "oauth.py", purpose: "创建 OAuth 处理器", approved: true, modified: true }
    ]
  }
}

// PLAN 模式：用户拒绝计划（Agent 重新规划）
{
  type: "plan_rejected",
  feedback: "计划中缺少测试步骤"  // 可选反馈
}

// FEEDBACK 模式：用户反馈
{
  type: "feedback_response",
  request_id: "fr-123",
  action: "continue" | "adjust" | "stop",
  feedback: "可选反馈文字"
}
```

---

## 10. TRAE 配色方案

### 10.1 三套主题

| 主题 | 适用场景 | 主背景 | 主前景 |
|------|---------|--------|--------|
| Dark | 深色主题（默认） | `#1a1a2e` | `#e4e4ef` |
| Light | 浅色主题 | `#ffffff` | `#1a1a2e` |
| Medium | 中等主题 | `#2d2d44` | `#d4d4e8` |

### 10.2 CSS 变量定义

```css
/* Dark Theme (默认) */
:root[data-theme="dark"] {
  --bg-primary: #1a1a2e;
  --bg-secondary: #16162a;
  --bg-tertiary: #20203a;
  --bg-hover: #2a2a4a;
  --bg-active: #33335a;
  --text-primary: #e4e4ef;
  --text-secondary: #a0a0b8;
  --text-muted: #6b6b8a;
  --border: #2a2a4a;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --danger: #dc2626;
}

/* Light Theme */
:root[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f8;
  --bg-tertiary: #ebebf0;
  --bg-hover: #e0e0e8;
  --bg-active: #d0d0e0;
  --text-primary: #1a1a2e;
  --text-secondary: #4a4a6a;
  --text-muted: #8a8aa8;
  --border: #d0d0e0;
  --accent: #6366f1;
  --accent-hover: #4f46e5;
  --success: #16a34a;
  --warning: #d97706;
  --error: #dc2626;
  --danger: #b91c1c;
}

/* Medium Theme */
:root[data-theme="medium"] {
  --bg-primary: #2d2d44;
  --bg-secondary: #252538;
  --bg-tertiary: #353550;
  --bg-hover: #3d3d60;
  --bg-active: #454570;
  --text-primary: #d4d4e8;
  --text-secondary: #a0a0c0;
  --text-muted: #7070a0;
  --border: #3d3d60;
  --accent: #818cf8;
  --accent-hover: #a5b4fc;
  --success: #4ade80;
  --warning: #fbbf24;
  --error: #f87171;
  --danger: #ef4444;
}
```

### 10.3 后期自定义配色

- 前端提供主题编辑器（设置页面）
- 用户可修改 CSS 变量值
- 保存到 localStorage
- 支持导入/导出主题配置（JSON）

---

## 11. 侧边栏设计

### 11.1 布局

```
┌──────────────────┐
│ [Work ▾]  [+新建] │  ← 模式选择器 + 新建任务按钮
├──────────────────┤
│ 🔍 搜索任务...    │  ← 搜索框
│ [☰ 列表] [▦ 分组] │  ← 视图切换
├──────────────────┤
│ 📁 my-project     │  ← 工作目录分组
│   ├ 📝 实现排序    │  ← 任务项
│   │   └ [+]       │  ← 加号：在此目录新建任务
│   ├ 📝 修复Bug     │
│   ├ 📝 重构认证    │
│   └ [+]           │
│ 📁 other-project  │
│   ├ 📝 ...        │
│   └ [+]           │
├──────────────────┤
│ ⚙️ 设置  📖 历史  │  ← 底部操作
└──────────────────┘
```

### 11.2 模式选择器

- 左上角下拉菜单，默认显示 "Work"
- 选项：PLAN / WORK / FEEDBACK / RESEARCH
- 每个选项带图标和简短描述
- 选择模式后影响新建任务的执行方式

### 11.3 任务列表

- **视图模式**：
  - 分组视图（默认）：按工作目录分组
  - 列表视图：平铺所有任务
- **搜索**：输入关键字过滤任务名
- **任务项**：
  - 任务名称
  - 工作目录路径
  - 模式标识（PLAN/WORK/FEEDBACK/RESEARCH）
  - 状态指示器（进行中/已完成/失败）
  - 加号按钮：在此工作目录下新建任务

### 11.4 模型选择器

- 对话框右下角
- 点击展开模型选择面板
- **内置模型**：
  - GPT-4 Turbo
  - GPT-4o
  - GPT-3.5 Turbo
  - Claude 3.5 Sonnet（如果 API 支持）
- **自定义模型**：
  - 用户可添加自定义模型（名称 + API Base + API Key）
  - 保存到 localStorage
  - 支持切换 API 提供商（OpenAI / DeepSeek / 本地模型）

### 11.5 文件上传

- 对话框左下角
- 点击选择文件或拖拽上传
- 上传的文件复制到工作区 `.uploads/` 目录
- 在消息中显示文件引用
- Agent 可通过 `read_file` 读取上传的文件
