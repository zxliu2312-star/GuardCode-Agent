import { useEffect, useState, useRef } from 'react'
import { useAppStore } from './store/appStore'
import { wsService } from './services/wsService'
import Sidebar from './components/Sidebar'
import EmptyState from './components/EmptyState'
import ChatPanel from './components/ChatPanel'
import CodeEditor from './components/CodeEditor'
import FileTree from './components/FileTree'
import Terminal from './components/Terminal'
import ConfirmDialog from './components/ConfirmDialog'
import PlanEditor from './components/PlanEditor'
import FeedbackDialog from './components/FeedbackDialog'
import SettingsPanel from './components/SettingsPanel'
import { Square, X, RefreshCw, MessageCircle, PanelLeftClose, PanelLeft } from 'lucide-react'

function App() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useAppStore((s) => s.toggleSidebar)
  const terminalCollapsed = useAppStore((s) => s.terminalCollapsed)
  const toggleTerminal = useAppStore((s) => s.toggleTerminal)
  const session = useAppStore((s) => s.session)
  const messages = useAppStore((s) => s.chat.messages)
  const currentFile = useAppStore((s) => s.files.currentFile)
  const pendingConfirm = useAppStore((s) => s.pendingConfirm)
  const pendingPlan = useAppStore((s) => s.pendingPlan)
  const pendingFeedback = useAppStore((s) => s.pendingFeedback)
  const wsConnected = useAppStore((s) => s.wsConnected)

  const [showUpdateNotification, setShowUpdateNotification] = useState(false)
  const [showEditMenu, setShowEditMenu] = useState(false)
  const [showHelpMenu, setShowHelpMenu] = useState(false)

  const hasChat = messages.length > 0
  const editMenuRef = useRef<HTMLDivElement>(null)
  const helpMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (session.sessionId && session.isRunning) {
      console.log('[App] Running session, connecting WebSocket:', session.sessionId)
      wsService.connect(session.sessionId)
    } else {
      wsService.disconnect()
    }
  }, [session.sessionId, session.isRunning])

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (editMenuRef.current && !editMenuRef.current.contains(e.target as Node)) {
        setShowEditMenu(false)
      }
      if (helpMenuRef.current && !helpMenuRef.current.contains(e.target as Node)) {
        setShowHelpMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // ===== Edit menu actions =====
  const handleCopy = () => {
    const selection = window.getSelection()?.toString() || ''
    if (selection) {
      navigator.clipboard.writeText(selection)
    } else if (currentFile) {
      // Copy current file content
      const content = useAppStore.getState().files.fileContent
      navigator.clipboard.writeText(content)
    }
    setShowEditMenu(false)
  }

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (currentFile && text) {
        useAppStore.getState().setFileContent(text)
        useAppStore.getState().markUnsaved(true)
      }
    } catch (err) {
      console.error('Paste failed:', err)
    }
    setShowEditMenu(false)
  }

  const handleCut = () => {
    const selection = window.getSelection()?.toString() || ''
    if (selection) {
      navigator.clipboard.writeText(selection)
      // Clear selection
      window.getSelection()?.removeAllRanges()
    }
    setShowEditMenu(false)
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden" style={{ backgroundColor: '#f5f5f5' }}>
      {/* ===== Top Bar ===== */}
      <header
        className="flex items-center justify-between px-4 shrink-0"
        style={{ 
          height: '50px',
          backgroundColor: 'var(--bg-primary)', 
          borderBottom: '1px solid var(--border-light)',
        }}
      >
        {/* Left: Sidebar Toggle + Edit/Help Menu */}
        <div className="flex items-center gap-4">
          <button
            className="icon-btn"
            onClick={toggleSidebar}
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            {sidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>

          <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-secondary)' }}>
            {/* Edit Menu */}
            <div className="relative" ref={editMenuRef}>
              <button
                className="hover:text-primary transition-colors px-2 py-1 rounded"
                style={{ color: showEditMenu ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
                onClick={() => setShowEditMenu(!showEditMenu)}
              >
                编辑(E)
              </button>
              {showEditMenu && (
                <div
                  className="absolute z-50 mt-1 py-1 rounded-lg animate-fade-in"
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-light)',
                    boxShadow: 'var(--shadow-lg)',
                    minWidth: '140px',
                  }}
                >
                  <button
                    className="w-full text-left px-3 py-1.5 text-xs transition-colors hover:bg-gray-50"
                    style={{ color: 'var(--text-primary)' }}
                    onClick={handleCopy}
                  >
                    复制 (Ctrl+C)
                  </button>
                  <button
                    className="w-full text-left px-3 py-1.5 text-xs transition-colors hover:bg-gray-50"
                    style={{ color: 'var(--text-primary)' }}
                    onClick={handlePaste}
                  >
                    粘贴 (Ctrl+V)
                  </button>
                  <button
                    className="w-full text-left px-3 py-1.5 text-xs transition-colors hover:bg-gray-50"
                    style={{ color: 'var(--text-primary)' }}
                    onClick={handleCut}
                  >
                    剪切 (Ctrl+X)
                  </button>
                </div>
              )}
            </div>

            {/* Help Menu */}
            <div className="relative" ref={helpMenuRef}>
              <button
                className="hover:text-primary transition-colors px-2 py-1 rounded"
                style={{ color: showHelpMenu ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
                onClick={() => setShowHelpMenu(!showHelpMenu)}
              >
                帮助(H)
              </button>
              {showHelpMenu && (
                <div
                  className="absolute z-50 mt-1 p-4 rounded-lg animate-fade-in"
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-light)',
                    boxShadow: 'var(--shadow-lg)',
                    width: '360px',
                  }}
                >
                  <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                    GuardCode Agent 帮助
                  </h3>
                  <div className="space-y-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
                    <div>
                      <strong style={{ color: 'var(--text-primary)' }}>开始使用：</strong>
                      <p>1. 点击左侧"新建任务"创建任务</p>
                      <p>2. 选择工作区目录（本地文件夹）</p>
                      <p>3. 在输入框中输入编程任务</p>
                      <p>4. 按 Enter 发送，Shift+Enter 换行</p>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--text-primary)' }}>模型配置：</strong>
                      <p>点击底部模型选择器，可添加自定义模型（名称、API URL、Token）</p>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--text-primary)' }}>快捷键：</strong>
                      <p>Ctrl+C / Ctrl+V / Ctrl+X — 复制/粘贴/剪切</p>
                      <p>Ctrl+S — 保存文件</p>
                      <p>Enter — 发送消息</p>
                      <p>Shift+Enter — 换行</p>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--text-primary)' }}>安全提示：</strong>
                      <p>所有文件操作限制在工作区内，危险命令自动拦截</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center: Project Info */}
        <div className="flex items-center gap-3">
          {session.workspace && (
            <div className="flex items-center gap-2 text-sm">
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                {session.workspace}
              </span>
              {session.sessionId && (
                <>
                  <span style={{ color: 'var(--text-muted)' }}>·</span>
                  <span
                    className="flex items-center gap-1.5"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor: wsConnected ? 'var(--success)' : 'var(--text-muted)',
                      }}
                    />
                    {wsConnected ? '已连接' : '未连接'}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Right: Stop Button */}
        <div className="flex items-center gap-2">
          {session.isRunning && (
            <button
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
              style={{
                backgroundColor: 'var(--danger)',
                color: '#fff',
              }}
              onClick={() => wsService.sendStop()}
            >
              <Square size={14} />
              <span>停止</span>
            </button>
          )}
        </div>
      </header>

      {/* Update Notification - Floating */}
      {showUpdateNotification && (
        <div
          className="fixed z-50 animate-slide-down"
          style={{
            top: '60px',
            right: '20px',
            width: '340px',
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-light)',
            borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-lg)',
            padding: '12px 16px',
          }}
        >
          <div className="flex items-start gap-3">
            <div
              className="flex items-center justify-center w-8 h-8 rounded-full shrink-0"
              style={{ backgroundColor: 'var(--accent-lighter)' }}
            >
              <RefreshCw size={16} style={{ color: 'var(--accent-primary)' }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                更新就绪
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                点击重启以更新
              </div>
            </div>
            <button
              className="px-3 py-1 rounded-md text-xs font-medium"
              style={{
                backgroundColor: 'var(--text-primary)',
                color: 'var(--bg-primary)',
              }}
            >
              更新
            </button>
            <button
              className="icon-btn"
              style={{ width: '24px', height: '24px' }}
              onClick={() => setShowUpdateNotification(false)}
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* ===== Main Content Area ===== */}
      <div className="flex flex-1 overflow-hidden p-3 gap-3" style={{ backgroundColor: '#f5f5f5' }}>
        {/* Left Sidebar */}
        {!sidebarCollapsed && <Sidebar />}

        {/* Center: Chat / Empty State */}
        <main
          className="flex-1 flex flex-col overflow-hidden rounded-xl"
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid var(--border-light)',
          }}
        >
          {hasChat ? <ChatPanel /> : <EmptyState />}
        </main>

        {/* Right: Code Editor + File Tree */}
        {currentFile && (
          <aside
            className="flex flex-col overflow-hidden rounded-xl"
            style={{
              width: '45%',
              minWidth: '400px',
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-light)',
            }}
          >
            <FileTree />
            <CodeEditor />
          </aside>
        )}
      </div>

      {/* ===== Bottom: Terminal ===== */}
      {!terminalCollapsed && <Terminal />}

      {/* Floating Assistant - Bottom Right */}
      <button
        className="fixed z-50 transition-all"
        style={{
          bottom: '20px',
          right: '20px',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--bg-primary)',
          boxShadow: 'var(--shadow-floating)',
          border: '1px solid var(--border-light)',
        }}
        onClick={toggleTerminal}
        title="助手"
      >
        <div className="flex items-center justify-center w-full h-full">
          <MessageCircle size={22} style={{ color: 'var(--accent-primary)' }} strokeWidth={1.5} />
        </div>
      </button>

      {/* ===== Modals ===== */}
      {pendingConfirm && <ConfirmDialog />}
      {pendingPlan && <PlanEditor />}
      {pendingFeedback && <FeedbackDialog />}
      <SettingsPanel />
    </div>
  )
}

export default App
