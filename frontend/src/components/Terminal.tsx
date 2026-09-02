import { useEffect, useRef } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { useAppStore } from '../store/appStore'
import { X, Trash2, ChevronDown, TerminalSquare } from 'lucide-react'
import '@xterm/xterm/css/xterm.css'

export default function Terminal() {
  const terminalOutputs = useAppStore((s) => s.terminal.outputs)
  const clearTerminal = useAppStore((s) => s.clearTerminal)
  const toggleTerminal = useAppStore((s) => s.toggleTerminal)
  const theme = useAppStore((s) => s.theme)

  const terminalRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const lastOutputCountRef = useRef(0)

  // ===== Initialize xterm.js =====
  useEffect(() => {
    if (!terminalRef.current) return

    const term = new XTerm({
      theme: {
        background:
          theme === 'light' ? '#ffffff' : theme === 'medium' ? '#2d2d44' : '#1a1a2e',
        foreground:
          theme === 'light' ? '#1a1a2e' : theme === 'medium' ? '#d4d4e8' : '#e4e4ef',
        cursor: '#6366f1',
        selectionBackground: '#33335a',
      },
      fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
      fontSize: 13,
      cursorBlink: true,
      disableStdin: true,
      convertEol: true,
      scrollback: 10000,
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)

    term.open(terminalRef.current)
    fitAddon.fit()

    xtermRef.current = term
    fitAddonRef.current = fitAddon

    // Write welcome message
    term.writeln('GuardCode Agent Terminal')
    term.writeln('--------------------------------')

    // Handle resize
    const handleResize = () => {
      try {
        fitAddon.fit()
      } catch (e) {
        // Ignore fit errors
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      term.dispose()
      xtermRef.current = null
    }
  }, [])

  // ===== Update theme =====
  useEffect(() => {
    if (xtermRef.current) {
      xtermRef.current.options.theme = {
        background:
          theme === 'light' ? '#ffffff' : theme === 'medium' ? '#2d2d44' : '#1a1a2e',
        foreground:
          theme === 'light' ? '#1a1a2e' : theme === 'medium' ? '#d4d4e8' : '#e4e4ef',
        cursor: '#6366f1',
        selectionBackground: '#33335a',
      }
    }
  }, [theme])

  // ===== Write new outputs =====
  useEffect(() => {
    if (!xtermRef.current) return

    const newOutputs = terminalOutputs.slice(lastOutputCountRef.current)
    lastOutputCountRef.current = terminalOutputs.length

    newOutputs.forEach((output) => {
      const term = xtermRef.current!
      term.writeln('')
      term.writeln(`$ ${output.command}`)

      if (output.stdout) {
        output.stdout.split('\n').forEach((line) => term.writeln(line))
      }

      if (output.stderr) {
        output.stderr.split('\n').forEach((line) => {
          term.writeln(`\x1b[31m${line}\x1b[0m`) // Red for stderr
        })
      }

      if (output.exitCode !== 0) {
        term.writeln(`\x1b[31m[退出码: ${output.exitCode}]\x1b[0m`)
      }

      term.writeln('--------------------------------')
    })

    // Scroll to bottom
    xtermRef.current.scrollToBottom()
  }, [terminalOutputs])

  // ===== Fit on mount =====
  useEffect(() => {
    if (fitAddonRef.current) {
      try {
        fitAddonRef.current.fit()
      } catch (e) {
        // Ignore
      }
    }
  })

  return (
    <div
      className="flex flex-col border-t shrink-0"
      style={{
        backgroundColor: 'var(--bg-primary)',
        borderColor: 'var(--border)',
        height: '220px',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between h-8 px-3 border-b"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="flex items-center gap-2">
          <TerminalSquare size={14} style={{ color: 'var(--accent)' }} />
          <span
            className="text-xs font-medium uppercase tracking-wider"
            style={{ color: 'var(--text-muted)' }}
          >
            终端
          </span>
          {terminalOutputs.length > 0 && (
            <span
              className="text-xs px-1.5 rounded"
              style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
            >
              {terminalOutputs.length}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <button
            className="icon-btn"
            onClick={clearTerminal}
            title="清空终端"
            style={{ width: '20px', height: '20px' }}
          >
            <Trash2 size={12} />
          </button>
          <button
            className="icon-btn"
            onClick={toggleTerminal}
            title="收起终端"
            style={{ width: '20px', height: '20px' }}
          >
            <ChevronDown size={12} />
          </button>
          <button
            className="icon-btn"
            onClick={toggleTerminal}
            title="关闭终端"
            style={{ width: '20px', height: '20px' }}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div ref={terminalRef} className="flex-1 overflow-hidden" />

      {/* Empty State */}
      {terminalOutputs.length === 0 && (
        <div
          className="absolute pointer-events-none text-xs"
          style={{
            color: 'var(--text-muted)',
            top: '40px',
            left: '12px',
          }}
        >
          等待命令输出...
        </div>
      )}
    </div>
  )
}
