import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  ChatMessage,
  FileNode,
  TerminalOutput,
  ConfirmRequest,
  FeedbackRequest,
  Plan,
  WorkMode,
  Task,
  TaskStatus,
  ModelConfig,
  ThemeMode,
  Session,
} from '../types'

// ===== Built-in Models =====

const BUILT_IN_MODELS: ModelConfig[] = [
  {
    name: 'GPT-4 Turbo',
    apiBase: 'https://api.openai.com/v1',
    apiKey: '',
    isBuiltIn: true,
  },
  {
    name: 'GPT-4o',
    apiBase: 'https://api.openai.com/v1',
    apiKey: '',
    isBuiltIn: true,
  },
  {
    name: 'GPT-3.5 Turbo',
    apiBase: 'https://api.openai.com/v1',
    apiKey: '',
    isBuiltIn: true,
  },
]

// ===== Store Interface =====

interface AppState {
  // Session
  session: {
    sessionId: string | null
    workspace: string
    mode: WorkMode
    isRunning: boolean
  }

  // Files
  files: {
    fileTree: FileNode[]
    currentFile: string | null
    fileContent: string
    unsavedChanges: boolean
  }

  // Chat
  chat: {
    messages: ChatMessage[]
  }

  // Terminal
  terminal: {
    outputs: TerminalOutput[]
  }

  // Pending requests
  pendingConfirm: ConfirmRequest | null
  pendingFeedback: FeedbackRequest | null
  pendingPlan: Plan | null

  // Tasks
  tasks: Task[]
  currentTaskId: string | null

  // Models
  models: ModelConfig[]
  currentModel: string

  // UI
  theme: ThemeMode
  sidebarCollapsed: boolean
  terminalCollapsed: boolean
  taskListCollapsed: boolean
  taskStartedAt: number | null
  showSettings: boolean
  wsConnected: boolean

  // ===== Actions =====
  setSession: (session: Partial<Session>) => void
  setRunning: (running: boolean) => void
  setTaskStartedAt: (timestamp: number | null) => void
  setMode: (mode: WorkMode) => void
  setFileTree: (tree: FileNode[]) => void
  openFile: (path: string, content: string) => void
  setFileContent: (content: string) => void
  markUnsaved: (unsaved: boolean) => void
  addMessage: (message: ChatMessage) => void
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void
  appendToMessage: (id: string, content: string) => void
  addTerminalOutput: (output: TerminalOutput) => void
  clearTerminal: () => void
  setPendingConfirm: (req: ConfirmRequest | null) => void
  setPendingFeedback: (req: FeedbackRequest | null) => void
  setPendingPlan: (plan: Plan | null) => void
  addTask: (task: Task) => void
  removeTask: (id: string) => void
  setCurrentTask: (id: string | null) => void
  setTasks: (tasks: Task[]) => void
  updateTaskStatus: (id: string, status: TaskStatus) => void
  setTheme: (theme: ThemeMode) => void
  toggleSidebar: () => void
  toggleTerminal: () => void
  toggleTaskList: () => void
  setShowSettings: (show: boolean) => void
  addModel: (model: ModelConfig) => void
  upsertModel: (model: ModelConfig) => void
  setModels: (models: ModelConfig[]) => void
  setModel: (name: string) => void
  removeModel: (name: string) => void
  clearMessages: () => void
  setWsConnected: (connected: boolean) => void
}

// ===== Helper: Generate ID =====

function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
}

// ===== Store =====

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Session
      session: {
        sessionId: null,
        workspace: '',
        mode: 'WORK',
        isRunning: false,
      },

      // Files
      files: {
        fileTree: [],
        currentFile: null,
        fileContent: '',
        unsavedChanges: false,
      },

      // Chat
      chat: {
        messages: [],
      },

      // Terminal
      terminal: {
        outputs: [],
      },

      // Pending
      pendingConfirm: null,
      pendingFeedback: null,
      pendingPlan: null,

      // Tasks
      tasks: [],
      currentTaskId: null,

      // Models
      models: BUILT_IN_MODELS,
      currentModel: 'GPT-4o',

      // UI
      theme: 'dark',
      sidebarCollapsed: false,
      terminalCollapsed: true,
      taskListCollapsed: false,
      taskStartedAt: null,
      showSettings: false,
      wsConnected: false,

      // ===== Actions =====

      setSession: (session) =>
        set((state) => ({
          session: {
            ...state.session,
            ...session,
          },
        })),

      setRunning: (running) =>
        set((state) => ({
          session: { ...state.session, isRunning: running },
          taskStartedAt: running ? Date.now() : state.taskStartedAt,
        })),

      setTaskStartedAt: (timestamp) => set({ taskStartedAt: timestamp }),

      setMode: (mode) =>
        set((state) => ({
          session: { ...state.session, mode },
        })),

      setFileTree: (tree) =>
        set((state) => ({
          files: { ...state.files, fileTree: tree },
        })),

      openFile: (path, content) =>
        set((state) => ({
          files: {
            ...state.files,
            currentFile: path,
            fileContent: content,
            unsavedChanges: false,
          },
        })),

      setFileContent: (content) =>
        set((state) => ({
          files: { ...state.files, fileContent: content },
        })),

      markUnsaved: (unsaved) =>
        set((state) => ({
          files: { ...state.files, unsavedChanges: unsaved },
        })),

      addMessage: (message) =>
        set((state) => ({
          chat: {
            messages: [...state.chat.messages, message],
          },
        })),

      updateMessage: (id, updates) =>
        set((state) => ({
          chat: {
            messages: state.chat.messages.map((m) =>
              m.id === id ? ({ ...m, ...updates } as ChatMessage) : m
            ),
          },
        })),

      appendToMessage: (id, content) =>
        set((state) => ({
          chat: {
            messages: state.chat.messages.map((m) =>
              m.id === id && m.type === 'assistant'
                ? { ...m, content: (m.content || '') + content } as ChatMessage
                : m
            ),
          },
        })),

      addTerminalOutput: (output) =>
        set((state) => ({
          terminal: {
            outputs: [...state.terminal.outputs, output],
          },
        })),

      clearTerminal: () =>
        set((state) => ({
          terminal: { outputs: [] },
        })),

      setPendingConfirm: (req) => set({ pendingConfirm: req }),

      setPendingFeedback: (req) => set({ pendingFeedback: req }),

      setPendingPlan: (plan) => set({ pendingPlan: plan }),

      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),

      removeTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id),
          currentTaskId: state.currentTaskId === id ? null : state.currentTaskId,
        })),

      setCurrentTask: (id) => set({ currentTaskId: id }),

      setTasks: (tasks) => set({ tasks }),

      updateTaskStatus: (id, status) =>
        set((state) => ({
          tasks: state.tasks.map((t) =>
            t.id === id ? { ...t, status } : t
          ),
        })),

      setTheme: (theme) => {
        document.documentElement.setAttribute('data-theme', theme)
        set({ theme })
      },

      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

      toggleTerminal: () =>
        set((state) => ({ terminalCollapsed: !state.terminalCollapsed })),

      toggleTaskList: () =>
        set((state) => ({ taskListCollapsed: !state.taskListCollapsed })),

      setShowSettings: (show) => set({ showSettings: show }),

      addModel: (model) =>
        set((state) => ({
          models: [...state.models, model],
        })),

      upsertModel: (model) =>
        set((state) => ({
          models: state.models.some((existing) => existing.name === model.name)
            ? state.models.map((existing) => existing.name === model.name ? model : existing)
            : [...state.models, model],
        })),

      setModels: (models) => set({ models }),

      setModel: (name) => set({ currentModel: name }),

      removeModel: (name) =>
        set((state) => ({
          models: state.models.filter((m) => m.name !== name),
          currentModel: state.currentModel === name ? (state.models[0]?.name || '') : state.currentModel,
        })),

      clearMessages: () =>
        set({
          chat: { messages: [] },
        }),

      setWsConnected: (connected) => set({ wsConnected: connected }),
    }),
    {
      name: 'guardcode-storage',
      partialize: (state) => ({
        theme: state.theme,
        models: state.models,
        currentModel: state.currentModel,
        tasks: state.tasks,
        taskListCollapsed: state.taskListCollapsed,
        taskStartedAt: state.taskStartedAt,
      }),
    }
  )
)

// Export helper
export { genId }
