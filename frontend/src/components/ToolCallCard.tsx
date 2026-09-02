import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import {
  Wrench,
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  FileText,
  GitCompare,
  Terminal,
  FilePlus,
  FileEdit,
  FolderSearch,
  Search,
  Trash,
  Download,
  Upload,
} from 'lucide-react'
import type { ChatMessage, ToolCallMessage, ToolResultMessage } from '../types'

// ===== Tool Icon Mapping =====

const TOOL_ICONS: Record<string, typeof Wrench> = {
  read_file: FileText,
  write_file: FileEdit,
  create_file: FilePlus,
  edit_file: FileEdit,
  delete_file: Trash,
  list_directory: FolderSearch,
  search_files: Search,
  run_command: Terminal,
  execute_command: Terminal,
  download_file: Download,
  upload_file: Upload,
}

function getToolIcon(tool: string) {
  return TOOL_ICONS[tool] || Wrench
}

// ===== Tool Name Mapping (Chinese) =====

const TOOL_NAMES: Record<string, string> = {
  read_file: '读取文件',
  write_file: '写入文件',
  create_file: '创建文件',
  edit_file: '编辑文件',
  delete_file: '删除文件',
  list_directory: '列出目录',
  search_files: '搜索文件',
  run_command: '运行命令',
  execute_command: '执行命令',
  download_file: '下载文件',
  upload_file: '上传文件',
}

function getToolName(tool: string): string {
  return TOOL_NAMES[tool] || tool
}

// ===== Args Summary =====

function getArgsSummary(tool: string, args: Record<string, unknown>): string {
  switch (tool) {
    case 'read_file':
    case 'write_file':
    case 'create_file':
    case 'edit_file':
    case 'delete_file':
      return (args.path as string) || (args.file_path as string) || ''
    case 'run_command':
    case 'execute_command':
      return (args.command as string) || ''
    case 'list_directory':
      return (args.path as string) || (args.directory as string) || ''
    case 'search_files':
      return `${args.pattern || args.query || ''} ${args.path || ''}`.trim()
    default:
      return Object.entries(args)
        .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
        .join(' ')
        .slice(0, 100)
  }
}

// ===== Tool Call Card =====

export default function ToolCallCard({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(false)
  const openFile = useAppStore((s) => s.openFile)
  const session = useAppStore((s) => s.session)

  // Handle both tool_call and tool_result message types
  const isToolCall = message.type === 'tool_call'
  const isToolResult = message.type === 'tool_result'

  const tool = isToolCall
    ? (message as ToolCallMessage).tool
    : (message as ToolResultMessage).tool
  const args = isToolCall
    ? (message as ToolCallMessage).args
    : {}
  const status = isToolCall
    ? (message as ToolCallMessage).status
    : (message as ToolResultMessage).success
      ? 'success'
      : 'failed'
  const result = isToolCall
    ? (message as ToolCallMessage).result
    : (message as ToolResultMessage).result
  const error = isToolCall
    ? (message as ToolCallMessage).error
    : (message as ToolResultMessage).error

  const Icon = getToolIcon(tool)
  const toolName = getToolName(tool)
  const argsSummary = getArgsSummary(tool, args)

  // Status icon and color
  let StatusIcon = Clock
  let statusColor = 'var(--warning)'
  if (status === 'success') {
    StatusIcon = CheckCircle
    statusColor = 'var(--success)'
  } else if (status === 'failed') {
    StatusIcon = XCircle
    statusColor = 'var(--error)'
  }

  // Check if result has file content to open
  const canOpenInEditor = Boolean(
    tool === 'read_file' && result && typeof result === 'object' && (result as Record<string, unknown>).content
  )
  const canViewDiff = tool === 'write_file' || tool === 'edit_file' || tool === 'create_file'

  const handleOpenInEditor = () => {
    if (canOpenInEditor) {
      const content = (result as Record<string, unknown>).content as string
      const path = (args.path as string) || (args.file_path as string) || 'unknown'
      openFile(path, content)
    }
  }

  const handleViewDiff = () => {
    // For now, open the file content in editor
    if (result && typeof result === 'object') {
      const content = (result as Record<string, unknown>).content as string
      const path = (args.path as string) || (args.file_path as string) || 'unknown'
      if (content) {
        openFile(path, content)
      }
    }
  }

  return (
    <div className="mb-2 animate-fade-in">
      <div
        className="rounded-lg overflow-hidden"
        style={{
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-light)',
        }}
      >
        {/* Header */}
        <button
          className="flex items-center gap-2 w-full px-3 py-2.5 text-left transition-colors hover:bg-gray-50"
          style={{ backgroundColor: 'var(--bg-secondary)' }}
          onClick={() => setExpanded(!expanded)}
        >
          {/* Expand/Collapse Icon */}
          <div
            className="flex items-center justify-center w-5 h-5 rounded"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}
          >
            {expanded ? (
              <ChevronDown size={12} style={{ color: 'var(--text-muted)' }} />
            ) : (
              <ChevronRight size={12} style={{ color: 'var(--text-muted)' }} />
            )}
          </div>

          {/* Tool Icon */}
          <div
            className="flex items-center justify-center w-7 h-7 rounded-md"
            style={{ backgroundColor: 'var(--accent-lighter)' }}
          >
            <Icon size={14} style={{ color: 'var(--accent-primary)' }} />
          </div>

          {/* Tool Name */}
          <span
            className="text-sm font-medium"
            style={{ color: 'var(--text-primary)' }}
          >
            {toolName}
          </span>

          {/* Args Summary */}
          <span
            className="text-xs truncate flex-1 px-2 py-0.5 rounded"
            style={{ color: 'var(--text-secondary)', backgroundColor: 'var(--bg-tertiary)' }}
          >
            {argsSummary || '无参数'}
          </span>

          {/* Status Icon */}
          <div className="flex items-center gap-1">
            <StatusIcon size={14} style={{ color: statusColor }} />
            <span className="text-xs" style={{ color: statusColor }}>
              {status === 'running' ? '执行中' : status === 'success' ? '成功' : status === 'failed' ? '失败' : '等待中'}
            </span>
          </div>
        </button>

        {/* Expanded Content */}
        {expanded && (
          <div className="p-3 space-y-3 border-t animate-slide-down" style={{ borderColor: 'var(--border-light)' }}>
            {/* Args JSON */}
            <div>
              <div
                className="text-xs font-medium mb-1.5 flex items-center gap-1.5"
                style={{ color: 'var(--text-muted)' }}
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--accent-primary)' }} />
                参数
              </div>
              <pre
                className="text-xs p-2.5 rounded-lg overflow-x-auto"
                style={{
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text-secondary)',
                  fontFamily: 'var(--font-mono, monospace)',
                }}
              >
                {JSON.stringify(args, null, 2)}
              </pre>
            </div>

            {/* Result JSON */}
            {result !== undefined && result !== null && (
              <div>
                <div
                  className="text-xs font-medium mb-1.5 flex items-center gap-1.5"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--success)' }} />
                  结果
                </div>
                <pre
                  className="text-xs p-2.5 rounded-lg overflow-x-auto max-h-60"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                >
                  {typeof result === 'string'
                    ? result
                    : JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}

            {/* Error */}
            {error && (
              <div>
                <div
                  className="text-xs font-medium mb-1.5 flex items-center gap-1.5"
                  style={{ color: 'var(--error)' }}
                >
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--error)' }} />
                  错误
                </div>
                <pre
                  className="text-xs p-2.5 rounded-lg overflow-x-auto"
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--error)',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                >
                  {error}
                </pre>
              </div>
            )}

            {/* Action Buttons */}
            {(canOpenInEditor || canViewDiff) && (
              <div className="flex gap-2 pt-1">
                {canOpenInEditor && (
                  <button
                    className="btn btn-secondary flex items-center gap-1.5 text-xs"
                    onClick={handleOpenInEditor}
                  >
                    <FileText size={12} />
                    在编辑器中打开
                  </button>
                )}
                {canViewDiff && (
                  <button
                    className="btn btn-secondary flex items-center gap-1.5 text-xs"
                    onClick={handleViewDiff}
                  >
                    <GitCompare size={12} />
                    查看差异
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
