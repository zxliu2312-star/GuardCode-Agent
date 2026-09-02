import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { wsService } from '../services/wsService'
import {
  AlertTriangle,
  Shield,
  Check,
  X,
  Terminal,
  FileEdit,
  Trash,
  Download,
  ShieldCheck,
} from 'lucide-react'
import type { ConfirmRequest } from '../types'

// ===== Risk Level Config =====

const RISK_CONFIG: Record<
  string,
  { color: string; bgColor: string; borderColor: string; label: string; icon: typeof Shield }
> = {
  safe: {
    color: 'var(--success)',
    bgColor: 'rgba(34, 197, 94, 0.1)',
    borderColor: 'var(--success)',
    label: '安全',
    icon: Shield,
  },
  moderate: {
    color: 'var(--warning)',
    bgColor: 'rgba(245, 158, 11, 0.1)',
    borderColor: 'var(--warning)',
    label: '中等风险',
    icon: AlertTriangle,
  },
  dangerous: {
    color: 'var(--danger)',
    bgColor: 'rgba(220, 38, 38, 0.1)',
    borderColor: 'var(--danger)',
    label: '高风险',
    icon: AlertTriangle,
  },
}

// ===== Tool Icon =====

const TOOL_ICONS: Record<string, typeof Terminal> = {
  run_command: Terminal,
  execute_command: Terminal,
  write_file: FileEdit,
  edit_file: FileEdit,
  create_file: FileEdit,
  delete_file: Trash,
  download_file: Download,
}

function getToolIcon(tool: string) {
  return TOOL_ICONS[tool] || Terminal
}

// ===== Confirm Dialog =====

export default function ConfirmDialog() {
  const pendingConfirm = useAppStore((s) => s.pendingConfirm)
  const setPendingConfirm = useAppStore((s) => s.setPendingConfirm)
  const [reason, setReason] = useState('')

  if (!pendingConfirm) return null

  const riskLevel = pendingConfirm.riskLevel || 'moderate'
  const riskConfig = RISK_CONFIG[riskLevel]
  const RiskIcon = riskConfig.icon
  const ToolIcon = getToolIcon(pendingConfirm.tool)

  const handleConfirm = () => {
    wsService.sendConfirm(pendingConfirm.request_id, true)
    setPendingConfirm(null)
    setReason('')
  }

  const handleWhitelist = () => {
    wsService.sendConfirm(pendingConfirm.request_id, true, true)
    setPendingConfirm(null)
    setReason('')
  }

  const handleReject = () => {
    wsService.sendConfirm(pendingConfirm.request_id, false)
    setPendingConfirm(null)
    setReason('')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleReject()
      }}
    >
      <div
        className="w-full max-w-md rounded-xl shadow-2xl animate-slide-up"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          border: `2px solid ${riskConfig.borderColor}`,
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-5 py-4 border-b"
          style={{
            borderColor: 'var(--border)',
            backgroundColor: riskConfig.bgColor,
          }}
        >
          <div
            className="flex items-center justify-center w-10 h-10 rounded-full shrink-0"
            style={{ backgroundColor: riskConfig.color }}
          >
            <RiskIcon size={20} color="#fff" />
          </div>
          <div>
            <h3
              className="text-base font-semibold"
              style={{ color: 'var(--text-primary)' }}
            >
              确认操作
            </h3>
            <div
              className="flex items-center gap-1.5 text-xs"
              style={{ color: riskConfig.color }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: riskConfig.color }}
              />
              {riskConfig.label}
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {/* Message */}
          <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
            {pendingConfirm.message}
          </p>

          {/* Tool Info */}
          <div
            className="flex items-center gap-2 p-3 rounded-lg"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}
          >
            <ToolIcon size={16} style={{ color: 'var(--accent-primary)' }} />
            <span
              className="text-sm font-medium"
              style={{ color: 'var(--text-primary)' }}
            >
              {pendingConfirm.tool}
            </span>
          </div>

          {/* Args */}
          <div>
            <div
              className="text-xs font-medium mb-1"
              style={{ color: 'var(--text-muted)' }}
            >
              操作参数
            </div>
            <pre
              className="text-xs p-2 rounded overflow-x-auto max-h-40"
              style={{
                backgroundColor: 'var(--bg-primary)',
                color: 'var(--text-secondary)',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {JSON.stringify(pendingConfirm.args, null, 2)}
            </pre>
          </div>

          {/* Reason Input */}
          <div>
            <input
              type="text"
              className="input-field"
              placeholder="拒绝原因（可选）"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-2 px-5 py-4 border-t"
          style={{ borderColor: 'var(--border)' }}
        >
          <button
            className="btn btn-secondary flex items-center gap-1.5"
            onClick={handleReject}
          >
            <X size={14} />
            拒绝
          </button>
          <button
            className="btn btn-secondary flex items-center gap-1.5"
            onClick={handleWhitelist}
            title="将此类命令加入白名单，后续不再询问"
          >
            <ShieldCheck size={14} />
            加入白名单
          </button>
          <button
            className="btn btn-primary flex items-center gap-1.5"
            onClick={handleConfirm}
            title="仅本次放行"
          >
            <Check size={14} />
            仅本次放行
          </button>
        </div>
      </div>
    </div>
  )
}
