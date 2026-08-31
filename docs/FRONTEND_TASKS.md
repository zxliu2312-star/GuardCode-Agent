# GuardCode Agent — 前端任务清单

> 本文档独立于原有 `TASKS.md`，专注于 Web 前端的实施任务。
> 后端 Agent 核心已全部通过测试，本清单覆盖 API 适配层 + 前端界面。

---

## Phase F1：后端 API 适配层（2-3 小时）

> **必须最先完成。** 这是前后端之间的桥梁，前端所有功能都依赖此层。
> 对应 FRONTEND_SPEC.md §4。

### F1.1 环境准备
- [ ] 安装后端依赖
  - [ ] `pip install fastapi uvicorn[standard] websockets`
  - [ ] 更新 `requirements.txt`（追加 fastapi, uvicorn, websockets）
- [ ] 创建 `api/` 目录结构
  - [ ] `api/__init__.py`
  - [ ] `api/server.py`
  - [ ] `api/routes/__init__.py`
  - [ ] `api/routes/sessions.py`
  - [ ] `api/routes/files.py`
  - [ ] `api/routes/ws.py`
  - [ ] `api/agent_adapter.py`

### F1.2 Agent 适配器（SPEC §4.1 — 核心中的核心）
- [ ] 实现 `AgentSession` 类
  - [ ] `__init__(session_id, workspace)`：初始化事件队列、确认队列、线程
  - [ ] `start(task)`：在后台线程启动 `run_agent_loop`
  - [ ] `_run_agent(task)`：线程目标函数
    - [ ] 加载 config（`load_config(workspace=self.workspace)`）
    - [ ] monkey-patch `agent_mod._print_tool_call` → 事件发射器
    - [ ] monkey-patch `agent_mod._print_tool_result` → 事件发射器
    - [ ] 调用 `run_agent_loop(task, config=config)`
    - [ ] 完成后推入 `{"type": "done", "content": result}` 事件
    - [ ] 异常时推入 `{"type": "error", "message": str(e)}` 事件
    - [ ] finally 恢复原始 print 函数 + 设置 `is_running = False`
  - [ ] `get_events() -> list[dict]`：非阻塞获取所有待处理事件
  - [ ] `confirm(tool_call_id, approved)`：向 confirm_queue 推入响应
  - [ ] `stop()`：设置 `is_running = False` + 推入 stopped 事件
- [ ] 全局会话管理
  - [ ] `sessions: dict[str, AgentSession]` 全局字典
  - [ ] `create_session(workspace) -> AgentSession`
  - [ ] `get_session(session_id) -> AgentSession | None`

### F1.3 REST 路由 — 会话管理
- [ ] `api/routes/sessions.py`
  - [ ] `POST /api/sessions` — 创建会话
    - [ ] 接收 `{"workspace": "/path"}`
    - [ ] 调用 `create_session(workspace)`
    - [ ] 返回 `{"session_id": "...", "workspace": "..."}`
  - [ ] `GET /api/sessions` — 列出所有会话
    - [ ] 返回 `[{"session_id": "...", "workspace": "...", "is_running": bool}]`
  - [ ] `GET /api/sessions/{session_id}` — 获取会话状态
    - [ ] 返回 `{"session_id": "...", "workspace": "...", "is_running": bool}`

### F1.4 REST 路由 — 文件操作
- [ ] `api/routes/files.py`
  - [ ] `GET /api/files?path=...` — 列出/读取文件
    - [ ] path 是目录 → 返回 `{"type": "directory", "entries": [...]}`
    - [ ] path 是文件 → 返回 `{"type": "file", "content": "..."}`
    - [ ] 复用后端 `validate_path()` 做路径校验
  - [ ] `PUT /api/files` — 写入文件
    - [ ] 接收 `{"path": "...", "content": "..."}`
    - [ ] 复用后端 `write_file` 工具或直接写文件
    - [ ] 返回 `{"success": true, "path": "..."}`
  - [ ] `DELETE /api/files?path=...` — 删除文件
    - [ ] 复用后端 `delete_file` 工具
    - [ ] 返回 `{"success": true, "path": "..."}`

### F1.5 WebSocket 路由
- [ ] `api/routes/ws.py`
  - [ ] `WebSocket /api/sessions/{session_id}/ws`
  - [ ] 连接时验证 session_id 存在
  - [ ] 接收 Client → Server 事件：
    - [ ] `{"type": "start", "task": "..."}` → 调用 `session.start(task)`
    - [ ] `{"type": "confirm_response", "tool_call_id": "...", "approved": bool}` → 调用 `session.confirm()`
    - [ ] `{"type": "stop"}` → 调用 `session.stop()`
  - [ ] 推送 Server → Client 事件：
    - [ ] 轮询 `session.get_events()`（每 100ms）
    - [ ] 收到事件后 `json.dumps` 推送
    - [ ] 事件类型：tool_call, tool_result, done, error, stopped

### F1.6 FastAPI 服务器入口
- [ ] `api/server.py`
  - [ ] 创建 FastAPI app
  - [ ] 添加 CORS 中间件（允许 `localhost:5173`）
  - [ ] 注册路由（sessions, files, ws）
  - [ ] `if __name__ == "__main__": uvicorn.run(app, host="127.0.0.1", port=8000)`

### F1.7 验证
- [ ] 启动服务器：`python -m api.server`
- [ ] `curl -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d "{\"workspace\":\".\"}"` → 返回 session_id
- [ ] `curl http://localhost:8000/api/files?path=.` → 返回文件列表
- [ ] `curl http://localhost:8000/api/files?path=README.md` → 返回文件内容
- [ ] 用 wscat 或浏览器 WebSocket 连接，发送 `{"type":"start","task":"list files"}` → 收到 tool_call 事件

---

## Phase F2：前端骨架 + 布局（1-2 小时）

> 对应 FRONTEND_SPEC.md §5。

### F2.1 项目初始化
- [ ] 创建 React 项目
  - [ ] `npm create vite@latest frontend -- --template react-ts`
  - [ ] `cd frontend && npm install`
- [ ] 安装核心依赖
  - [ ] `npm install @monaco-editor/react @xterm/xterm @xterm/addon-fit zustand lucide-react`
  - [ ] `npm install -D tailwindcss postcss autoprefixer`
  - [ ] `npx tailwindcss init -p`
- [ ] 配置 Tailwind CSS
  - [ ] `tailwind.config.js`（content 路径配置）
  - [ ] `postcss.config.js`
  - [ ] `src/index.css`（Tailwind 指令）
- [ ] 配置 Vite proxy
  - [ ] `vite.config.ts` 添加 `/api` 代理到 `localhost:8000`
  - [ ] `vite.config.ts` 添加 `/ws` 代理（WebSocket）

### F2.2 类型定义
- [ ] `src/types/index.ts`
  - [ ] `ChatMessage` 联合类型（user, assistant, tool_call, tool_result, system）
  - [ ] `FileNode` 类型（name, type, path, children）
  - [ ] `TerminalOutput` 类型（command, stdout, stderr, exitCode）
  - [ ] `ConfirmRequest` 类型（tool_call_id, tool, args, message）
  - [ ] `ServerEvent` 类型（WebSocket 事件联合类型）
  - [ ] `ClientEvent` 类型（WebSocket 发送事件联合类型）

### F2.3 状态管理
- [ ] `src/store/appStore.ts`（Zustand）
  - [ ] 会话状态：`sessionId`, `workspace`, `isRunning`
  - [ ] 文件状态：`fileTree`, `currentFile`, `fileContent`, `unsavedChanges`
  - [ ] 聊天状态：`messages: ChatMessage[]`
  - [ ] 终端状态：`terminalOutput: TerminalOutput[]`
  - [ ] 确认状态：`pendingConfirm: ConfirmRequest | null`
  - [ ] Actions：`setSession`, `setRunning`, `setFileTree`, `openFile`, `addMessage`, `addTerminalOutput`, `setPendingConfirm`

### F2.4 API 客户端
- [ ] `src/api/client.ts`
  - [ ] `createSession(workspace: string): Promise<{session_id, workspace}>`
  - [ ] `listFiles(path: string): Promise<FileNode[]>`
  - [ ] `readFile(path: string): Promise<{content: string}>`
  - [ ] `writeFile(path: string, content: string): Promise<{success: boolean}>`
  - [ ] `deleteFile(path: string): Promise<{success: boolean}>`

### F2.5 WebSocket Hook
- [ ] `src/hooks/useWebSocket.ts`
  - [ ] 连接 `ws://localhost:8000/api/sessions/{sessionId}/ws`
  - [ ] `onmessage` 事件分发到 store
    - [ ] `tool_call` → `store.addMessage({role: "tool_call", ...})`
    - [ ] `tool_result` → `store.addMessage({role: "tool_result", ...})`
    - [ ] `confirm_request` → `store.setPendingConfirm(data)`
    - [ ] `context_compress` → `store.addMessage({role: "system", type: "compress", ...})`
    - [ ] `done` → `store.setRunning(false)` + `store.addMessage({role: "assistant", ...})`
    - [ ] `error` → `store.setRunning(false)` + `store.addMessage({role: "system", type: "error", ...})`
  - [ ] `sendStart(task: string)` 发送 `{"type": "start", "task": ...}`
  - [ ] `sendConfirm(tool_call_id: string, approved: boolean)` 发送 confirm_response
  - [ ] `sendStop()` 发送 `{"type": "stop"}`
  - [ ] 断线重连（3 秒间隔，最多 5 次）

### F2.6 布局骨架
- [ ] `src/App.tsx`
  - [ ] 顶部栏：GuardCode 标题 + workspace 输入 + 会话状态指示器 + 停止按钮
  - [ ] 左栏（w-64）：FileTree 占位（"选择 workspace 后显示文件"）
  - [ ] 中栏（flex-1）：CodeEditor 占位（"点击文件树中的文件打开编辑器"）
  - [ ] 右栏（w-96）：ChatPanel 占位（输入框 + "输入编程任务开始对话"）
  - [ ] 底部（h-48）：Terminal 占位（可折叠）
  - [ ] 会话创建流程：输入 workspace → `createSession()` → 连接 WebSocket → 加载文件树

### F2.7 验证
- [ ] `npm run dev` 启动前端
- [ ] 浏览器打开 `http://localhost:5173`
- [ ] 三栏布局可见
- [ ] 输入 workspace 路径，创建会话
- [ ] 控制台无 WebSocket 报错
- [ ] 发送任务 "list files"，聊天面板显示 tool_call 事件

---

## Phase F3：核心组件实现（3-4 小时）

### F3.1 FileTree 组件
- [ ] `src/components/FileTree.tsx`
  - [ ] 递归渲染目录树（`FileNode[]` → 树形结构）
  - [ ] 文件夹点击展开/折叠（本地 state 管理展开状态）
  - [ ] 文件图标按扩展名区分
    - [ ] `.py` → 🐍 / `.js` → 📜 / `.json` → 📋 / `.md` → 📝 / 默认 → 📄
    - [ ] 文件夹 → 📁（展开）/ 📂（折叠）
  - [ ] 点击文件 → `onFileSelect(path)` → 调用 `readFile(path)` → 更新 store
  - [ ] Agent write_file/delete_file 后自动刷新（监听 store.messages 变化）
  - [ ] 空状态："请先选择 workspace"

### F3.2 CodeEditor 组件
- [ ] `src/components/CodeEditor.tsx`
  - [ ] Monaco Editor 集成（`@monaco-editor/react`）
  - [ ] 按文件扩展名自动切换语言
    - [ ] `.py` → python / `.js` → javascript / `.json` → json / `.md` → markdown
  - [ ] Ctrl+S 保存
    - [ ] 调用 `writeFile(currentFile, content)`
    - [ ] 保存成功 toast 提示
    - [ ] 清除 unsavedChanges 标记
  - [ ] 未保存提示：文件名旁显示 ●
  - [ ] Agent 修改文件后自动刷新
    - [ ] 监听 tool_result 中 write_file 事件
    - [ ] 如果修改的是当前打开的文件 → 重新 `readFile` → 更新内容
    - [ ] 显示 toast "文件被 Agent 修改，已刷新"
  - [ ] 空状态："点击文件树中的文件打开编辑器"
  - [ ] 深色主题（与整体 UI 一致）

### F3.3 ChatPanel 组件
- [ ] `src/components/ChatPanel.tsx`
  - [ ] 消息列表渲染
    - [ ] user 消息：右对齐，蓝色气泡
    - [ ] assistant 消息：左对齐，支持基本 Markdown（代码块高亮）
    - [ ] tool_call：渲染 `<ToolCallCard>`
    - [ ] tool_result：渲染 `<ToolCallCard>`（带 result）
    - [ ] system 消息：居中，带图标（compress=📊, error=❌, warning=⚠️）
  - [ ] 底部输入框
    - [ ] 多行文本输入（textarea）
    - [ ] Enter 发送 / Shift+Enter 换行
    - [ ] 发送按钮
    - [ ] Agent 运行时禁用输入 + 显示停止按钮
  - [ ] 自动滚动到最新消息（`useRef` + `scrollIntoView`）
  - [ ] 空状态："输入编程任务开始对话 🚀"

### F3.4 ToolCallCard 组件
- [ ] `src/components/ToolCallCard.tsx`
  - [ ] 工具图标映射
    - [ ] read_file → 📄 / write_file → ✏️ / list_files → 📁
    - [ ] delete_file → 🗑️ / run_command → ⚡
  - [ ] 参数摘要（一行显示关键参数）
    - [ ] read_file: `path: "src/main.py"`
    - [ ] write_file: `path: "sort.py", content: <512 chars>`
    - [ ] run_command: `command: "pytest -v"`
  - [ ] 可折叠展开
    - [ ] 展开后显示完整参数 JSON
    - [ ] 展开后显示完整结果 JSON
  - [ ] 状态标识
    - [ ] 进行中：⏳ 黄色（有 tool_call 无 tool_result）
    - [ ] 成功：✓ 绿色
    - [ ] 失败：✗ 红色
  - [ ] 交互按钮
    - [ ] read_file 结果：点击"在编辑器中打开" → `openFile(path, content)`
    - [ ] write_file 结果：点击"查看 diff" → 打开 diff 视图（可选）

### F3.5 Terminal 组件
- [ ] `src/components/Terminal.tsx`
  - [ ] xterm.js 集成（`@xterm/xterm` + `@xterm/addon-fit`）
  - [ ] 监听 store.terminalOutput 变化
    - [ ] 新增 output 时 `term.writeln(text)` 写入
    - [ ] stdout 白色，stderr 红色
  - [ ] 命令分隔线：`--- $ pytest -v ---`
  - [ ] 自动滚动到底部
  - [ ] 可折叠/展开（点击标题栏切换）
  - [ ] 清空按钮
  - [ ] 空状态：终端无输出时显示"Agent 执行的命令输出将显示在这里"

### F3.6 ConfirmDialog 组件
- [ ] `src/components/ConfirmDialog.tsx`
  - [ ] 模态弹窗（fixed inset-0 + backdrop-blur）
  - [ ] 显示内容
    - [ ] 工具名 + 风险等级标签
    - [ ] 完整参数（JSON 格式化）
    - [ ] 警告消息
  - [ ] 风险等级颜色
    - [ ] DANGEROUS：红色边框 + 红色标题
    - [ ] BLOCKED：灰色边框 + "已阻止"文字
  - [ ] 按钮
    - [ ] "确认执行"（红色按钮，DANGEROUS 时）
    - [ ] "拒绝"（灰色按钮）
  - [ ] 点击后调用 `sendConfirm(tool_call_id, approved)` + `setPendingConfirm(null)`

### F3.7 验证
- [ ] 提交任务 "create a file hello.txt with content 'Hello World'"
  - [ ] 聊天面板显示 tool_call(write_file) → tool_result(success)
  - [ ] 文件树自动刷新，显示 hello.txt
  - [ ] 点击 hello.txt，编辑器打开显示 "Hello World"
- [ ] 提交任务 "delete hello.txt"
  - [ ] 确认弹窗弹出
  - [ ] 点击"拒绝" → Agent 收到拒绝，继续
  - [ ] 再次提交，点击"确认执行" → 文件删除
  - [ ] 文件树自动刷新，hello.txt 消失
- [ ] 提交任务 "run pytest"
  - [ ] 终端面板显示命令输出
  - [ ] 聊天面板显示 tool_call(run_command) → tool_result

---

## Phase F4：集成与打磨（1-2 小时）

### F4.1 会话管理
- [ ] 启动页面：workspace 路径输入 + "连接" 按钮
- [ ] 会话状态指示器：● Running / ● Idle / ● Error
- [ ] 停止按钮：Agent 运行时可点击停止

### F4.2 错误处理
- [ ] WebSocket 断线：显示"连接断开，正在重连..."提示
- [ ] API 调用失败：toast 错误提示
- [ ] Agent 错误：聊天面板显示红色系统消息

### F4.3 交互优化
- [ ] 文件树：搜索框过滤文件名
- [ ] 聊天面板：消息时间戳显示
- [ ] 编辑器：文件修改未保存时关闭确认
- [ ] 终端：自动折叠（Agent 不执行命令时）

### F4.4 视觉打磨
- [ ] 统一深色主题
- [ ] 组件间距和对齐
- [ ] 过渡动画（展开/折叠、弹窗）
- [ ] Loading 状态（Monaco 加载中、文件读取中）

### F4.5 端到端验收
- [ ] 场景 1：简单文件操作
  - [ ] 提交 "create notes.txt with my TODO list"
  - [ ] 验证：文件树更新 + 编辑器可打开 + 内容合理
- [ ] 场景 2：代码生成 + 测试
  - [ ] 提交 "implement bubble sort in Python with tests"
  - [ ] 验证：sort.py + test_sort.py 出现在文件树
  - [ ] 验证：终端显示 pytest 输出
  - [ ] 验证：编辑器可查看代码
- [ ] 场景 3：危险操作确认
  - [ ] 提交 "delete all temporary files"
  - [ ] 验证：确认弹窗弹出
  - [ ] 验证：拒绝后 Agent 继续
- [ ] 场景 4：上下文压缩
  - [ ] 提交需要多轮迭代的任务
  - [ ] 验证：聊天面板显示压缩系统消息
- [ ] 场景 5：Agent 完成
  - [ ] 验证：最终消息显示在聊天面板
  - [ ] 验证：状态指示器变为 Idle

---

## 交付前检查

### 功能完整性
- [ ] 三栏布局正常（文件树 | 编辑器 | 聊天面板）
- [ ] 底部终端可折叠
- [ ] WebSocket 连接稳定
- [ ] 文件树正确展示目录结构
- [ ] 编辑器支持语法高亮
- [ ] 聊天面板展示所有消息类型
- [ ] 工具调用卡片可折叠
- [ ] 确认弹窗正常工作
- [ ] 终端显示命令输出
- [ ] Agent 完成后状态正确

### 代码质量
- [ ] TypeScript 类型完整
- [ ] 无 console.error
- [ ] 组件职责单一
- [ ] API 客户端封装完整

### 文档
- [ ] FRONTEND_SPEC.md 完整
- [ ] FRONTEND_PLAN.md 完整
- [ ] FRONTEND_TASKS.md 完整
- [ ] README.md 更新启动方式
