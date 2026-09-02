import { useEffect, useRef, useCallback } from 'react'
import Editor, { OnMount, BeforeMount } from '@monaco-editor/react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import { Save, FileText, X } from 'lucide-react'

// ===== Language Detection =====

function getLanguageByExtension(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const langMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    json: 'json',
    html: 'html',
    css: 'css',
    scss: 'scss',
    less: 'less',
    py: 'python',
    java: 'java',
    c: 'c',
    cpp: 'cpp',
    cs: 'csharp',
    go: 'go',
    rs: 'rust',
    rb: 'ruby',
    php: 'php',
    swift: 'swift',
    kt: 'kotlin',
    md: 'markdown',
    yml: 'yaml',
    yaml: 'yaml',
    xml: 'xml',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
    zsh: 'shell',
    dockerfile: 'dockerfile',
    toml: 'ini',
    ini: 'ini',
    vue: 'html',
    svelte: 'html',
  }
  return langMap[ext] || 'plaintext'
}

// ===== Code Editor Component =====

export default function CodeEditor() {
  const currentFile = useAppStore((s) => s.files.currentFile)
  const fileContent = useAppStore((s) => s.files.fileContent)
  const unsavedChanges = useAppStore((s) => s.files.unsavedChanges)
  const setFileContent = useAppStore((s) => s.setFileContent)
  const markUnsaved = useAppStore((s) => s.markUnsaved)
  const session = useAppStore((s) => s.session)
  const theme = useAppStore((s) => s.theme)
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

  // Monaco theme based on app theme
  const monacoTheme = theme === 'light' ? 'light' : 'vs-dark'

  // ===== Handle Editor Mount =====
  const handleMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor

    // Define custom dark theme
    monaco.editor.defineTheme('guardcode-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#16162a',
        'editor.foreground': '#e4e4ef',
        'editorLineNumber.foreground': '#6b6b8a',
        'editorLineNumber.activeForeground': '#a0a0b8',
        'editor.selectionBackground': '#33335a',
        'editor.lineHighlightBackground': '#20203a',
        'editorCursor.foreground': '#6366f1',
        'editorIndentGuide.background': '#2a2a4a',
        'editorIndentGuide.activeBackground': '#33335a',
      },
    })

    monaco.editor.defineTheme('guardcode-medium', {
      base: 'vs-dark',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#252538',
        'editor.foreground': '#d4d4e8',
        'editorLineNumber.foreground': '#7070a0',
        'editorLineNumber.activeForeground': '#a0a0c0',
        'editor.selectionBackground': '#454570',
        'editor.lineHighlightBackground': '#353550',
        'editorCursor.foreground': '#818cf8',
      },
    })

    // Ctrl+S to save
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      handleSave()
    })
  }, [])

  // ===== Before Mount =====
  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    // Configure TypeScript defaults
    monaco.languages.typescript.typescriptDefaults.setDiagnosticsOptions({
      noSemanticValidation: true,
      noSyntaxValidation: false,
    })
  }, [])

  // ===== Handle Content Change =====
  const handleChange = (value: string | undefined) => {
    setFileContent(value || '')
    markUnsaved(true)
  }

  // ===== Handle Save =====
  const handleSave = useCallback(async () => {
    if (!currentFile || !session.workspace) return

    try {
      await apiClient.writeFile(currentFile, fileContent, session.workspace)
      markUnsaved(false)
    } catch (err) {
      console.error('Save failed:', err)
    }
  }, [currentFile, fileContent, session.workspace, markUnsaved])

  // ===== Keyboard shortcut for save (outside Monaco) =====
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's' && currentFile) {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentFile, handleSave])

  // ===== Close File =====
  const handleClose = () => {
    useAppStore.getState().openFile('', '')
    useAppStore.setState((state) => ({
      files: { ...state.files, currentFile: null, fileContent: '', unsavedChanges: false },
    }))
  }

  if (!currentFile) {
    return null
  }

  const language = getLanguageByExtension(currentFile)
  const filename = currentFile.split(/[\\/]/).pop() || currentFile

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* ===== Editor Header ===== */}
      <div
        className="flex items-center justify-between h-9 px-3 border-b shrink-0"
        style={{
          backgroundColor: 'var(--bg-tertiary)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={14} style={{ color: 'var(--accent)' }} />
          <span
            className="text-sm truncate"
            style={{ color: 'var(--text-primary)' }}
          >
            {filename}
          </span>
          {unsavedChanges && (
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--warning)' }}
              title="未保存的更改"
            />
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            className="icon-btn"
            onClick={handleSave}
            disabled={!unsavedChanges}
            title="保存 (Ctrl+S)"
            style={{ opacity: unsavedChanges ? 1 : 0.4 }}
          >
            <Save size={14} />
          </button>
          <button className="icon-btn" onClick={handleClose} title="关闭文件">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* ===== Monaco Editor ===== */}
      <div className="flex-1 overflow-hidden">
        <Editor
          height="100%"
          language={language}
          value={fileContent}
          theme={
            theme === 'light'
              ? 'light'
              : theme === 'medium'
                ? 'guardcode-medium'
                : 'guardcode-dark'
          }
          onMount={handleMount}
          beforeMount={handleBeforeMount}
          onChange={handleChange}
          loading={
            <div
              className="flex items-center justify-center h-full text-sm"
              style={{ color: 'var(--text-muted)' }}
            >
              加载编辑器...
            </div>
          }
          options={{
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
            fontLigatures: true,
            minimap: { enabled: true, scale: 1 },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            insertSpaces: true,
            wordWrap: 'on',
            lineNumbers: 'on',
            renderWhitespace: 'selection',
            bracketPairColorization: { enabled: true },
            smoothScrolling: true,
            cursorBlinking: 'smooth',
            cursorSmoothCaretAnimation: 'on',
            padding: { top: 8, bottom: 8 },
            scrollbar: {
              verticalScrollbarSize: 8,
              horizontalScrollbarSize: 8,
            },
          }}
        />
      </div>

      {/* ===== Status Bar ===== */}
      <div
        className="flex items-center justify-between h-6 px-3 text-xs border-t shrink-0"
        style={{
          backgroundColor: 'var(--bg-tertiary)',
          borderColor: 'var(--border)',
          color: 'var(--text-muted)',
        }}
      >
        <span>{language}</span>
        <span className="truncate">{currentFile}</span>
      </div>
    </div>
  )
}
