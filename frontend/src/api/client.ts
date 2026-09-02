import type { Session, FileNode, FileDirectoryResponse, FileContentResponse, WorkMode, BrowseResult, ModelConfig, DBModelConfig, WorkspaceSetting, DBTask, DBRule, ChatMessage } from '../types'

// ===== API Base URL =====

const API_BASE = '/api'

// ===== Helper: Build URL with Query Params =====

function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value)
      }
    })
  }
  return url.toString()
}

// ===== Helper: Handle Response =====

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText)
    throw new Error(`API Error ${response.status}: ${errorText}`)
  }
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return response.json()
  }
  return response.text() as unknown as T
}

// ===== Session API =====

export async function createSession(
  workspace: string,
  mode: WorkMode
): Promise<Session> {
  const response = await fetch(buildUrl('/sessions'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace, mode }),
  })
  const result = await handleResponse<{ session_id: string; workspace: string; mode: string }>(response)
  return {
    sessionId: result.session_id,
    workspace: result.workspace,
    mode: result.mode as WorkMode,
    status: 'idle',
    isRunning: false,
    createdAt: Date.now(),
  }
}

export async function listSessions(): Promise<Session[]> {
  const response = await fetch(buildUrl('/sessions'), {
    method: 'GET',
  })
  return handleResponse<Session[]>(response)
}

export async function getSession(id: string): Promise<Session> {
  const response = await fetch(buildUrl(`/sessions/${id}`), {
    method: 'GET',
  })
  return handleResponse<Session>(response)
}

export async function startTask(
  id: string,
  task: string,
  model?: string,
  apiBase?: string,
  apiKey?: string
): Promise<{ status: string }> {
  const body: Record<string, unknown> = { task }
  if (model) body.model = model
  if (apiBase) body.api_base = apiBase
  if (apiKey) body.api_key = apiKey

  const response = await fetch(buildUrl(`/sessions/${id}/start`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse<{ status: string }>(response)
}

export async function stopSession(id: string): Promise<{ status: string }> {
  const response = await fetch(buildUrl(`/sessions/${id}/stop`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return handleResponse<{ status: string }>(response)
}

// ===== File API =====

export async function getFiles(
  path: string,
  workspace: string
): Promise<FileDirectoryResponse> {
  const response = await fetch(
    buildUrl('/files', { path, workspace }),
    { method: 'GET' }
  )
  return handleResponse<FileDirectoryResponse>(response)
}

export async function getFileContent(
  path: string,
  workspace: string
): Promise<string> {
  const response = await fetch(
    buildUrl('/files', { path, workspace }),
    { method: 'GET' }
  )
  const result = await handleResponse<FileContentResponse>(response)
  return result.content
}

export async function writeFile(
  path: string,
  content: string,
  workspace: string
): Promise<{ status: string }> {
  const response = await fetch(
    buildUrl('/files', { workspace }),
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, content }),
    }
  )
  return handleResponse<{ status: string }>(response)
}

export async function deleteFile(
  path: string,
  workspace: string
): Promise<{ status: string }> {
  const response = await fetch(
    buildUrl('/files', { path, workspace }),
    { method: 'DELETE' }
  )
  return handleResponse<{ status: string }>(response)
}

export async function uploadFile(
  file: File,
  workspace: string
): Promise<{ path: string; status: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(
    buildUrl('/upload', { workspace }),
    {
      method: 'POST',
      body: formData,
    }
  )
  return handleResponse<{ path: string; status: string }>(response)
}

// ===== WebSocket URL =====

export function getWebSocketUrl(sessionId: string): string {
  // In development, use the proxy through the frontend dev server
  // In production, use the same host as the current page
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host // includes port
  return `${protocol}//${host}${API_BASE}/sessions/${sessionId}/ws`
}

// ===== Export all as namespace =====

export const apiClient = {
  createSession,
  listSessions,
  getSession,
  startTask,
  stopSession,
  getFiles,
  getFileContent,
  writeFile,
  deleteFile,
  uploadFile,
  getWebSocketUrl,
  // Browse
  browseDirectories,
  selectWorkspace,
  // Models
  listModels,
  createModel,
  updateModel,
  deleteModel,
  // Tasks
  listDBTasks,
  createDBTask,
  getDBTask,
  updateDBTask,
  deleteDBTask,
  updateTaskStatus,
  // Workspaces
  listWorkspaces,
  saveWorkspace,
  deleteWorkspace,
  // Settings
  getSetting,
  setSetting,
  // Rules
  listRules,
  createRule,
  updateRule,
  deleteRule,
  // Messages
  getTaskMessages,
  saveMessage,
  deleteTaskMessages,
}

// ===== Browse Local Filesystem =====

export async function browseDirectories(path: string = ''): Promise<BrowseResult> {
  const params: Record<string, string> | undefined = path ? { path } : undefined
  const response = await fetch(buildUrl('/browse', params), { method: 'GET' })
  return handleResponse<BrowseResult>(response)
}

export async function selectWorkspace(path: string, isFavorite: boolean = false): Promise<{ success: boolean; path: string; display_name: string }> {
  const response = await fetch(buildUrl('/browse/select'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, is_favorite: isFavorite }),
  })
  return handleResponse(response)
}

// ===== Model Config API =====

export async function listModels(): Promise<{ models: DBModelConfig[] }> {
  const response = await fetch(buildUrl('/models'), { method: 'GET' })
  return handleResponse(response)
}

export async function createModel(model: { name: string; api_base: string; api_key: string; model_name: string; is_built_in: boolean }): Promise<{ model: DBModelConfig }> {
  const response = await fetch(buildUrl('/models'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  })
  return handleResponse(response)
}

export async function updateModel(configId: string, model: { name: string; api_base: string; api_key: string; model_name: string; is_built_in: boolean }): Promise<{ model: DBModelConfig }> {
  const response = await fetch(buildUrl(`/models/${configId}`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  })
  return handleResponse(response)
}

export async function deleteModel(configId: string): Promise<{ success: boolean }> {
  const response = await fetch(buildUrl(`/models/${configId}`), { method: 'DELETE' })
  return handleResponse(response)
}

// ===== Task CRUD API =====

export async function listDBTasks(): Promise<{ tasks: DBTask[] }> {
  const response = await fetch(buildUrl('/tasks'), { method: 'GET' })
  return handleResponse(response)
}

export async function createDBTask(task: { name: string; workspace: string; mode: string; status: string; session_id?: string; last_message?: string }): Promise<{ task: DBTask }> {
  const response = await fetch(buildUrl('/tasks'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task),
  })
  return handleResponse(response)
}

export async function getDBTask(taskId: string): Promise<{ task: DBTask }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}`), { method: 'GET' })
  return handleResponse(response)
}

export async function updateDBTask(taskId: string, task: { name: string; workspace: string; mode: string; status: string; session_id?: string; last_message?: string }): Promise<{ task: DBTask }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(task),
  })
  return handleResponse(response)
}

export async function deleteDBTask(taskId: string): Promise<{ success: boolean }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}`), { method: 'DELETE' })
  return handleResponse(response)
}

export async function updateTaskStatus(taskId: string, status: string, lastMessage?: string): Promise<{ success: boolean }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}/status`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, last_message: lastMessage }),
  })
  return handleResponse(response)
}

// ===== Workspace API =====

export async function listWorkspaces(): Promise<{ workspaces: WorkspaceSetting[] }> {
  const response = await fetch(buildUrl('/workspaces'), { method: 'GET' })
  return handleResponse(response)
}

export async function saveWorkspace(path: string, displayName?: string, isFavorite: boolean = false): Promise<{ workspace: WorkspaceSetting }> {
  const response = await fetch(buildUrl('/workspaces'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, display_name: displayName, is_favorite: isFavorite }),
  })
  return handleResponse(response)
}

export async function deleteWorkspace(path: string): Promise<{ success: boolean }> {
  const response = await fetch(buildUrl('/workspaces', { path }), { method: 'DELETE' })
  return handleResponse(response)
}

// ===== App Settings API =====

export async function getSetting(key: string): Promise<{ key: string; value: string | null }> {
  const response = await fetch(buildUrl(`/settings/${key}`), { method: 'GET' })
  return handleResponse(response)
}

export async function setSetting(key: string, value: string): Promise<{ key: string; value: string }> {
  const response = await fetch(buildUrl(`/settings/${key}`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  })
  return handleResponse(response)
}

// ===== Rules API =====

export async function listRules(): Promise<{ rules: DBRule[] }> {
  const response = await fetch(buildUrl('/rules'), { method: 'GET' })
  return handleResponse(response)
}

export async function createRule(rule: { name: string; content: string; is_enabled: boolean }): Promise<{ rule: DBRule }> {
  const response = await fetch(buildUrl('/rules'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  })
  return handleResponse(response)
}

export async function updateRule(ruleId: string, rule: { name: string; content: string; is_enabled: boolean }): Promise<{ rule: DBRule }> {
  const response = await fetch(buildUrl(`/rules/${ruleId}`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
  })
  return handleResponse(response)
}

export async function deleteRule(ruleId: string): Promise<{ success: boolean }> {
  const response = await fetch(buildUrl(`/rules/${ruleId}`), { method: 'DELETE' })
  return handleResponse(response)
}

// ===== Messages API =====

export async function getTaskMessages(taskId: string, limit?: number): Promise<{ messages: ChatMessage[] }> {
  const params = limit ? { limit: String(limit) } : undefined
  const response = await fetch(buildUrl(`/tasks/${taskId}/messages`, params), { method: 'GET' })
  return handleResponse(response)
}

export async function saveMessage(taskId: string, message: { id: string; type: string; content?: string; timestamp: number; metadata?: any }): Promise<{ message: any }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}/messages`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message),
  })
  return handleResponse(response)
}

export async function deleteTaskMessages(taskId: string): Promise<{ deleted: number }> {
  const response = await fetch(buildUrl(`/tasks/${taskId}/messages`), { method: 'DELETE' })
  return handleResponse(response)
}
