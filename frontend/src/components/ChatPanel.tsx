import { useState, useRef, useEffect } from 'react'
import { useAppStore, genId } from '../store/appStore'
import { wsService } from '../services/wsService'
import { apiClient } from '../api/client'
import ModelSelector from './ModelSelector'
import {
  Paperclip,
  Send,
  Square,
  User,
  Bot,
  Info,
  AlertTriangle,
  AlertCircle,
  Sparkles,
  Clock,
  ChevronDown,
  ChevronRight,
  Copy,
  RefreshCw,
  Check,
  FileText,
  ListChecks,
  MessageSquare,
  Terminal,
} from 'lucide-react'
import type { ChatMessage, WorkMode } from '../types'
import appLogo from '../../icons/GCA.png'

// ===== Simple Markdown Renderer =====

function renderMarkdown(content: string): string {
  if (!content) return ''
  let html = content

  // Code blocks (```) - must be processed first
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre><code class="language-${lang}">${escapeHtml(code.trim())}</code></pre>`
  })

  // Inline code - but not within code blocks
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')

  // Bold and italic
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  )

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')

  // Ordered lists - use replacer function to avoid $2 interpretation
  html = html.replace(/^(\d+)\. (.+)$/gm, (match, num, text) => `<li>${text}</li>`)
  
  // Unordered lists
  html = html.replace(/^[-*]\s+(.+)$/gm, (match, text) => `<li>${text}</li>`)

  // Paragraphs (split by double newline)
  const paragraphs = html.split(/\n\n+/)
  html = paragraphs
    .map((p) => {
      const trimmed = p.trim()
      if (!trimmed) return ''
      if (/^<(h[1-3]|pre|blockquote|ul|ol|li)/.test(trimmed)) return trimmed
      return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`
    })
    .join('')

  // Wrap consecutive <li> in <ul>
  html = html.replace(/(<li>.*?<\/li>)(?!\s*<li)/gs, '<ul>$1</ul>')

  return html
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function formatDuration(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${hours}h${String(minutes).padStart(2, '0')}m${String(seconds).padStart(2, '0')}s`
}

function WorkStatus({ startedAt }: { startedAt: number | null }) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="flex items-center gap-2 mb-2">
      <img src={appLogo} alt="GuardCode Agent" className="h-6 w-6 object-contain" />
      <div>
        <div className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>GuardCode Agent Work</div>
        <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>任务耗时 {startedAt ? formatDuration(now - startedAt) : '0h00m00s'}</div>
      </div>
    </div>
  )
}

function AssistantMessage({ message, isLastMessage, isRunning, taskStartedAt, showHeader, isLastInRound, roundContent, onRetry }: { message: ChatMessage; isLastMessage: boolean; isRunning: boolean; taskStartedAt: number | null; showHeader: boolean; isLastInRound: boolean; roundContent: string; onRetry?: () => void }) {
  const [showThinking, setShowThinking] = useState(true)
  const [copied, setCopied] = useState(false)
  const msg = message as any

  const hasContent = msg.content && msg.content.trim().length > 0
  // 思考中状态：最后一条消息且任务进行中且无内容（模型刚开始，还未输出）
  const isThinking = isLastMessage && isRunning && !hasContent
  // 思考过程状态：最后一条消息且任务进行中且有内容（模型正在流式输出）
  const isThinkingProcess = isLastMessage && isRunning && hasContent

  const handleCopy = async () => {
    const textToCopy = roundContent || msg.content || ''
    if (!textToCopy) return
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  return (
    <div className="flex justify-start mb-6 animate-fade-in">
      <div className="w-full max-w-[85%]">
        {/* Assistant Header with Logo - only show when showHeader is true */}
        {showHeader && (
          <div className="flex items-center gap-2 mb-2">
            <img src={appLogo} alt="GCA" className="w-8 h-8 rounded-full shrink-0 object-contain" />
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                GuardCode Agent
              </span>
              {msg.model && (
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: 'var(--accent-lighter)',
                    color: 'var(--accent-primary)',
                  }}
                >
                  {msg.model}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Thinking Section - 思考中动画（无内容时） */}
        {isThinking && showHeader && (
          <div className="ml-10 mb-3">
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <Sparkles size={14} style={{ color: 'var(--accent-primary)' }} />
              <span>思考中</span>
              <span className="flex gap-0.5">
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '0ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '150ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '300ms' }} />
              </span>
            </div>
          </div>
        )}

        {/* Thinking Process - 思考过程（有内容且任务进行中，可折叠，默认展开） */}
        {isThinkingProcess && showHeader && (
          <div className="ml-10 mb-3">
            <button
              className="flex items-center gap-2 text-sm transition-colors mb-2"
              style={{ color: 'var(--text-secondary)' }}
              onClick={() => setShowThinking(!showThinking)}
            >
              <Sparkles size={14} style={{ color: 'var(--accent-primary)' }} />
              <span>思考过程</span>
              <span className="flex gap-0.5">
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '0ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '150ms' }} />
                <span className="w-1 h-1 rounded-full animate-bounce" style={{ backgroundColor: 'var(--accent-primary)', animationDelay: '300ms' }} />
              </span>
              {showThinking ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {showThinking && (
              <div
                className="p-3 rounded-lg text-sm animate-slide-down"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border-light)',
                  color: 'var(--text-secondary)',
                }}
              >
                <div
                  className="markdown-body leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                />
                <span
                  className="inline-block w-2 h-4 ml-0.5 align-middle"
                  style={{ backgroundColor: 'var(--accent-primary)', verticalAlign: 'middle', animation: 'pulse 1s infinite' }}
                />
              </div>
            )}
          </div>
        )}

        {/* Content Section - 最终结果（任务结束后显示） */}
        {hasContent && !isThinkingProcess && (
          <div className={showHeader ? 'ml-10' : 'ml-10'}>
            <div
              className="rounded-xl px-4 py-3"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                border: '1px solid var(--border-light)',
              }}
            >
              <div
                className="markdown-body text-sm leading-relaxed"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
              />
            </div>

            {/* Action Buttons - only show on the last message of a round */}
            {!isRunning && hasContent && isLastInRound && (
              <div className="flex items-center gap-1 mt-2">
                <button
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-gray-100"
                  style={{ color: 'var(--text-muted)' }}
                  onClick={handleCopy}
                  title="复制内容"
                >
                  {copied ? <Check size={12} style={{ color: 'var(--success)' }} /> : <Copy size={12} />}
                  <span>{copied ? '已复制' : '复制'}</span>
                </button>
                {onRetry && (
                  <button
                    className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:bg-gray-100"
                    style={{ color: 'var(--text-muted)' }}
                    onClick={onRetry}
                    title="重新生成"
                  >
                    <RefreshCw size={12} />
                    <span>重试</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Task Timer */}
        {isRunning && taskStartedAt && showHeader && (
          <div className="ml-10 mt-2 flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-muted)' }}>
            <Clock size={12} />
            <span>任务执行中 · {formatDuration(Date.now() - taskStartedAt)}</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ===== Tool Call Message (Expand/Collapse) =====

function getToolCallSummary(tool: string, args: Record<string, unknown>): string {
  if (!args || typeof args !== 'object') return ''
  switch (tool) {
    case 'run_command':
    case 'execute_command':
      return (args.command as string) || ''
    case 'read_file':
    case 'write_file':
    case 'create_file':
    case 'edit_file':
    case 'delete_file':
      return (args.path as string) || (args.file_path as string) || ''
    case 'list_directory':
      return (args.path as string) || (args.directory as string) || ''
    case 'search_files':
      return `${args.pattern || args.query || ''} ${args.path || ''}`.trim()
    default:
      return Object.entries(args)
        .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join(' ')
        .slice(0, 80)
  }
}

function getToolResultSummary(result: unknown, error?: string): string {
  if (error) return error.slice(0, 80)
  if (typeof result === 'string') return result.slice(0, 80)
  if (result && typeof result === 'object') {
    const obj = result as Record<string, unknown>
    if (obj.content) return String(obj.content).slice(0, 80)
    if (obj.path) return String(obj.path)
    if (obj.output) return String(obj.output).slice(0, 80)
    return JSON.stringify(result).slice(0, 80)
  }
  return String(result || '').slice(0, 80)
}

function ToolCallMessage({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(false)

  if (message.type === 'tool_call') {
    const { tool, args, status, riskLevel } = message
    const summary = getToolCallSummary(tool, args)
    const riskColor =
      riskLevel === 'dangerous'
        ? 'var(--error)'
        : riskLevel === 'moderate'
        ? 'var(--warning)'
        : 'var(--success)'
    const statusColor =
      status === 'success'
        ? 'var(--success)'
        : status === 'failed'
        ? 'var(--error)'
        : 'var(--warning)'

    return (
      <div className="ml-10 mb-3">
        <div
          className="rounded-lg overflow-hidden"
          style={{
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-light)',
          }}
        >
          <button
            className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:bg-gray-50"
            style={{ backgroundColor: 'var(--bg-secondary)' }}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
            ) : (
              <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
            )}
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {tool}: {summary || '无参数'}
            </span>
            {riskLevel && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded uppercase"
                style={{ backgroundColor: riskColor, color: '#fff' }}
              >
                {riskLevel}
              </span>
            )}
            {status && (
              <span className="text-xs ml-auto" style={{ color: statusColor }}>
                {status === 'running' ? '执行中' : status === 'success' ? '成功' : status === 'failed' ? '失败' : '等待中'}
              </span>
            )}
          </button>
          {expanded && (
            <pre
              className="text-xs p-3 overflow-x-auto animate-slide-down"
              style={{
                backgroundColor: 'var(--bg-secondary)',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-mono, monospace)',
                borderTop: '1px solid var(--border-light)',
              }}
            >
              {JSON.stringify(args, null, 2)}
            </pre>
          )}
        </div>
      </div>
    )
  }

  if (message.type !== 'tool_result') return null
  const { tool, result, success, error } = message
  const resultSummary = getToolResultSummary(result, error)

  return (
    <div className="ml-10 mb-3">
      <div
        className="rounded-lg overflow-hidden"
        style={{
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-light)',
        }}
      >
        <button
          className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:bg-gray-50"
          style={{ backgroundColor: 'var(--bg-secondary)' }}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
          ) : (
            <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
          )}
          <span
            className="text-xs font-medium px-1.5 py-0.5 rounded"
            style={{
              backgroundColor: success ? 'var(--success)' : 'var(--error)',
              color: '#fff',
            }}
          >
            {success ? '成功' : '失败'}
          </span>
          <span className="text-sm flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>
            {tool}: {resultSummary || '无结果'}
          </span>
        </button>
        {expanded && (
          <pre
            className="text-xs p-3 overflow-x-auto max-h-60 animate-slide-down"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              color: success ? 'var(--text-secondary)' : 'var(--error)',
              fontFamily: 'var(--font-mono, monospace)',
              borderTop: '1px solid var(--border-light)',
            }}
          >
            {error || (typeof result === 'string' ? result : JSON.stringify(result, null, 2))}
          </pre>
        )}
      </div>
    </div>
  )
}

// ===== Message Bubble =====

function MessageBubble({ message, isLastMessage, isRunning, taskStartedAt, showHeader, isLastInRound, roundContent, onRetry }: { message: ChatMessage; isLastMessage: boolean; isRunning: boolean; taskStartedAt: number | null; showHeader: boolean; isLastInRound: boolean; roundContent: string; onRetry?: () => void }) {
  switch (message.type) {
    case 'user':
      return (
        <div className="flex justify-end mb-6 animate-fade-in">
          <div className="flex items-start gap-2 max-w-[80%]">
            <div
              className="rounded-xl px-4 py-3"
              style={{
                backgroundColor: 'var(--accent-primary)',
                color: '#fff',
              }}
            >
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
            </div>
            <div
              className="flex items-center justify-center w-8 h-8 rounded-full shrink-0"
              style={{ backgroundColor: 'var(--bg-tertiary)' }}
            >
              <User size={16} style={{ color: 'var(--text-secondary)' }} />
            </div>
          </div>
        </div>
      )

    case 'assistant':
      return <AssistantMessage message={message} isLastMessage={isLastMessage} isRunning={isRunning} taskStartedAt={taskStartedAt} showHeader={showHeader} isLastInRound={isLastInRound} roundContent={roundContent} onRetry={onRetry} />

    case 'tool_call':
    case 'tool_result':
      return <ToolCallMessage message={message} />

    case 'system':
      return (
        <div className="flex justify-center mb-4 animate-fade-in">
          <div
            className="flex items-center gap-2 px-4 py-2 rounded-full text-sm"
            style={{
              backgroundColor: 'var(--bg-tertiary)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            {message.level === 'error' ? (
              <AlertCircle size={14} style={{ color: 'var(--error)' }} />
            ) : message.level === 'warning' ? (
              <AlertTriangle size={14} style={{ color: 'var(--warning)' }} />
            ) : (
              <Info size={14} style={{ color: 'var(--text-muted)' }} />
            )}
            <span>{message.content}</span>
          </div>
        </div>
      )

    default:
      return null
  }
}

// ===== Mode Switcher Config =====

const MODE_BUTTONS: { mode: WorkMode; tooltip: string; Icon: typeof FileText }[] = [
  { mode: 'RESEARCH', tooltip: '规格模式', Icon: FileText },
  { mode: 'PLAN', tooltip: '计划模式', Icon: ListChecks },
  { mode: 'FEEDBACK', tooltip: '反馈模式', Icon: MessageSquare },
  { mode: 'WORK', tooltip: '工作模式', Icon: Terminal },
]

// ===== Chat Panel =====

export default function ChatPanel() {
  const messages = useAppStore((s) => s.chat.messages)
  const addMessage = useAppStore((s) => s.addMessage)
  const session = useAppStore((s) => s.session)
  const setRunning = useAppStore((s) => s.setRunning)
  const currentModel = useAppStore((s) => s.currentModel)
  const models = useAppStore((s) => s.models)
  const taskStartedAt = useAppStore((s) => s.taskStartedAt)
  const wsConnected = useAppStore((s) => s.wsConnected)
  const currentTaskId = useAppStore((s) => s.currentTaskId)

  const [input, setInput] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])

  const handleSend = async () => {
    if (!input.trim() || session.isRunning) return

    const userMessage = {
      id: genId(),
      type: 'user' as const,
      content: input.trim(),
      timestamp: Date.now(),
    }
    addMessage(userMessage)
    
    // 保存用户消息到数据库
    if (currentTaskId) {
      try {
        await apiClient.saveMessage(currentTaskId, {
          id: userMessage.id,
          type: userMessage.type,
          content: userMessage.content,
          timestamp: userMessage.timestamp,
        })
      } catch (err) {
        console.error('Failed to save user message:', err)
      }
    }
    
    setInput('')
    setRunning(true)
    const taskId = useAppStore.getState().currentTaskId
    if (taskId) {
      useAppStore.getState().updateTaskStatus(taskId, 'running')
      apiClient.updateTaskStatus(taskId, 'running').catch(() => {})
    }

    // Send via WebSocket
    const modelConfig = models.find((m) => m.name === currentModel)
    const sent = wsService.sendStart(input.trim(), currentModel, modelConfig?.apiBase, modelConfig?.apiKey)

    if (!sent) {
      // Fallback: try REST API
      if (session.sessionId) {
        try {
          await apiClient.startTask(session.sessionId, input.trim(), currentModel, modelConfig?.apiBase, modelConfig?.apiKey)
        } catch (err) {
          addMessage({
            id: genId(),
            type: 'system',
            content: `发送失败: ${err instanceof Error ? err.message : '未知错误'}`,
            level: 'error',
            timestamp: Date.now(),
          })
          setRunning(false)
        }
      } else {
        addMessage({
          id: genId(),
          type: 'system',
          content: '未连接到服务器，请先创建会话',
          level: 'error',
          timestamp: Date.now(),
        })
        setRunning(false)
      }
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStop = () => {
    wsService.sendStop()
    setRunning(false)
    const taskId = useAppStore.getState().currentTaskId
    if (taskId) {
      useAppStore.getState().updateTaskStatus(taskId, 'stopped')
      apiClient.updateTaskStatus(taskId, 'stopped').catch(() => {})
    }
  }

  const handleRetry = () => {
    const userMessages = messages.filter((m) => m.type === 'user')
    if (userMessages.length === 0) return
    const lastUserMessage = userMessages[userMessages.length - 1]
    setRunning(true)
    const taskId = useAppStore.getState().currentTaskId
    if (taskId) {
      useAppStore.getState().updateTaskStatus(taskId, 'running')
      apiClient.updateTaskStatus(taskId, 'running').catch(() => {})
    }
    const modelConfig = models.find((m) => m.name === currentModel)
    const sent = wsService.sendStart(lastUserMessage.content, currentModel, modelConfig?.apiBase, modelConfig?.apiKey)
    if (!sent && session.sessionId) {
      apiClient.startTask(session.sessionId, lastUserMessage.content, currentModel, modelConfig?.apiBase, modelConfig?.apiKey).catch(() => {
        setRunning(false)
      })
    }
  }

  // Calculate whether each message should show the assistant header
  // Show header only for the first assistant message in a round (after user/system message)
  const getShowHeader = (index: number): boolean => {
    const msg = messages[index]
    if (msg.type !== 'assistant') return true
    if (index === 0) return true
    const prevMsg = messages[index - 1]
    // If previous message is assistant/tool_call/tool_result, same round - don't show header
    if (prevMsg.type === 'assistant' || prevMsg.type === 'tool_call' || prevMsg.type === 'tool_result') {
      return false
    }
    return true
  }

  // Check if this is the last message in a round (next message is user/system, or no next message)
  const getIsLastInRound = (index: number): boolean => {
    const msg = messages[index]
    if (msg.type !== 'assistant') return false
    if (index === messages.length - 1) return true
    const nextMsg = messages[index + 1]
    // If next message is user/system, this is the last in the round
    if (nextMsg.type === 'user' || nextMsg.type === 'system') {
      return true
    }
    return false
  }

  // Gather all assistant content in the current round (starting from this message going backwards)
  const getRoundContent = (index: number): string => {
    const contents: string[] = []
    // Go backwards from index to find all assistant messages in this round
    for (let i = index; i >= 0; i--) {
      const m = messages[i]
      if (m.type === 'user' || m.type === 'system') break
      if (m.type === 'assistant' && m.content) {
        contents.unshift(m.content)
      }
    }
    return contents.join('\n\n')
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      try {
        if (session.workspace) {
          const result = await apiClient.uploadFile(file, session.workspace)
          addMessage({
            id: genId(),
            type: 'system',
            content: `文件已上传: ${result.path || file.name}`,
            level: 'info',
            timestamp: Date.now(),
          })
        }
      } catch (err) {
        addMessage({
          id: genId(),
          type: 'system',
          content: `上传失败: ${err instanceof Error ? err.message : '未知错误'}`,
          level: 'error',
          timestamp: Date.now(),
        })
      }
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = e.dataTransfer.files
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      try {
        if (session.workspace) {
          await apiClient.uploadFile(file, session.workspace)
        }
      } catch (err) {
        console.error('Upload failed:', err)
      }
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* ===== Message List ===== */}
      <div
        className="flex-1 overflow-y-auto px-4 py-4"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          border: isDragging ? '2px dashed var(--accent-primary)' : 'none',
        }}
      >
        <div className="max-w-4xl mx-auto">
          {messages.map((msg, index) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              isLastMessage={index === messages.length - 1}
              isRunning={session.isRunning}
              taskStartedAt={taskStartedAt}
              showHeader={getShowHeader(index)}
              isLastInRound={getIsLastInRound(index)}
              roundContent={getRoundContent(index)}
              onRetry={msg.type === 'assistant' && getIsLastInRound(index) && !session.isRunning ? handleRetry : undefined}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* ===== Input Area ===== */}
      <div
        className="border-t px-6 py-4"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="max-w-4xl mx-auto">
          <div
            className="flex items-end gap-3 rounded-2xl px-4 py-3"
            style={{
              backgroundColor: 'var(--bg-primary)',
              border: '2px solid var(--border)',
            }}
          >
            {/* Textarea */}
            <textarea
              ref={textareaRef}
              className="flex-1 bg-transparent outline-none resize-none text-sm py-1"
              style={{
                color: 'var(--text-primary)',
                minHeight: '24px',
                maxHeight: '200px',
              }}
              placeholder="输入编程任务开始对话..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />

            {/* Action Buttons */}
            <div className="flex items-center gap-2 shrink-0">
              {/* Mode Switcher - 仅在无消息（新对话）时显示，对话开始后隐藏 */}
              {messages.length === 0 && (
                <div className="flex items-center gap-1">
                  {MODE_BUTTONS.map(({ mode: m, tooltip, Icon }) => (
                    <button
                      key={m}
                      onClick={() => useAppStore.getState().setSession({ mode: m })}
                      title={tooltip}
                      className="flex items-center justify-center transition-colors"
                      style={{
                        width: '32px',
                        height: '32px',
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
              )}

              {/* Current Mode Indicator - 对话开始后显示当前模式（不可切换） */}
              {messages.length > 0 && (() => {
                const currentModeBtn = MODE_BUTTONS.find(({ mode: m }) => m === session.mode)
                if (!currentModeBtn) return null
                const { Icon, tooltip } = currentModeBtn
                return (
                  <div
                    className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs"
                    title={tooltip}
                    style={{
                      backgroundColor: 'var(--bg-tertiary)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    <Icon size={14} />
                    <span>{tooltip}</span>
                  </div>
                )
              })()}

              {/* File Upload Button */}
              <button
                className="icon-btn"
                onClick={() => fileInputRef.current?.click()}
                title="上传文件"
              >
                <Paperclip size={18} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={handleFileUpload}
              />

              {/* Model Selector */}
              <ModelSelector />

              {/* Send / Stop Button */}
              {session.isRunning ? (
                <button
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  style={{
                    backgroundColor: 'var(--danger)',
                    color: '#fff',
                  }}
                  onClick={handleStop}
                >
                  <Square size={14} />
                  <span>停止</span>
                </button>
              ) : (
                <button
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all"
                  style={{
                    backgroundColor: input.trim() ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                    color: input.trim() ? '#fff' : 'var(--text-muted)',
                    opacity: input.trim() ? 1 : 0.6,
                    cursor: input.trim() ? 'pointer' : 'not-allowed',
                  }}
                  onClick={handleSend}
                  disabled={!input.trim()}
                >
                  <Send size={14} />
                  <span>发送</span>
                </button>
              )}
            </div>
          </div>

          {/* Connection Status */}
          <div
            className="flex items-center justify-between mt-2 px-2 text-xs"
            style={{ color: 'var(--text-muted)' }}
          >
            <div className="flex items-center gap-1.5">
              {session.isRunning ? (
                <>
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{
                      backgroundColor: wsConnected ? 'var(--success)' : 'var(--text-muted)',
                    }}
                  />
                  <span>{wsConnected ? '已连接' : '未连接'}</span>
                </>
              ) : (
                <span>任务已完成</span>
              )}
            </div>
            <span>Enter 发送 · Shift+Enter 换行</span>
          </div>
        </div>
      </div>
    </div>
  )
}
