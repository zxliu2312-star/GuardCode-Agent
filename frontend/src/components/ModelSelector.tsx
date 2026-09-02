import { useState, useRef, useEffect } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import {
  ChevronDown,
  Check,
  Plus,
  Cpu,
  X,
  Trash2,
} from 'lucide-react'
import type { ModelConfig } from '../types'

// ===== Model Selector Component =====

export default function ModelSelector() {
  const models = useAppStore((s) => s.models)
  const currentModel = useAppStore((s) => s.currentModel)
  const setModel = useAppStore((s) => s.setModel)
  const upsertModel = useAppStore((s) => s.upsertModel)
  const setModels = useAppStore((s) => s.setModels)
  const removeModel = useAppStore((s) => s.removeModel)

  const [isOpen, setIsOpen] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [newModel, setNewModel] = useState<ModelConfig>({
    name: '',
    apiBase: '',
    apiKey: '',
    isBuiltIn: false,
    modelName: '',
  })
  const dropdownRef = useRef<HTMLDivElement>(null)

  // ===== Close dropdown on outside click =====
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setShowAddForm(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // ===== Load models from backend on mount =====
  useEffect(() => {
    loadModels()
  }, [])

  const normalizeModels = (modelList: ModelConfig[]) => {
    const seen = new Set<string>()
    return modelList.filter((model) => {
      if (seen.has(model.name)) return false
      seen.add(model.name)
      return true
    })
  }

  const loadModels = async () => {
    try {
      const result = await apiClient.listModels()
      const dbModels: ModelConfig[] = (result.models || []).map((m) => ({
        name: m.name,
        apiBase: m.api_base,
        apiKey: m.api_key,
        isBuiltIn: m.is_built_in,
        modelName: m.model_name,
        id: m.id,
      }))
      const builtIn = models.filter((m) => m.isBuiltIn)
      const custom = dbModels.filter((m) => !m.isBuiltIn)
      setModels(normalizeModels([...builtIn, ...custom]))
    } catch (err) {
      console.error('Failed to load models from DB:', err)
    }
  }

  // ===== Handle model selection =====
  const handleSelectModel = (name: string) => {
    setModel(name)
    setIsOpen(false)
  }

  // ===== Handle add custom model =====
  const handleAddModel = async () => {
    if (!newModel.name.trim() || !newModel.apiBase.trim() || isSaving) return
    setIsSaving(true)
    try {
      // Save to backend database
      const result = await apiClient.createModel({
        name: newModel.name.trim(),
        api_base: newModel.apiBase.trim(),
        api_key: newModel.apiKey.trim(),
        model_name: newModel.modelName?.trim() || newModel.name.trim(),
        is_built_in: false,
      })

      const model: ModelConfig = {
        name: newModel.name.trim(),
        apiBase: newModel.apiBase.trim(),
        apiKey: newModel.apiKey.trim(),
        isBuiltIn: false,
        modelName: newModel.modelName?.trim() || newModel.name.trim(),
        id: result.model.id,
      }
      upsertModel(model)
      setModel(model.name)
      setSaveStatus({ type: 'success', message: `模型「${model.name}」已保存` })
      setTimeout(() => setSaveStatus(null), 2500)
    } catch (err) {
      // Fallback: save locally only
      console.error('Failed to save model to DB:', err)
      const model: ModelConfig = {
        name: newModel.name.trim(),
        apiBase: newModel.apiBase.trim(),
        apiKey: newModel.apiKey.trim(),
        isBuiltIn: false,
        modelName: newModel.modelName?.trim() || newModel.name.trim(),
      }
      upsertModel(model)
      setModel(model.name)
      setSaveStatus({ type: 'error', message: `保存失败：${err instanceof Error ? err.message : '未知错误'}，已临时添加` })
      setTimeout(() => setSaveStatus(null), 3500)
    }

    // Reset form
    setNewModel({ name: '', apiBase: '', apiKey: '', isBuiltIn: false, modelName: '' })
    setShowAddForm(false)
    setIsSaving(false)
  }

  // ===== Handle delete custom model =====
  const handleDeleteModel = async (model: ModelConfig, e: React.MouseEvent) => {
    e.stopPropagation()
    if (model.id) {
      try {
        await apiClient.deleteModel(model.id)
      } catch (err) {
        console.error('Failed to delete model from DB:', err)
      }
    }
    removeModel(model.name)
  }

  const builtInModels = models.filter((m) => m.isBuiltIn)
  const customModels = models.filter((m) => !m.isBuiltIn)

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors"
        style={{
          backgroundColor: 'var(--bg-primary)',
          color: 'var(--text-secondary)',
          border: '1px solid var(--border)',
        }}
        onClick={() => setIsOpen(!isOpen)}
        title="选择模型"
      >
        <Cpu size={14} style={{ color: 'var(--accent)' }} />
        <span className="truncate max-w-[100px]">{currentModel}</span>
        <ChevronDown
          size={12}
          style={{
            color: 'var(--text-muted)',
            transform: isOpen ? 'rotate(180deg)' : 'none',
            transition: 'transform 0.2s',
          }}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute bottom-full right-0 mb-1 w-80 rounded-lg shadow-xl z-50 animate-slide-down"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            border: '1px solid var(--border)',
            maxHeight: '85vh',
            overflowY: 'auto',
          }}
        >
          {/* Built-in Models */}
          <div className="p-2">
            <div
              className="text-xs font-medium uppercase tracking-wider px-2 py-1 mb-1"
              style={{ color: 'var(--text-muted)' }}
            >
              内置模型
            </div>
            {builtInModels.map((model) => (
              <button
                key={model.name}
                className="flex items-center justify-between w-full px-2 py-1.5 rounded text-sm transition-colors"
                style={{
                  backgroundColor:
                    currentModel === model.name ? 'var(--bg-active)' : 'transparent',
                  color: currentModel === model.name ? 'var(--accent)' : 'var(--text-primary)',
                }}
                onClick={() => handleSelectModel(model.name)}
              >
                <span className="truncate">{model.name}</span>
                {currentModel === model.name && <Check size={14} />}
              </button>
            ))}
          </div>

          {/* Custom Models */}
          {customModels.length > 0 && (
            <div className="p-2 border-t" style={{ borderColor: 'var(--border)' }}>
              <div
                className="text-xs font-medium uppercase tracking-wider px-2 py-1 mb-1"
                style={{ color: 'var(--text-muted)' }}
              >
                自定义模型
              </div>
              {customModels.map((model) => (
                <div
                  key={model.name}
                  className="flex items-center justify-between w-full px-2 py-1.5 rounded text-sm transition-colors group"
                  style={{
                    backgroundColor:
                      currentModel === model.name ? 'var(--bg-active)' : 'transparent',
                    color: currentModel === model.name ? 'var(--accent)' : 'var(--text-primary)',
                  }}
                >
                  <button
                    className="flex-1 text-left truncate"
                    onClick={() => handleSelectModel(model.name)}
                  >
                    {currentModel === model.name && '✓ '}{model.name}
                  </button>
                  <button
                    className="icon-btn shrink-0 opacity-0 group-hover:opacity-100"
                    style={{ width: '20px', height: '20px' }}
                    onClick={(e) => handleDeleteModel(model, e)}
                    title="删除模型"
                  >
                    <Trash2 size={12} style={{ color: 'var(--danger)' }} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add Custom Model */}
          <div className="border-t" style={{ borderColor: 'var(--border)' }}>
            {showAddForm ? (
              <div className="p-3 space-y-2 animate-slide-down">
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>
                    模型名称
                  </label>
                  <input
                    type="text"
                    className="input-field text-sm"
                    placeholder="例如：My GPT-4"
                    value={newModel.name}
                    onChange={(e) =>
                      setNewModel({ ...newModel, name: e.target.value })
                    }
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>
                    模型标识 (model_name)
                  </label>
                  <input
                    type="text"
                    className="input-field text-sm"
                    placeholder="例如：gpt-4-turbo"
                    value={newModel.modelName}
                    onChange={(e) =>
                      setNewModel({ ...newModel, modelName: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>
                    API URL
                  </label>
                  <input
                    type="text"
                    className="input-field text-sm"
                    placeholder="https://api.openai.com/v1"
                    value={newModel.apiBase}
                    onChange={(e) =>
                      setNewModel({ ...newModel, apiBase: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="text-xs font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>
                    API Token
                  </label>
                  <input
                    type="password"
                    className="input-field text-sm"
                    placeholder="sk-..."
                    value={newModel.apiKey}
                    onChange={(e) =>
                      setNewModel({ ...newModel, apiKey: e.target.value })
                    }
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn btn-primary flex-1 text-xs"
                    onClick={handleAddModel}
                    disabled={!newModel.name.trim() || !newModel.apiBase.trim() || isSaving}
                    style={{
                      opacity:
                        newModel.name.trim() && newModel.apiBase.trim() && !isSaving ? 1 : 0.5,
                    }}
                  >
                    {isSaving ? '保存中...' : '保存'}
                  </button>
                  <button
                    className="btn btn-secondary text-xs"
                    onClick={() => setShowAddForm(false)}
                  >
                    取消
                  </button>
                </div>
                {saveStatus && (
                  <div
                    className="text-xs px-2 py-1.5 rounded"
                    style={{
                      color: saveStatus.type === 'success' ? '#166534' : '#991b1b',
                      backgroundColor: saveStatus.type === 'success' ? '#f0fdf4' : '#fef2f2',
                    }}
                  >
                    {saveStatus.message}
                  </div>
                )}
              </div>
            ) : (
              <button
                className="flex items-center gap-2 w-full px-3 py-2 text-sm transition-colors"
                style={{ color: 'var(--text-secondary)' }}
                onClick={() => setShowAddForm(true)}
              >
                <Plus size={14} style={{ color: 'var(--accent)' }} />
                添加自定义模型
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
