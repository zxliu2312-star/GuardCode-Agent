import { useState, useEffect, useCallback } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  File as FileIcon,
  FileCode,
  FileJson,
  FileText,
  FileType,
  RefreshCw,
} from 'lucide-react'
import type { FileNode } from '../types'

// ===== File Icon by Extension =====

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  switch (ext) {
    case 'ts':
    case 'tsx':
    case 'js':
    case 'jsx':
    case 'vue':
    case 'svelte':
      return FileCode
    case 'json':
      return FileJson
    case 'md':
    case 'txt':
    case 'log':
      return FileText
    case 'css':
    case 'scss':
    case 'less':
      return FileType
    default:
      // Check for special filenames
      if (name.toLowerCase() === 'dockerfile') return FileCode
      return FileIcon
  }
}

function getFileIconColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  switch (ext) {
    case 'ts':
    case 'tsx':
      return '#3178c6' // TypeScript blue
    case 'js':
    case 'jsx':
      return '#f7df1e' // JavaScript yellow
    case 'json':
      return '#cbcb41'
    case 'css':
    case 'scss':
    case 'less':
      return '#264de4'
    case 'md':
      return 'var(--text-secondary)'
    case 'html':
      return '#e34c26'
    case 'py':
      return '#3572A5'
    case 'go':
      return '#00ADD8'
    case 'rs':
      return '#dea584'
    default:
      return 'var(--text-secondary)'
  }
}

// ===== File Tree Item =====

interface FileTreeItemProps {
  node: FileNode
  level: number
  onOpenFile: (node: FileNode) => void
  expandedPaths: Set<string>
  toggleExpand: (node: FileNode) => void
}

function FileTreeItem({
  node,
  level,
  onOpenFile,
  expandedPaths,
  toggleExpand,
}: FileTreeItemProps) {
  const isDirectory = node.type === 'directory'
  const isExpanded = expandedPaths.has(node.path)
  const currentFile = useAppStore((s) => s.files.currentFile)
  const isActive = currentFile === node.path

  const handleClick = () => {
    if (isDirectory) {
      toggleExpand(node)
    } else {
      onOpenFile(node)
    }
  }

  const Icon = isDirectory
    ? isExpanded
      ? FolderOpen
      : Folder
    : getFileIcon(node.name)
  const iconColor = isDirectory ? 'var(--accent)' : getFileIconColor(node.name)

  return (
    <div>
      <button
        className="flex items-center gap-1 w-full px-1 py-0.5 rounded text-sm transition-colors"
        style={{
          paddingLeft: `${level * 12 + 4}px`,
          backgroundColor: isActive ? 'var(--bg-active)' : 'transparent',
          color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
        }}
        onClick={handleClick}
      >
        {/* Expand/Collapse Icon */}
        {isDirectory ? (
          isExpanded ? (
            <ChevronDown size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          ) : (
            <ChevronRight size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          )
        ) : (
          <span style={{ width: 12, flexShrink: 0 }} />
        )}

        {/* File/Folder Icon */}
        <Icon size={14} style={{ color: iconColor, flexShrink: 0 }} />

        {/* Name */}
        <span className="truncate flex-1 text-left">{node.name}</span>
      </button>

      {/* Children */}
      {isDirectory && isExpanded && node.children && node.children.length > 0 && (
        <div>
          {node.children.map((child) => (
            <FileTreeItem
              key={child.path}
              node={child}
              level={level + 1}
              onOpenFile={onOpenFile}
              expandedPaths={expandedPaths}
              toggleExpand={toggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ===== File Tree Component =====

export default function FileTree() {
  const fileTree = useAppStore((s) => s.files.fileTree)
  const setFileTree = useAppStore((s) => s.setFileTree)
  const openFile = useAppStore((s) => s.openFile)
  const session = useAppStore((s) => s.session)
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  // ===== Load File Tree =====
  const loadFileTree = useCallback(async () => {
    if (!session.workspace) return

    setLoading(true)
    try {
      const result = await apiClient.getFiles('.', session.workspace)
      const tree = result.entries || []
      setFileTree(tree)
      setExpandedPaths(new Set())
    } catch (err) {
      console.error('Failed to load file tree:', err)
      setFileTree([])
    } finally {
      setLoading(false)
    }
  }, [session.workspace, setFileTree])

  // ===== Load on workspace change =====
  useEffect(() => {
    if (session.workspace) {
      loadFileTree()
    }
  }, [session.workspace, loadFileTree])

  // ===== Toggle Expand =====
  const toggleExpand = async (node: FileNode) => {
    if (expandedPaths.has(node.path)) {
      setExpandedPaths((prev) => {
        const next = new Set(prev)
        next.delete(node.path)
        return next
      })
      return
    }

    if (!node.children) {
      try {
        const result = await apiClient.getFiles(node.path, session.workspace)
        node.children = result.entries || []
        setFileTree([...fileTree])
      } catch (err) {
        console.error('Failed to load directory:', err)
        return
      }
    }

    setExpandedPaths((prev) => new Set(prev).add(node.path))
  }

  // ===== Handle Open File =====
  const handleOpenFile = async (node: FileNode) => {
    if (!session.workspace) return

    try {
      const content = await apiClient.getFileContent(node.path, session.workspace)
      openFile(node.path, content)
    } catch (err) {
      console.error('Failed to read file:', err)
      // Open with empty content on error
      openFile(node.path, '')
    }
  }

  // ===== Auto-refresh when fileTree changes (agent modifications) =====
  useEffect(() => {
    // This effect runs when fileTree is updated from WebSocket events
    // Could add logic here to auto-expand new directories
  }, [fileTree])

  return (
    <div
      className="border-b shrink-0"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderColor: 'var(--border)',
        maxHeight: '200px',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between h-8 px-3 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color: 'var(--text-muted)' }}
        >
          文件浏览器
        </span>
        <button
          className="icon-btn"
          onClick={loadFileTree}
          disabled={loading}
          title="刷新"
          style={{ width: '20px', height: '20px' }}
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Tree */}
      <div className="overflow-y-auto p-1" style={{ maxHeight: '160px' }}>
        {fileTree.length === 0 ? (
          <div
            className="text-center py-4 text-xs"
            style={{ color: 'var(--text-muted)' }}
          >
            {session.workspace ? '暂无文件' : '请选择工作区'}
          </div>
        ) : (
          fileTree.map((node) => (
            <FileTreeItem
              key={node.path}
              node={node}
              level={0}
              onOpenFile={handleOpenFile}
              expandedPaths={expandedPaths}
              toggleExpand={toggleExpand}
            />
          ))
        )}
      </div>
    </div>
  )
}
