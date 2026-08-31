# GuardCode Agent — 前端实施计划

> 本文档独立于原有 `PLAN.md`，专注于 Web 前端的实施策略和时间安排。
> 后端 Agent 核心已全部通过测试，本计划在此基础上新增 API 适配层和前端界面。

---

## 1. 目标

在已有 GuardCode Agent 后端基础上，一天内完成 TRAE 式 Web 前端界面：

- **后端 API 适配层**：FastAPI + WebSocket，将同步 Agent loop 适配为事件驱动
- **前端界面**：React + Monaco Editor + 文件树 + AI 聊天面板 + 终端
- **实时通信**：WebSocket 推送工具调用、结果、风险警告、确认请求

---

## 2. 实施策略

### 2.1 核心原则

- **后端零侵入**：不修改 `guardcode/` 目录下任何代码，通过 monkey-patch + 适配层接入
- **先 API 后 UI**：先完成 API 适配层（SPEC 4.1），前端才有数据可连
- **AI 协作加速**：每个组件都有明确的接口定义和代码示例，AI 可直接生成
- **垂直切片**：先打通一条完整链路（创建会话→发送任务→看到工具调用→完成），再补细节

### 2.2 为什么先完成 API 适配层（SPEC 4.1）

```
后端 Agent 核心（已完成）
        ↓ 需要 API 适配层作为桥梁
API 适配层（FastAPI + WebSocket）  ← 必须先完成
        ↓ 前端才有数据可连
前端界面（React）                  ← 后完成
```

API 适配层是前后端之间的唯一桥梁。没有它，前端的 WebSocket 和 REST 调用都没有接收端。
先完成 4.1 的 `AgentSession` 适配器和 FastAPI 路由，前端开发时就能直接连接真实后端，避免 mock 数据的浪费。

### 2.3 验证标准

| 阶段 | 验证方式 |
|------|----------|
| API 适配层完成 | `curl` 创建会话 + `wscat` 连接 WebSocket 发送任务，收到 tool_call 事件 |
| 前端骨架完成 | 浏览器打开，三栏布局可见，WebSocket 连接成功 |
| 核心组件完成 | 提交任务，聊天面板实时显示工具调用和结果 |
| 集成打磨完成 | 文件树点击打开文件，编辑器保存，终端显示命令输出，确认弹窗工作 |

---

## 3. 分阶段实施

### Phase F1：后端 API 适配层（2-3 小时）

**目标**：将同步 `run_agent_loop` 适配为 WebSocket 事件流，提供 REST API。

**为什么最先做**：这是前后端之间的桥梁。前端所有功能都依赖此层。

#### F1.1 安装依赖
- [ ] `pip install fastapi uvicorn[standard] websockets`
- [ ] 更新 `requirements.txt`

#### F1.2 Agent 适配器（SPEC 4.1）
- [ ] 创建 `api/agent_adapter.py`
  - [ ] `AgentSession` 类：线程 + 事件队列
  - [ ] monkey-patch `_print_tool_call` / `_print_tool_result` 为事件发射器
  - [ ] `start(task)` 在后台线程启动 agent
  - [ ] `get_events()` 非阻塞获取事件
  - [ ] `confirm(tool_call_id, approved)` 用户确认响应
  - [ ] `stop()` 停止 agent

#### F1.3 FastAPI 服务器
- [ ] 创建 `api/server.py`（FastAPI 入口 + CORS）
- [ ] 创建 `api/routes/sessions.py`
  - [ ] `POST /api/sessions` 创建会话
  - [ ] `GET /api/sessions` 列出会话
  - [ ] `GET /api/sessions/{id}` 获取会话状态
- [ ] 创建 `api/routes/files.py`
  - [ ] `GET /api/files?path=...` 列出/读取文件
  - [ ] `PUT /api/files` 写入文件
  - [ ] `DELETE /api/files?path=...` 删除文件
- [ ] 创建 `api/routes/ws.py`
  - [ ] `WebSocket /api/sessions/{id}/ws` 事件流端点
  - [ ] 接收 `start` / `confirm_response` / `stop` 事件
  - [ ] 推送 `tool_call` / `tool_result` / `done` / `error` 事件

#### F1.4 验证
- [ ] `curl -X POST http://localhost:8000/api/sessions -d '{"workspace":"."}'` 创建会话
- [ ] `wscat -c ws://localhost:8000/api/sessions/{id}/ws` 连接 WebSocket
- [ ] 发送 `{"type":"start","task":"list files"}` 收到 tool_call 事件
- [ ] `curl http://localhost:8000/api/files?path=.` 返回文件列表

---

### Phase F2：前端骨架 + 布局（1-2 小时）

**目标**：搭建 React 项目，实现三栏布局，WebSocket 连接成功。

#### F2.1 项目初始化
- [ ] `npm create vite@latest frontend -- --template react-ts`
- [ ] 安装依赖：`tailwindcss`, `zustand`, `lucide-react`, `@monaco-editor/react`, `@xterm/xterm`, `@xterm/addon-fit`
- [ ] 配置 Tailwind CSS
- [ ] 配置 Vite proxy（`/api` → `localhost:8000`）

#### F2.2 类型定义
- [ ] 创建 `src/types/index.ts`
  - [ ] `ChatMessage` 联合类型
  - [ ] `FileNode` 类型
  - [ ] `TerminalOutput` 类型
  - [ ] `ConfirmRequest` 类型
  - [ ] `WebSocketEvent` 类型

#### F2.3 状态管理
- [ ] 创建 `src/store/appStore.ts`（Zustand）
  - [ ] 会话状态：sessionId, workspace, isRunning
  - [ ] 文件状态：fileTree, currentFile, fileContent
  - [ ] 聊天状态：messages
  - [ ] 终端状态：terminalOutput
  - [ ] 确认状态：pendingConfirm

#### F2.4 布局骨架
- [ ] `App.tsx` 三栏布局 + 顶部栏 + 底部终端
- [ ] 顶部栏：GuardCode 标题 + 会话状态 + 停止按钮
- [ ] 左栏占位：FileTree（空状态）
- [ ] 中栏占位：CodeEditor（空状态）
- [ ] 右栏占位：ChatPanel（空状态 + 输入框）
- [ ] 底部占位：Terminal（可折叠）

#### F2.5 WebSocket 连接
- [ ] 创建 `src/hooks/useWebSocket.ts`
  - [ ] 连接 WebSocket
  - [ ] 事件分发到 store
  - [ ] 断线重连
- [ ] 创建 `src/api/client.ts`
  - [ ] REST API 封装：createSession, getFiles, writeFile, deleteFile

#### F2.6 验证
- [ ] 浏览器打开 `localhost:5173`，三栏布局可见
- [ ] 输入 workspace 路径，创建会话
- [ ] WebSocket 连接成功（控制台无报错）
- [ ] 发送任务，聊天面板显示 tool_call 事件

---

### Phase F3：核心组件实现（3-4 小时）

**目标**：实现所有核心组件，完整展示 Agent 工作过程。

#### F3.1 FileTree 组件
- [ ] 递归渲染目录树
- [ ] 文件夹展开/折叠
- [ ] 文件图标按扩展名区分（.py, .js, .md, .json 等）
- [ ] 点击文件触发 `onFileSelect` → 调用 `GET /api/files` → 打开编辑器
- [ ] Agent 修改文件后自动刷新文件树

#### F3.2 CodeEditor 组件
- [ ] Monaco Editor 集成
- [ ] 按文件扩展名自动切换语言模式
- [ ] Ctrl+S 保存（`PUT /api/files`）
- [ ] 未保存提示（文件名旁显示 ●）
- [ ] Agent 修改文件后自动刷新内容
- [ ] Diff 视图（Agent 修改前后对比，可选）

#### F3.3 ChatPanel 组件
- [ ] 消息列表渲染
  - [ ] user 消息：右对齐气泡
  - [ ] assistant 消息：左对齐，支持 Markdown 渲染
  - [ ] tool_call：ToolCallCard 组件
  - [ ] tool_result：ToolCallCard 组件（带结果）
  - [ ] system 消息：居中，带图标
- [ ] 底部输入框 + 发送按钮
- [ ] Agent 运行时显示停止按钮
- [ ] 自动滚动到最新消息
- [ ] 空状态提示："输入编程任务开始对话"

#### F3.4 ToolCallCard 组件
- [ ] 工具名 + 图标（read_file=📄, write_file=✏️, run_command=⚡, list_files=📁, delete_file=🗑️）
- [ ] 参数摘要（一行显示关键参数）
- [ ] 可折叠展开查看完整参数和结果
- [ ] 成功 ✓ 绿色，失败 ✗ 红色
- [ ] read_file 结果：点击"在编辑器中打开"
- [ ] write_file 结果：点击"查看 diff"

#### F3.5 Terminal 组件
- [ ] xterm.js 集成
- [ ] 展示 `run_command` 的 stdout/stderr
- [ ] 命令执行时实时追加输出
- [ ] ANSI 颜色支持
- [ ] 可折叠/展开
- [ ] 自动滚动到底部

#### F3.6 ConfirmDialog 组件
- [ ] 模态弹窗
- [ ] 显示工具名、参数、风险等级
- [ ] "确认执行" / "拒绝" 按钮
- [ ] 风险等级颜色：DANGEROUS=红色边框，BLOCKED=灰色
- [ ] 点击后发送 `confirm_response` WebSocket 事件

#### F3.7 验证
- [ ] 提交任务 "create hello.txt with content 'Hello World'"
- [ ] 聊天面板显示：tool_call(write_file) → tool_result(success)
- [ ] 文件树自动刷新，显示 hello.txt
- [ ] 点击文件树中的 hello.txt，编辑器打开显示内容
- [ ] 提交任务 "delete hello.txt"
- [ ] 确认弹窗弹出，点击"确认执行"
- [ ] 文件树自动刷新，hello.txt 消失

---

### Phase F4：集成与打磨（1-2 小时）

**目标**：完善交互细节，确保端到端体验流畅。

#### F4.1 会话管理
- [ ] 启动时选择 workspace 目录
- [ ] 会话列表（侧边栏或下拉菜单）
- [ ] 切换会话

#### F4.2 错误处理
- [ ] WebSocket 断线重连 + 提示
- [ ] API 调用失败 toast 提示
- [ ] Agent 错误在聊天面板显示

#### F4.3 交互优化
- [ ] 文件树搜索/过滤
- [ ] 聊天面板消息搜索（可选）
- [ ] 编辑器多标签页（可选）
- [ ] 终端清空按钮
- [ ] 深色/浅色主题切换（可选）

#### F4.4 响应式设计
- [ ] 窗口缩小时三栏可折叠
- [ ] 移动端基本可用（可选）

#### F4.5 验证
- [ ] 端到端测试：提交编程任务 → Agent 自主完成 → 文件树更新 → 编辑器显示代码 → 终端显示测试结果
- [ ] 断网恢复测试：断开网络 → 提示 → 恢复 → 自动重连
- [ ] 危险操作测试：提交删除任务 → 确认弹窗 → 拒绝 → Agent 继续

---

## 4. 技术选型理由

### 4.1 为什么选 FastAPI

| 对比项 | FastAPI | Flask | Django |
|--------|---------|-------|--------|
| WebSocket 原生支持 | ✅ | ❌（需扩展） | ❌ |
| 异步支持 | ✅ 原生 | ❌ | 部分 |
| 自动文档 | ✅ OpenAPI | ❌ | ❌ |
| 学习成本 | 低 | 低 | 高 |
| 与 Python Agent 集成 | 直接 import | 直接 import | 过重 |

### 4.2 为什么选 React + Vite

| 对比项 | React + Vite | Vue + Vite | Svelte |
|--------|--------------|-----------|--------|
| Monaco Editor 集成 | `@monaco-editor/react` 成熟 | 需手动封装 | 需手动封装 |
| xterm.js 集成 | 成熟方案 | 可用 | 需适配 |
| AI 生成代码质量 | 最高（训练数据最多） | 高 | 一般 |
| 生态规模 | 最大 | 大 | 小 |

### 4.3 为什么选 Zustand 而非 Redux

- Zustand：5 分钟上手，零 boilerplate，适合中小型项目
- Redux：过度工程化，对于单页工具应用不必要

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Agent loop 同步阻塞 | WebSocket 无法推送事件 | 线程 + 事件队列适配（SPEC 4.1） |
| 用户确认阻塞线程 | Agent 卡死等待确认 | `confirm_queue` 超时机制（30s 自动拒绝） |
| Monaco Editor 加载慢 | 首屏白屏 | loading 占位符 + CDN 加载 |
| WebSocket 断线 | 事件丢失 | 断线重连 + 状态恢复 |
| 文件树深层递归 | 渲染卡顿 | 虚拟滚动（react-arborist）或懒加载 |
| 跨域问题 | 前端无法调用 API | CORS 中间件 + Vite proxy |

---

## 6. 测试策略

### 6.1 API 适配层测试
- `curl` 测试所有 REST 端点
- `wscat` 测试 WebSocket 事件流
- 单元测试：`AgentSession` 的事件队列和确认机制

### 6.2 前端测试
- 手动测试：提交任务 → 观察事件流 → 验证 UI 更新
- 关键场景：
  - 文件操作（创建/读取/修改/删除）
  - 命令执行（终端输出）
  - 危险操作（确认弹窗）
  - 上下文压缩（系统消息）
  - Agent 完成（最终消息）

### 6.3 端到端测试
```
1. 创建会话（workspace = 测试目录）
2. 提交任务 "implement bubble sort with tests"
3. 验证：
   - 聊天面板显示工具调用链
   - 文件树出现 sort.py 和 test_sort.py
   - 编辑器可打开查看代码
   - 终端显示 pytest 输出
   - Agent 完成后显示最终消息
```

---

## 7. 时间表

| Phase | 任务 | 预计时间 | 交付物 |
|-------|------|----------|--------|
| F1 | 后端 API 适配层 | 2-3 小时 | FastAPI 服务器 + WebSocket 事件流 |
| F2 | 前端骨架 + 布局 | 1-2 小时 | 三栏布局 + WebSocket 连接 |
| F3 | 核心组件实现 | 3-4 小时 | 编辑器/文件树/聊天/终端/确认弹窗 |
| F4 | 集成与打磨 | 1-2 小时 | 端到端流畅体验 |
| **总计** | | **7-11 小时** | **完整可用的 TRAE 式前端** |

---

## 8. 启动检查清单

开始实施前确认：

- [ ] 后端测试全部通过（`pytest tests/`）
- [ ] `OPENAI_API_KEY` 环境变量已设置
- [ ] Node.js 18+ 已安装
- [ ] Python 3.10+ 已安装
- [ ] 工作区目录可访问
