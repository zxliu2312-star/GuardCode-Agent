import { useState } from 'react'
import { useAppStore } from '../store/appStore'
import { wsService } from '../services/wsService'
import {
  MessageSquare,
  Play,
  Edit3,
  Square,
  AlertCircle,
} from 'lucide-react'

// ===== Feedback Dialog Component =====

export default function FeedbackDialog() {
  const pendingFeedback = useAppStore((s) => s.pendingFeedback)
  const setPendingFeedback = useAppStore((s) => s.setPendingFeedback)
  const setRunning = useAppStore((s) => s.setRunning)
  const [feedbackText, setFeedbackText] = useState('')
  const [showAdjustInput, setShowAdjustInput] = useState(false)

  if (!pendingFeedback) return null

  // ===== Handle Actions =====

  const handleContinue = () => {
    wsService.sendFeedback(pendingFeedback.request_id, 'continue', '')
    setPendingFeedback(null)
    setFeedbackText('')
    setShowAdjustInput(false)
  }

  const handleAdjust = () => {
    if (!showAdjustInput) {
      setShowAdjustInput(true)
      return
    }
    wsService.sendFeedback(pendingFeedback.request_id, 'adjust', feedbackText)
    setPendingFeedback(null)
    setFeedbackText('')
    setShowAdjustInput(false)
  }

  const handleStop = () => {
    wsService.sendFeedback(pendingFeedback.request_id, 'stop', '')
    setRunning(false)
    setPendingFeedback(null)
    setFeedbackText('')
    setShowAdjustInput(false)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) handleContinue()
      }}
    >
      <div
        className="w-full max-w-md rounded-xl shadow-2xl animate-slide-up"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-5 py-4 border-b"
          style={{
            borderColor: 'var(--border)',
            backgroundColor: 'var(--bg-tertiary)',
          }}
        >
          <div
            className="flex items-center justify-center w-10 h-10 rounded-full shrink-0"
            style={{ backgroundColor: 'var(--accent)' }}
          >
            <MessageSquare size={20} color="#fff" />
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              需要您的反馈
            </h3>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              反馈模式 - 关键决策点
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3">
          {/* Message */}
          <div
            className="flex items-start gap-2 p-3 rounded-lg"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}
          >
            <AlertCircle size={16} style={{ color: 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {pendingFeedback.message}
            </p>
          </div>

          {/* Tool Info */}
          <div
            className="flex items-center gap-2 p-2 rounded-lg"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}
          >
            <span
              className="text-xs font-medium px-2 py-0.5 rounded"
              style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--accent)' }}
            >
              {pendingFeedback.tool}
            </span>
          </div>

          {/* Args */}
          {pendingFeedback.args && Object.keys(pendingFeedback.args).length > 0 && (
            <div>
              <div
                className="text-xs font-medium mb-1"
                style={{ color: 'var(--text-muted)' }}
              >
                操作详情
              </div>
              <pre
                className="text-xs p-2 rounded overflow-x-auto max-h-32"
                style={{
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-secondary)',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {JSON.stringify(pendingFeedback.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Adjust Input */}
          {showAdjustInput && (
            <div className="animate-slide-down">
              <div
                className="text-xs font-medium mb-1"
                style={{ color: 'var(--text-muted)' }}
              >
                调整建议
              </div>
              <textarea
                className="input-field resize-none"
                placeholder="请输入您的调整建议..."
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                rows={3}
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between gap-2 px-5 py-4 border-t"
          style={{ borderColor: 'var(--border)' }}
        >
          {/* Stop Button (Left) */}
          <button
            className="btn btn-danger flex items-center gap-1.5"
            onClick={handleStop}
          >
            <Square size={14} />
            停止
          </button>

          {/* Continue / Adjust (Right) */}
          <div className="flex items-center gap-2">
            <button
              className="btn btn-secondary flex items-center gap-1.5"
              onClick={handleAdjust}
            >
              <Edit3 size={14} />
              {showAdjustInput ? '提交调整' : '调整'}
            </button>
            <button
              className="btn btn-primary flex items-center gap-1.5"
              onClick={handleContinue}
            >
              <Play size={14} />
              继续
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
