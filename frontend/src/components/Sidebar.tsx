import { useState, useMemo, useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import {
  Plus,
  Folder,
  ChevronDown,
  ChevronRight,
  User,
  Bell,
  Settings,
  Trash2,
} from 'lucide-react'
import type { Task } from '../types'

export default function Sidebar() {
  const tasks = useAppStore((s) => s.tasks)
  const setTasks = useAppStore((s) => s.setTasks)
  const addTask = useAppStore((s) => s.addTask)
  const setCurrentTask = useAppStore((s) => s.setCurrentTask)
  const currentTaskId = useAppStore((s) => s.currentTaskId)
  const session = useAppStore((s) => s.session)
  const setSession = useAppStore((s) => s.setSession)
  const clearMessages = useAppStore((s) => s.clearMessages)
  const taskListCollapsed = useAppStore((s) => s.taskListCollapsed)
  const toggleTaskList = useAppStore((s) => s.toggleTaskList)
  const showSettings = useAppStore((s) => s.showSettings)
  const setShowSettings = useAppStore((s) => s.setShowSettings)

  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  // Load tasks from backend on mount
  useEffect(() => {
    loadTasks()
  }, [])

  const loadTasks = async () => {
    try {
      const result = await apiClient.listDBTasks()
      if (result.tasks && result.tasks.length > 0) {
        const dbTasks: Task[] = result.tasks.map((t: any) => ({
          id: t.id,
          name: t.name,
          workspace: t.workspace,
          mode: t.mode as Task['mode'],
          status: t.status as Task['status'],
          createdAt: new Date(t.created_at).getTime(),
          sessionId: t.session_id,
        }))
        setTasks(dbTasks)
      }
    } catch (err) {
      console.error('Failed to load tasks from DB:', err)
    }
  }

  // Group tasks by workspace
  const groupedTasks = useMemo(() => {
    const groups: Record<string, Task[]> = {}
    tasks.forEach((task) => {
      const ws = task.workspace || '纯对话'
      if (!groups[ws]) {
        groups[ws] = []
      }
      groups[ws].push(task)
    })
    return groups
  }, [tasks])

  // New task: directly exit current conversation and start a new one
  const handleNewTask = () => {
    clearMessages()
    setCurrentTask(null)
    setSession({
      sessionId: null,
      workspace: '',
      mode: 'WORK',
      isRunning: false,
    })
  }

  const handleSelectTask = async (task: Task) => {
    setCurrentTask(task.id)
    
    const sid = task.sessionId || task.id
    
    setSession({
      sessionId: sid,
      workspace: task.workspace,
      mode: task.mode,
      isRunning: task.status === 'running',
    })
    
    clearMessages()
    
    try {
      const result = await apiClient.getTaskMessages(task.id)
      if (result.messages && result.messages.length > 0) {
        const store = useAppStore.getState()
        result.messages.forEach((msg: any) => {
          const chatMsg = convertDBMessage(msg)
          if (chatMsg) {
            store.addMessage(chatMsg)
          }
        })
      }
    } catch (err) {
      console.error('Failed to load task messages:', err)
    }
    
    if (task.status !== 'running') {
      useAppStore.getState().setWsConnected(false)
    }
  }
  
  const convertDBMessage = (dbMsg: any): any => {
    const base = {
      id: dbMsg.id,
      timestamp: dbMsg.timestamp,
    }
    const metadata = dbMsg.metadata || {}
    
    switch (dbMsg.type) {
      case 'user':
        return {
          ...base,
          type: 'user',
          content: dbMsg.content || '',
          attachments: metadata.attachments,
        }
      case 'assistant':
        return {
          ...base,
          type: 'assistant',
          content: dbMsg.content || '',
          model: metadata.model,
        }
      case 'tool_call':
        return {
          ...base,
          type: 'tool_call',
          tool: metadata.tool || 'unknown',
          args: metadata.args || {},
          status: metadata.status || 'success',
          riskLevel: metadata.riskLevel,
        }
      case 'tool_result':
        return {
          ...base,
          type: 'tool_result',
          tool: metadata.tool || 'unknown',
          result: metadata.result,
          success: metadata.success !== false,
          error: metadata.error,
        }
      case 'system':
        return {
          ...base,
          type: 'system',
          content: dbMsg.content || '',
          level: metadata.level || 'info',
        }
      default:
        return null
    }
  }

  const handleDeleteTask = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await apiClient.deleteDBTask(taskId)
    } catch (err) {
      console.error('Failed to delete task:', err)
    }
    useAppStore.getState().removeTask(taskId)
  }

  const toggleGroup = (workspace: string) => {
    setExpandedGroups((prev) => ({ ...prev, [workspace]: !prev[workspace] }))
  }

  return (
    <aside
      className="flex flex-col shrink-0"
      style={{ 
        width: '260px',
        minWidth: '260px',
        backgroundColor: 'var(--bg-sidebar)', 
        borderRight: '1px solid var(--border-light)',
      }}
    >
      {/* New Task Button - directly starts a new conversation */}
      <div className="p-3">
        <button
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all"
          style={{
            backgroundColor: 'var(--bg-active)',
            color: 'var(--text-primary)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--bg-hover)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--bg-active)'
          }}
          onClick={handleNewTask}
        >
          <Plus size={16} strokeWidth={2} />
          <span>新建任务</span>
        </button>
      </div>

      {/* Task List Section */}
      <div className="flex-1 overflow-y-auto px-3">
        {/* Task List Header with Collapse Toggle */}
        <div className="flex items-center justify-between mb-2 px-2">
          <span className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
            任务列表
          </span>
          <button
            className="icon-btn"
            style={{ width: '20px', height: '20px' }}
            onClick={toggleTaskList}
            title={taskListCollapsed ? '展开任务列表' : '折叠任务列表'}
          >
            {taskListCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>

        {/* Task List Content (collapsible) */}
        {!taskListCollapsed && (
          <>
            {Object.keys(groupedTasks).length === 0 ? (
              <div
                className="text-center py-8 text-sm"
                style={{ color: 'var(--text-muted)' }}
              >
                暂无任务
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(groupedTasks).map(([workspace, groupTasks]) => (
                  <div key={workspace}>
                    {/* Workspace Header */}
                    <button
                      className="workspace-folder w-full"
                      onClick={() => toggleGroup(workspace)}
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        {expandedGroups[workspace] !== false ? (
                          <ChevronDown size={14} strokeWidth={2} style={{ color: 'var(--text-muted)' }} />
                        ) : (
                          <ChevronRight size={14} strokeWidth={2} style={{ color: 'var(--text-muted)' }} />
                        )}
                        <Folder size={16} strokeWidth={1.5} />
                        <span className="truncate">{workspace}</span>
                      </div>
                    </button>

                    {/* Task Items */}
                    {expandedGroups[workspace] !== false && (
                      <div className="mt-1 space-y-0.5">
                        {groupTasks.map((task) => (
                          <div
                            key={task.id}
                            className={`task-item w-full text-left flex items-center group ${task.id === currentTaskId ? 'active' : ''}`}
                            onClick={() => handleSelectTask(task)}
                            title={task.name}
                            style={{ cursor: 'pointer', paddingRight: '8px' }}
                          >
                            <span className="flex-1 truncate">{task.name}</span>
                            <button
                              className="icon-btn shrink-0 opacity-0 group-hover:opacity-100"
                              style={{ width: '20px', height: '20px' }}
                              onClick={(e) => handleDeleteTask(task.id, e)}
                              title="删除任务"
                            >
                              <Trash2 size={12} style={{ color: 'var(--danger)' }} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Collapsed state - show count */}
        {taskListCollapsed && tasks.length > 0 && (
          <div className="text-center py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            {tasks.length} 个任务
          </div>
        )}
      </div>

      {/* Footer: Settings + User */}
      <div
        className="flex items-center justify-end p-3 border-t"
        style={{ borderColor: 'var(--border-light)' }}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div
            className="flex items-center justify-center w-8 h-8 rounded-full shrink-0"
            style={{ backgroundColor: 'var(--bg-active)' }}
          >
            <User size={16} style={{ color: 'var(--text-secondary)' }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs truncate" style={{ color: 'var(--text-primary)' }}>
              用户
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              本地版
            </div>
          </div>
        </div>
        <button
          className="icon-btn"
          style={{ width: '24px', height: '24px' }}
          onClick={() => setShowSettings(!showSettings)}
          title="设置"
        >
          <Settings size={14} style={{ color: 'var(--text-secondary)' }} />
        </button>
      </div>
    </aside>
  )
}
