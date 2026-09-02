// ===== Chat Message Types =====

export type ChatMessageType =
  | 'user'
  | 'assistant'
  | 'tool_call'
  | 'tool_result'
  | 'system'

export interface BaseMessage {
  id: string
  type: ChatMessageType
  timestamp: number
}

export interface UserMessage extends BaseMessage {
  type: 'user'
  content: string
  attachments?: string[]
}

export interface AssistantMessage extends BaseMessage {
  type: 'assistant'
  content: string
  model?: string
  thinking?: string
}

export interface ToolCallMessage extends BaseMessage {
  type: 'tool_call'
  tool: string
  args: Record<string, unknown>
  status: 'pending' | 'running' | 'success' | 'failed'
  result?: unknown
  error?: string
  riskLevel?: 'safe' | 'moderate' | 'dangerous'
}

export interface ToolResultMessage extends BaseMessage {
  type: 'tool_result'
  tool: string
  result: unknown
  success: boolean
  error?: string
}

export interface SystemMessage extends BaseMessage {
  type: 'system'
  content: string
  level?: 'info' | 'warning' | 'error'
}

export type ChatMessage =
  | UserMessage
  | AssistantMessage
  | ToolCallMessage
  | ToolResultMessage
  | SystemMessage

// ===== File Types =====

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  children?: FileNode[]
  expanded?: boolean
}

// ===== Terminal Types =====

export interface TerminalOutput {
  id: string
  command: string
  stdout: string
  stderr: string
  exitCode: number
  timestamp: number
}

// ===== Confirm / Feedback Types =====

export interface ConfirmRequest {
  request_id: string
  tool: string
  args: Record<string, unknown>
  message: string
  riskLevel?: 'safe' | 'moderate' | 'dangerous'
}

export interface FeedbackRequest {
  request_id: string
  tool: string
  args: Record<string, unknown>
  message: string
}

// ===== Plan Types =====

export interface PlanStep {
  id: string
  action: string
  target: string
  purpose: string
  approved?: boolean
  modified?: boolean
  status?: 'pending' | 'running' | 'completed' | 'failed'
}

export interface Plan {
  steps: PlanStep[]
  summary: string
}

// ===== Server Event Types =====

export type ServerEventType =
  | 'tool_call'
  | 'tool_result'
  | 'confirm_request'
  | 'feedback_request'
  | 'plan_created'
  | 'plan_step_completed'
  | 'mode_changed'
  | 'context_compress'
  | 'done'
  | 'error'
  | 'blocked'
  | 'model_call'
  | 'info'
  | 'stopped'
  | 'risk_warning'
  | 'llm_start'
  | 'llm_chunk'
  | 'llm_done'

export interface ServerEvent {
  type: ServerEventType
  data: Record<string, unknown>
  timestamp?: number
  message?: string
}

// ===== Work Mode =====

export type WorkMode = 'PLAN' | 'WORK' | 'FEEDBACK' | 'RESEARCH'

// ===== Task Types =====

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'stopped'

export interface Task {
  id: string
  name: string
  workspace: string
  mode: WorkMode
  status: TaskStatus
  createdAt: number
  sessionId?: string
}

// ===== Model Config =====

export interface ModelConfig {
  name: string
  apiBase: string
  apiKey: string
  isBuiltIn: boolean
  modelName?: string
  id?: string
}

// DB representation (snake_case from API)
export interface DBModelConfig {
  id: string
  name: string
  api_base: string
  api_key: string
  model_name: string
  is_built_in: boolean
  created_at: string
  updated_at: string
}

export interface FileDirectoryResponse {
  type: 'directory'
  path: string
  entries: FileNode[]
}

export interface FileContentResponse {
  type: 'file'
  path: string
  content: string
  size: number
}

// ===== Browse Result =====

export interface BrowseEntry {
  name: string
  path: string
  type: 'directory' | 'file'
}

export interface BrowseResult {
  path: string
  parent: string | null
  entries: BrowseEntry[]
}

// ===== Workspace Setting =====

export interface WorkspaceSetting {
  id: string
  path: string
  display_name: string | null
  last_used: string
  is_favorite: number
}

// ===== DB Task =====

export interface DBTask {
  id: string
  name: string
  workspace: string
  mode: string
  status: string
  created_at: string
  updated_at: string
  session_id: string | null
  last_message: string | null
}

// ===== Session Types =====

export interface Session {
  sessionId: string | null
  workspace: string
  mode: WorkMode
  status: 'idle' | 'running' | 'stopped' | 'error'
  isRunning?: boolean
  createdAt: number
}

// ===== Theme =====

export type ThemeMode = 'dark' | 'light' | 'medium'

// ===== Rule =====

export interface DBRule {
  id: string
  name: string
  content: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface Rule {
  id: string
  name: string
  content: string
  isEnabled: boolean
}
