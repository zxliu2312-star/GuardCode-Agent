import { useState, useRef } from 'react'
import { useAppStore } from '../store/appStore'
import { wsService } from '../services/wsService'
import {
  Check,
  X,
  Plus,
  GripVertical,
  ListChecks,
  Trash2,
  ChevronUp,
  ChevronDown,
} from 'lucide-react'
import type { Plan, PlanStep } from '../types'

// ===== Plan Editor Component =====

export default function PlanEditor() {
  const pendingPlan = useAppStore((s) => s.pendingPlan)
  const setPendingPlan = useAppStore((s) => s.setPendingPlan)

  const [steps, setSteps] = useState<PlanStep[]>(pendingPlan?.steps || [])
  const [summary, setSummary] = useState(pendingPlan?.summary || '')
  const [rejectFeedback, setRejectFeedback] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)
  const dragIndexRef = useRef<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)

  if (!pendingPlan) return null

  // ===== Step Actions =====

  const updateStep = (id: string, updates: Partial<PlanStep>) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, ...updates, modified: true } : s))
    )
  }

  const toggleStepApproved = (id: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, approved: !s.approved } : s))
    )
  }

  const addStep = () => {
    const newStep: PlanStep = {
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      action: '新步骤',
      target: '',
      purpose: '',
      approved: true,
      modified: true,
      status: 'pending',
    }
    setSteps((prev) => [...prev, newStep])
  }

  const removeStep = (id: string) => {
    setSteps((prev) => prev.filter((s) => s.id !== id))
  }

  const moveStep = (index: number, direction: 'up' | 'down') => {
    setSteps((prev) => {
      const newSteps = [...prev]
      const targetIndex = direction === 'up' ? index - 1 : index + 1
      if (targetIndex < 0 || targetIndex >= newSteps.length) return prev
      ;[newSteps[index], newSteps[targetIndex]] = [newSteps[targetIndex], newSteps[index]]
      return newSteps
    })
  }

  // ===== Drag and Drop =====

  const handleDragStart = (index: number) => {
    dragIndexRef.current = index
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    setDragOverIndex(index)
  }

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault()
    const dragIndex = dragIndexRef.current
    if (dragIndex === null || dragIndex === dropIndex) return

    setSteps((prev) => {
      const newSteps = [...prev]
      const [draggedStep] = newSteps.splice(dragIndex, 1)
      newSteps.splice(dropIndex, 0, draggedStep)
      return newSteps.map((s) => ({ ...s, modified: true }))
    })

    dragIndexRef.current = null
    setDragOverIndex(null)
  }

  // ===== Approve / Reject =====

  const handleApprove = () => {
    const approvedPlan: Plan = {
      steps: steps.map((s) => ({ ...s })),
      summary,
    }
    wsService.sendPlanApproved(approvedPlan)
    setPendingPlan(null)
  }

  const handleReject = () => {
    if (!showRejectInput) {
      setShowRejectInput(true)
      return
    }
    wsService.sendPlanRejected(rejectFeedback || '计划被拒绝')
    setPendingPlan(null)
    setRejectFeedback('')
    setShowRejectInput(false)
  }

  const approvedCount = steps.filter((s) => s.approved !== false).length
  const totalCount = steps.length

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) setPendingPlan(null)
      }}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-xl shadow-2xl animate-slide-up"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-5 py-4 border-b shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <div
            className="flex items-center justify-center w-10 h-10 rounded-full shrink-0"
            style={{ backgroundColor: 'var(--accent)' }}
          >
            <ListChecks size={20} color="#fff" />
          </div>
          <div className="flex-1">
            <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              执行计划
            </h3>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              已批准 {approvedCount}/{totalCount} 步骤
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="px-5 py-3 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
            计划摘要
          </div>
          <textarea
            className="input-field resize-none"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={2}
            style={{ color: 'var(--text-primary)' }}
          />
        </div>

        {/* Steps List */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          <div className="space-y-2">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className="flex items-start gap-2 p-3 rounded-lg transition-all"
                draggable
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDrop={(e) => handleDrop(e, index)}
                style={{
                  backgroundColor:
                    dragOverIndex === index ? 'var(--bg-hover)' : 'var(--bg-tertiary)',
                  border: step.approved === false
                    ? '1px solid var(--error)'
                    : '1px solid var(--border)',
                  opacity: step.approved === false ? 0.6 : 1,
                }}
              >
                {/* Drag Handle */}
                <div
                  className="cursor-grab active:cursor-grabbing pt-1"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <GripVertical size={14} />
                </div>

                {/* Checkbox */}
                <button
                  className="mt-0.5 shrink-0"
                  onClick={() => toggleStepApproved(step.id)}
                  style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '4px',
                    border: `2px solid ${step.approved !== false ? 'var(--success)' : 'var(--text-muted)'}`,
                    backgroundColor: step.approved !== false ? 'var(--success)' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {step.approved !== false && <Check size={12} color="#fff" />}
                </button>

                {/* Step Content */}
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs font-medium px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--accent)' }}
                    >
                      {index + 1}
                    </span>
                    <input
                      type="text"
                      className="flex-1 bg-transparent text-sm font-medium outline-none"
                      style={{ color: 'var(--text-primary)' }}
                      value={step.action}
                      onChange={(e) => updateStep(step.id, { action: e.target.value })}
                    />
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      className="flex-1 bg-transparent text-xs outline-none"
                      style={{ color: 'var(--text-secondary)' }}
                      placeholder="目标"
                      value={step.target}
                      onChange={(e) => updateStep(step.id, { target: e.target.value })}
                    />
                  </div>
                  <input
                    type="text"
                    className="w-full bg-transparent text-xs outline-none"
                    style={{ color: 'var(--text-muted)' }}
                    placeholder="目的"
                    value={step.purpose}
                    onChange={(e) => updateStep(step.id, { purpose: e.target.value })}
                  />
                </div>

                {/* Step Controls */}
                <div className="flex flex-col gap-0.5 shrink-0">
                  <button
                    className="icon-btn"
                    style={{ width: '20px', height: '20px' }}
                    onClick={() => moveStep(index, 'up')}
                    disabled={index === 0}
                    title="上移"
                  >
                    <ChevronUp size={12} />
                  </button>
                  <button
                    className="icon-btn"
                    style={{ width: '20px', height: '20px' }}
                    onClick={() => moveStep(index, 'down')}
                    disabled={index === steps.length - 1}
                    title="下移"
                  >
                    <ChevronDown size={12} />
                  </button>
                  <button
                    className="icon-btn"
                    style={{ width: '20px', height: '20px' }}
                    onClick={() => removeStep(step.id)}
                    title="删除步骤"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Add Step Button */}
          <button
            className="w-full mt-3 flex items-center justify-center gap-1.5 py-2 rounded-lg text-sm transition-colors"
            style={{
              border: '1px dashed var(--border)',
              color: 'var(--text-secondary)',
            }}
            onClick={addStep}
          >
            <Plus size={14} />
            添加步骤
          </button>
        </div>

        {/* Reject Input */}
        {showRejectInput && (
          <div className="px-5 py-3 border-t animate-slide-up" style={{ borderColor: 'var(--border)' }}>
            <textarea
              className="input-field resize-none"
              placeholder="请输入拒绝原因或修改建议..."
              value={rejectFeedback}
              onChange={(e) => setRejectFeedback(e.target.value)}
              rows={3}
              autoFocus
            />
          </div>
        )}

        {/* Footer */}
        <div
          className="flex items-center justify-between gap-2 px-5 py-4 border-t shrink-0"
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            拖拽步骤可重新排序，点击复选框可批准/取消
          </div>
          <div className="flex items-center gap-2">
            <button
              className="btn btn-secondary flex items-center gap-1.5"
              onClick={handleReject}
            >
              <X size={14} />
              {showRejectInput ? '确认拒绝' : '拒绝计划'}
            </button>
            <button
              className="btn btn-primary flex items-center gap-1.5"
              onClick={handleApprove}
            >
              <Check size={14} />
              批准计划
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
