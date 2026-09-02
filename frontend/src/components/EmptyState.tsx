import { useState, useRef, useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import { wsService } from '../services/wsService'
import { ChevronDown, Paperclip, Folder, Monitor, ArrowUp, X, FolderOpen, ChevronRight, Home, Check, Plus, Cpu, Trash2, FileText, ListChecks, MessageSquare, Terminal } from 'lucide-react'
import type { BrowseEntry, ModelConfig, WorkMode } from '../types'
import appLogo from '../../icons/GCA.png'

type Environment = 'local' | 'docker' | 'wsl'

const MODE_BUTTONS: { mode: WorkMode; tooltip: string; Icon: typeof FileText }[] = [
  { mode: 'RESEARCH', tooltip: '规格模式', Icon: FileText },
  { mode: 'PLAN', tooltip: '计划模式', Icon: ListChecks },
  { mode: 'FEEDBACK', tooltip: '反馈模式', Icon: MessageSquare },
  { mode: 'WORK', tooltip: '工作模式', Icon: Terminal },
]

export default function EmptyState() {
  const addMessage = useAppStore((s) => s.addMessage)
  const setRunning = useAppStore((s) => s.setRunning)
  const currentModel = useAppStore((s) => s.currentModel)
  const models = useAppStore((s) => s.models)
  const setModel = useAppStore((s) => s.setModel)
  const upsertModel = useAppStore((s) => s.upsertModel)
  const removeModel = useAppStore((s) => s.removeModel)
  const session = useAppStore((s) => s.session)
  const setSession = useAppStore((s) => s.setSession)
  const addTask = useAppStore((s) => s.addTask)
  const setCurrentTask = useAppStore((s) => s.setCurrentTask)
  const wsConnected = useAppStore((s) => s.wsConnected)
  
  const [input, setInput] = useState('')
  const [environment, setEnvironment] = useState<Environment>('local')
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showEnvMenu, setShowEnvMenu] = useState(false)
  const [showWorkspaceBrowser, setShowWorkspaceBrowser] = useState(false)
  const [showAddModelForm, setShowAddModelForm] = useState(false)
  
  // Workspace browser state
  const [browsePath, setBrowsePath] = useState('')
  const [browseEntries, setBrowseEntries] = useState<BrowseEntry[]>([])
  const [browseParent, setBrowseParent] = useState<string | null>(null)
  const [selectedWorkspace, setSelectedWorkspace] = useState(session.workspace || '')
  const [browseLoading, setBrowseLoading] = useState(false)

  // New model form state
  const [newModel, setNewModel] = useState<ModelConfig>({
    name: '', apiBase: '', apiKey: '', isBuiltIn: false, modelName: '',
  })
  
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const modelMenuRef = useRef<HTMLDivElement>(null)

  // Load workspaces from backend on mount
  useEffect(() => {
    loadWorkspaces()
  }, [])

  // Close model menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
        setShowModelMenu(false)
        setShowAddModelForm(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadWorkspaces = async () => {
    try {
      const result = await apiClient.listWorkspaces()
      if (result.workspaces && result.workspaces.length > 0) {
        const last = result.workspaces[0]
        setSelectedWorkspace(last.path)
        setSession({ workspace: last.path })
      }
    } catch (err) {
      console.error('Failed to load workspaces:', err)
    }
  }

  // Browse directories
  const browseTo = async (path: string) => {
    setBrowseLoading(true)
    try {
      const result = await apiClient.browseDirectories(path)
      setBrowsePath(result.path)
      setBrowseEntries(result.entries)
      setBrowseParent(result.parent)
    } catch (err) {
      console.error('Browse failed:', err)
    } finally {
      setBrowseLoading(false)
    }
  }

  const openWorkspaceBrowser = () => {
    setShowWorkspaceBrowser(true)
    browseTo('')
  }

  const handleSelectWorkspace = async (path: string) => {
    try {
      await apiClient.selectWorkspace(path)
      setSelectedWorkspace(path)
      setSession({ workspace: path })
      setShowWorkspaceBrowser(false)
    } catch (err) {
      console.error('Select workspace failed:', err)
      setSelectedWorkspace(path)
      setSession({ workspace: path })
      setShowWorkspaceBrowser(false)
    }
  }

  // Clear workspace (switch to conversation-only mode)
  const handleClearWorkspace = () => {
    setSelectedWorkspace('')
    setSession({ workspace: '' })
  }

  // Add custom model
  const handleAddModel = async () => {
    if (!newModel.name.trim() || !newModel.apiBase.trim()) return
    try {
      const result = await apiClient.createModel({
        name: newModel.name.trim(),
        api_base: newModel.apiBase.trim(),
        api_key: newModel.apiKey.trim(),
        model_name: newModel.modelName?.trim() || newModel.name.trim(),
        is_built_in: false,
      })
      const model: ModelConfig = {
        name: newModel.name.trim(),
        apiBase: newModel.apiBase.trim(),
        apiKey: newModel.apiKey.trim(),
        isBuiltIn: false,
        modelName: newModel.modelName?.trim() || newModel.name.trim(),
        id: result.model.id,
      }
      upsertModel(model)
      setModel(model.name)
    } catch (err) {
      // Fallback: save locally only
      console.error('Failed to save model to DB:', err)
      upsertModel({
        name: newModel.name.trim(),
        apiBase: newModel.apiBase.trim(),
        apiKey: newModel.apiKey.trim(),
        isBuiltIn: false,
        modelName: newModel.modelName?.trim() || newModel.name.trim(),
      })
      setModel(newModel.name.trim())
    }
    setNewModel({ name: '', apiBase: '', apiKey: '', isBuiltIn: false, modelName: '' })
    setShowAddModelForm(false)
    setShowModelMenu(false)
  }

  // Delete custom model
  const handleDeleteModel = async (model: ModelConfig, e: React.MouseEvent) => {
    e.stopPropagation()
    if (model.id) {
      try {
        await apiClient.deleteModel(model.id)
      } catch (err) {
        console.error('Failed to delete model:', err)
      }
    }
    removeModel(model.name)
  }

  const handleSend = async () => {
    console.log('[EmptyState] handleSend called, input:', input.trim())
    if (!input.trim()) return

    const workspace = selectedWorkspace || ''
    console.log('[EmptyState] workspace:', workspace, 'sessionId:', session.sessionId)

    const userMessageId = `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    addMessage({
      id: userMessageId,
      type: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    })
    setRunning(true)
    setInput('')
    setAttachedFiles([])

    const modelConfig = models.find((m) => m.name === currentModel)
    const taskText = input.trim()

    try {
      let sid = session.sessionId
      let isNewSession = false

      if (!sid) {
        console.log('[EmptyState] Creating new session via REST API...')
        const newSession = await apiClient.createSession(workspace, session.mode)
        console.log('[EmptyState] Session created:', newSession)
        sid = newSession.sessionId
        if (!sid) {
          throw new Error('Failed to create session: no session ID returned')
        }
        isNewSession = true

        setSession({
          sessionId: sid,
          workspace,
          mode: session.mode,
        })

        try {
          const taskName = taskText.slice(0, 50) + (taskText.length > 50 ? '...' : '')
          const result = await apiClient.createDBTask({
            name: taskName,
            workspace: workspace,
            mode: session.mode,
            status: 'running',
            session_id: sid,
            last_message: taskText,
          })
          if (result && result.task) {
            const newTask = {
              id: result.task.id,
              name: result.task.name,
              workspace: result.task.workspace,
              mode: result.task.mode as 'WORK' | 'PLAN' | 'FEEDBACK' | 'RESEARCH',
              status: result.task.status as 'pending' | 'running' | 'completed' | 'failed' | 'stopped',
              createdAt: new Date(result.task.created_at).getTime(),
              sessionId: result.task.session_id || undefined,
            }
            addTask(newTask)
            setCurrentTask(newTask.id)
            
            // 保存用户消息到数据库
            try {
              await apiClient.saveMessage(newTask.id, {
                id: userMessageId,
                type: 'user',
                content: taskText,
                timestamp: Date.now(),
              })
            } catch (msgErr) {
              console.error('Failed to save user message:', msgErr)
            }
          }
        } catch (taskErr) {
          console.error('Failed to create task record:', taskErr)
          const localTaskId = sid
          const taskName = taskText.slice(0, 50) + (taskText.length > 50 ? '...' : '')
          addTask({
            id: localTaskId,
            name: taskName,
            workspace: workspace,
            mode: session.mode,
            status: 'running',
            createdAt: Date.now(),
          })
          setCurrentTask(localTaskId)
        }
      }

      if (isNewSession) {
        let waited = 0
        const maxWait = 10000
        const interval = 200
        while (waited < maxWait) {
          const state = useAppStore.getState()
          if (state.wsConnected) {
            console.log('[EmptyState] WebSocket connected after', waited, 'ms')
            break
          }
          await new Promise((resolve) => setTimeout(resolve, interval))
          waited += interval
        }
        if (!useAppStore.getState().wsConnected) {
          console.warn('[EmptyState] WebSocket not connected after timeout, using REST API fallback')
          await apiClient.startTask(sid, taskText, currentModel, modelConfig?.apiBase, modelConfig?.apiKey)
          return
        }
      }

      const sent = wsService.sendStart(taskText, currentModel, modelConfig?.apiBase, modelConfig?.apiKey)
      if (!sent) {
        console.warn('[EmptyState] Failed to send via WebSocket, falling back to REST API')
        await apiClient.startTask(sid, taskText, currentModel, modelConfig?.apiBase, modelConfig?.apiKey)
      }
    } catch (err) {
      addMessage({
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
        type: 'system',
        content: `发送失败: ${err instanceof Error ? err.message : '未知错误'}`,
        level: 'error',
        timestamp: Date.now(),
      })
      setRunning(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setAttachedFiles([...attachedFiles, ...Array.from(e.target.files)])
    }
  }

  const removeFile = (index: number) => {
    setAttachedFiles(attachedFiles.filter((_, i) => i !== index))
  }

  const envOptions = [
    { value: 'local' as Environment, label: '本地' },
    { value: 'docker' as Environment, label: 'Docker' },
    { value: 'wsl' as Environment, label: 'WSL' },
  ]

  const builtInModels = models.filter((m) => m.isBuiltIn)
  const customModels = models.filter((m) => !m.isBuiltIn)

  return (
    <div className="flex flex-col items-center h-full px-8" style={{ paddingTop: '120px' }}>
      {/* Welcome Title */}
      <div className="flex items-center gap-6 mb-12 animate-fade-in">
        <img src={appLogo} alt="GuardCode Agent" className="h-20 w-20 object-contain" />
        <h1
          style={{ 
            color: 'var(--text-primary)',
            letterSpacing: '-0.02em',
            fontSize: '36px',
            fontWeight: 600,
          }}
        >
          GuardCode Agent
        </h1>
      </div>

      {/* Main Prompt Composer */}
      <div className="w-full animate-slide-up" style={{ maxWidth: '1200px' }}>
        {/* Prompt Input Box */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #d7d7d7',
            borderRadius: '22px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            minHeight: '195px',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Input Area */}
          <div style={{ flex: 1, padding: '24px', paddingBottom: '12px' }}>
            <textarea
              ref={textareaRef}
              className="w-full bg-transparent outline-none resize-none"
              style={{
                color: 'var(--text-primary)',
                fontSize: '16px',
                lineHeight: '1.5',
                minHeight: '80px',
                border: 'none',
              }}
              placeholder="输入你的编程任务，例如：分析项目结构、修改代码、运行测试……"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            {/* Attached Files */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {attachedFiles.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm"
                    style={{
                      backgroundColor: 'var(--bg-secondary)',
                      border: '1px solid var(--border-light)',
                    }}
                  >
                    <span>📄 {file.name}</span>
                    <button
                      className="hover:opacity-70"
                      onClick={() => removeFile(index)}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Toolbar */}
          <div className="flex items-center justify-between px-6 pb-5">
            {/* Left Tools */}
            <div className="flex items-center gap-3">
              {/* Mode Switcher */}
              <div className="flex items-center gap-1">
                {MODE_BUTTONS.map(({ mode: m, tooltip, Icon }) => (
                  <button
                    key={m}
                    onClick={() => useAppStore.getState().setSession({ mode: m })}
                    title={tooltip}
                    className="flex items-center justify-center transition-colors"
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '8px',
                      backgroundColor: session.mode === m ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                      color: session.mode === m ? '#fff' : 'var(--text-secondary)',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    <Icon size={16} />
                  </button>
                ))}
              </div>

              {/* File Picker */}
              <button
                className="flex items-center justify-center transition-all"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  border: '1px solid #eeeeee',
                  backgroundColor: '#ffffff',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f9f9f9'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff'
                }}
                onClick={() => fileInputRef.current?.click()}
                title="添加文件"
              >
                <Paperclip size={20} strokeWidth={1.5} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileSelect}
              />

              {/* Divider */}
              <div
                style={{
                  width: '1px',
                  height: '20px',
                  backgroundColor: '#e5e5e5',
                  margin: '0 12px',
                }}
              />
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              {/* Model Selector with Custom Model Config */}
              <div className="relative" ref={modelMenuRef}>
                <button
                  className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors"
                  style={{
                    color: '#222222',
                    backgroundColor: 'transparent',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#f5f5f5'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent'
                  }}
                  onClick={() => setShowModelMenu(!showModelMenu)}
                >
                  <Cpu size={14} style={{ color: '#7c6cff' }} />
                  <span>{currentModel || '选择模型'}</span>
                  <ChevronDown size={14} />
                </button>

                {showModelMenu && (
                  <div
                    className="absolute z-50 mt-2 py-2 rounded-lg animate-fade-in"
                    style={{
                      backgroundColor: '#ffffff',
                      border: '1px solid var(--border-light)',
                      boxShadow: 'var(--shadow-lg)',
                      minWidth: '240px',
                      right: 0,
                    }}
                  >
                    {/* Built-in Models */}
                    <div className="px-3 py-1 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                      内置模型
                    </div>
                    {builtInModels.map((model) => (
                      <button
                        key={model.name}
                        className="w-full text-left px-3 py-2 text-sm transition-colors"
                        style={{
                          color: currentModel === model.name ? '#7c6cff' : '#222222',
                          backgroundColor: currentModel === model.name ? '#f0ebff' : 'transparent',
                        }}
                        onClick={() => {
                          setModel(model.name)
                          setShowModelMenu(false)
                        }}
                      >
                        {currentModel === model.name && '✓ '}{model.name}
                      </button>
                    ))}

                    {/* Custom Models */}
                    {customModels.length > 0 && (
                      <div className="border-t mt-1 pt-1" style={{ borderColor: '#eee' }}>
                        <div className="px-3 py-1 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                          自定义模型
                        </div>
                        {customModels.map((model) => (
                          <div
                            key={model.name}
                            className="flex items-center w-full px-3 py-2 text-sm transition-colors group"
                            style={{
                              color: currentModel === model.name ? '#7c6cff' : '#222222',
                              backgroundColor: currentModel === model.name ? '#f0ebff' : 'transparent',
                            }}
                          >
                            <button
                              className="flex-1 text-left truncate"
                              onClick={() => {
                                setModel(model.name)
                                setShowModelMenu(false)
                              }}
                            >
                              {currentModel === model.name && '✓ '}{model.name}
                            </button>
                            <button
                              className="icon-btn shrink-0 opacity-0 group-hover:opacity-100"
                              style={{ width: '20px', height: '20px' }}
                              onClick={(e) => handleDeleteModel(model, e)}
                              title="删除模型"
                            >
                              <Trash2 size={12} style={{ color: '#e74c3c' }} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Add Custom Model Section */}
                    <div className="border-t mt-1 pt-1" style={{ borderColor: '#eee' }}>
                      {showAddModelForm ? (
                        <div className="p-3 space-y-2 animate-slide-down">
                          <div>
                            <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>
                              模型名称
                            </label>
                            <input
                              type="text"
                              className="input-field text-sm"
                              placeholder="例如：My GPT-4"
                              value={newModel.name}
                              onChange={(e) => setNewModel({ ...newModel, name: e.target.value })}
                              autoFocus
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>
                              模型标识 (model_name)
                            </label>
                            <input
                              type="text"
                              className="input-field text-sm"
                              placeholder="例如：gpt-4-turbo"
                              value={newModel.modelName}
                              onChange={(e) => setNewModel({ ...newModel, modelName: e.target.value })}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>
                              API URL
                            </label>
                            <input
                              type="text"
                              className="input-field text-sm"
                              placeholder="https://api.openai.com/v1"
                              value={newModel.apiBase}
                              onChange={(e) => setNewModel({ ...newModel, apiBase: e.target.value })}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>
                              API Token
                            </label>
                            <input
                              type="password"
                              className="input-field text-sm"
                              placeholder="sk-..."
                              value={newModel.apiKey}
                              onChange={(e) => setNewModel({ ...newModel, apiKey: e.target.value })}
                            />
                          </div>
                          <div className="flex gap-2">
                            <button
                              className="btn btn-primary flex-1 text-xs"
                              onClick={handleAddModel}
                              disabled={!newModel.name.trim() || !newModel.apiBase.trim()}
                              style={{ opacity: newModel.name.trim() && newModel.apiBase.trim() ? 1 : 0.5 }}
                            >
                              保存
                            </button>
                            <button
                              className="btn btn-secondary text-xs"
                              onClick={() => setShowAddModelForm(false)}
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          className="flex items-center gap-2 w-full px-3 py-2 text-sm transition-colors"
                          style={{ color: '#666' }}
                          onClick={() => setShowAddModelForm(true)}
                        >
                          <Plus size={14} style={{ color: '#7c6cff' }} />
                          添加自定义模型
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Send Button */}
              <button
                className="flex items-center justify-center transition-all"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: input.trim() ? '#7c6cff' : '#ddd9ff',
                  color: input.trim() ? '#ffffff' : '#aaaaaa',
                  cursor: input.trim() ? 'pointer' : 'not-allowed',
                  border: 'none',
                }}
                onMouseEnter={(e) => {
                  if (input.trim()) {
                    e.currentTarget.style.backgroundColor = '#6b5dd9'
                  }
                }}
                onMouseLeave={(e) => {
                  if (input.trim()) {
                    e.currentTarget.style.backgroundColor = '#7c6cff'
                  }
                }}
                onClick={handleSend}
                disabled={!input.trim()}
              >
                <ArrowUp size={20} strokeWidth={2} />
              </button>
            </div>
          </div>
        </div>

        {/* Context Bar */}
        <div
          className="flex items-center gap-8 mt-3 px-7 rounded-2xl"
          style={{
            height: '64px',
            backgroundColor: '#f5f5f5',
          }}
        >
          {/* Environment Selector */}
          <div className="relative">
            <button
              className="flex items-center gap-2 text-sm transition-colors"
              style={{ color: 'var(--text-primary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--accent-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onClick={() => setShowEnvMenu(!showEnvMenu)}
            >
              <Monitor size={16} strokeWidth={1.5} />
              <span>{envOptions.find(e => e.value === environment)?.label}</span>
              <ChevronDown size={14} />
            </button>

            {showEnvMenu && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowEnvMenu(false)}
                />
                <div
                  className="absolute z-50 py-2 rounded-lg animate-fade-in"
                  style={{
                    backgroundColor: '#ffffff',
                    border: '1px solid var(--border-light)',
                    boxShadow: 'var(--shadow-lg)',
                    minWidth: '140px',
                    bottom: '100%',
                    marginBottom: '8px',
                  }}
                >
                  <div className="px-3 py-1 text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
                    执行环境
                  </div>
                  {envOptions.map((option) => (
                    <button
                      key={option.value}
                      className="w-full text-left px-3 py-2 text-sm transition-colors"
                      style={{
                        color: environment === option.value ? 'var(--accent-primary)' : 'var(--text-primary)',
                        backgroundColor: environment === option.value ? 'var(--accent-lighter)' : 'transparent',
                      }}
                      onMouseEnter={(e) => {
                        if (environment !== option.value) {
                          e.currentTarget.style.backgroundColor = 'var(--bg-hover)'
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (environment !== option.value) {
                          e.currentTarget.style.backgroundColor = 'transparent'
                        }
                      }}
                      onClick={() => {
                        setEnvironment(option.value)
                        setShowEnvMenu(false)
                      }}
                    >
                      {environment === option.value && '✓ '}{option.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Workspace Selector */}
          <div className="relative flex items-center gap-2">
            <button
              className="flex items-center gap-2 text-sm transition-colors"
              style={{ color: 'var(--text-primary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--accent-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onClick={openWorkspaceBrowser}
            >
              <Folder size={16} strokeWidth={1.5} />
              <span className="truncate max-w-[200px]">
                {selectedWorkspace ? selectedWorkspace.split(/[\\/]/).pop() || selectedWorkspace : '选择工作区'}
              </span>
              <ChevronDown size={14} />
            </button>
            {/* Clear workspace button — switch to conversation-only mode */}
            {selectedWorkspace && (
              <button
                className="icon-btn"
                style={{ width: '20px', height: '20px' }}
                onClick={handleClearWorkspace}
                title="移除工作区（仅对话模式）"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Mode indicator */}
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {selectedWorkspace ? '工作区模式' : '纯对话模式'}
          </div>
        </div>
      </div>

      {/* ===== Workspace Browser Modal ===== */}
      {showWorkspaceBrowser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowWorkspaceBrowser(false)
          }}
        >
          <div
            className="w-full max-w-2xl rounded-xl shadow-2xl animate-slide-up flex flex-col"
            style={{
              backgroundColor: 'var(--bg-primary)',
              border: '1px solid var(--border-light)',
              maxHeight: '80vh',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4 border-b shrink-0"
              style={{ borderColor: 'var(--border-light)' }}
            >
              <div className="flex items-center gap-2">
                <FolderOpen size={20} style={{ color: 'var(--accent-primary)' }} />
                <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                  选择工作区
                </h3>
              </div>
              <button
                className="icon-btn"
                onClick={() => setShowWorkspaceBrowser(false)}
              >
                <X size={18} />
              </button>
            </div>

            {/* Current Path */}
            <div
              className="flex items-center gap-2 px-5 py-3 border-b shrink-0"
              style={{ borderColor: 'var(--border-light)', backgroundColor: 'var(--bg-secondary)' }}
            >
              <button
                className="icon-btn"
                style={{ width: '24px', height: '24px' }}
                onClick={() => browseTo('')}
                title="回到根目录"
              >
                <Home size={14} />
              </button>
              {browseParent && (
                <button
                  className="icon-btn"
                  style={{ width: '24px', height: '24px' }}
                  onClick={() => browseTo(browseParent)}
                  title="上一级"
                >
                  <ChevronRight size={14} style={{ transform: 'rotate(180deg)' }} />
                </button>
              )}
              <span
                className="text-sm truncate flex-1"
                style={{ color: 'var(--text-secondary)' }}
              >
                {browsePath || '根目录'}
              </span>
              {browseLoading && (
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  加载中...
                </span>
              )}
            </div>

            {/* Directory List */}
            <div className="flex-1 overflow-y-auto p-2">
              {browseEntries.length === 0 && !browseLoading ? (
                <div
                  className="text-center py-8 text-sm"
                  style={{ color: 'var(--text-muted)' }}
                >
                  没有子目录
                </div>
              ) : (
                browseEntries.map((entry) => (
                  <button
                    key={entry.path}
                    className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm transition-colors text-left"
                    style={{
                      color: 'var(--text-primary)',
                      backgroundColor: selectedWorkspace === entry.path ? 'var(--accent-lighter)' : 'transparent',
                    }}
                    onMouseEnter={(e) => {
                      if (selectedWorkspace !== entry.path) {
                        e.currentTarget.style.backgroundColor = 'var(--bg-hover)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedWorkspace !== entry.path) {
                        e.currentTarget.style.backgroundColor = 'transparent'
                      }
                    }}
                    onClick={() => browseTo(entry.path)}
                    onDoubleClick={() => handleSelectWorkspace(entry.path)}
                  >
                    <Folder size={16} style={{ color: 'var(--accent-primary)' }} />
                    <span className="truncate flex-1">{entry.name}</span>
                    <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
                  </button>
                ))
              )}
            </div>

            {/* Footer */}
            <div
              className="flex items-center justify-between gap-2 px-5 py-4 border-t shrink-0"
              style={{ borderColor: 'var(--border-light)' }}
            >
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                双击目录选择为工作区，单击进入目录
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="btn btn-secondary text-sm"
                  onClick={() => setShowWorkspaceBrowser(false)}
                >
                  取消
                </button>
                <button
                  className="btn btn-primary text-sm flex items-center gap-1.5"
                  onClick={() => handleSelectWorkspace(browsePath)}
                  disabled={!browsePath}
                  style={{ opacity: browsePath ? 1 : 0.5 }}
                >
                  <Check size={14} />
                  选择此目录
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
