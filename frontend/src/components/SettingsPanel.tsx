import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../store/appStore'
import { apiClient } from '../api/client'
import { X, Cpu, BookOpen, Plus, Trash2, Edit3, Check, Power } from 'lucide-react'
import type { ModelConfig, DBRule } from '../types'

type Tab = 'models' | 'rules'

export default function SettingsPanel() {
  const showSettings = useAppStore((s) => s.showSettings)
  const setShowSettings = useAppStore((s) => s.setShowSettings)
  const models = useAppStore((s) => s.models)
  const upsertModel = useAppStore((s) => s.upsertModel)
  const removeModel = useAppStore((s) => s.removeModel)
  const setModels = useAppStore((s) => s.setModels)

  const [activeTab, setActiveTab] = useState<Tab>('models')
  const [rules, setRules] = useState<DBRule[]>([])
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null)
  const [editingRule, setEditingRule] = useState<DBRule | null>(null)
  const [showModelForm, setShowModelForm] = useState(false)
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // New model form
  const [modelForm, setModelForm] = useState<ModelConfig>({
    name: '', apiBase: '', apiKey: '', isBuiltIn: false, modelName: '',
  })

  // New rule form
  const [ruleForm, setRuleForm] = useState({ name: '', content: '', is_enabled: true })

  // Toast helper
  const showToast = (type: 'success' | 'error', message: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current)
    setToast({ type, message })
    toastTimer.current = setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    return () => {
      if (toastTimer.current) clearTimeout(toastTimer.current)
    }
  }, [])

  useEffect(() => {
    if (showSettings) {
      loadRules()
      loadModels()
    }
  }, [showSettings])

  const loadRules = async () => {
    try {
      const result = await apiClient.listRules()
      setRules(result.rules || [])
    } catch (err) {
      console.error('Failed to load rules:', err)
    }
  }

  const normalizeModels = (models: ModelConfig[]) => {
    const seen = new Set<string>()
    return models.filter((model) => {
      if (seen.has(model.name)) return false
      seen.add(model.name)
      return true
    })
  }

  const loadModels = async () => {
    try {
      const result = await apiClient.listModels()
      if (result.models && result.models.length > 0) {
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
      }
    } catch (err) {
      console.error('Failed to load models:', err)
    }
  }

  // ===== Model handlers =====
  const handleSaveModel = async () => {
    if (!modelForm.name.trim() || !modelForm.apiBase.trim() || isSaving) return
    setIsSaving(true)
    try {
      const result = await apiClient.createModel({
        name: modelForm.name.trim(),
        api_base: modelForm.apiBase.trim(),
        api_key: modelForm.apiKey.trim(),
        model_name: modelForm.modelName?.trim() || modelForm.name.trim(),
        is_built_in: false,
      })
      upsertModel({
        name: modelForm.name.trim(),
        apiBase: modelForm.apiBase.trim(),
        apiKey: modelForm.apiKey.trim(),
        isBuiltIn: false,
        modelName: modelForm.modelName?.trim() || modelForm.name.trim(),
        id: result.model.id,
      })
      showToast('success', `模型「${modelForm.name.trim()}」已保存到数据库`)
    } catch (err) {
      console.error('Failed to save model:', err)
      upsertModel({
        name: modelForm.name.trim(),
        apiBase: modelForm.apiBase.trim(),
        apiKey: modelForm.apiKey.trim(),
        isBuiltIn: false,
        modelName: modelForm.modelName?.trim() || modelForm.name.trim(),
      })
      showToast('error', `保存失败：${err instanceof Error ? err.message : '未知错误'}，已临时添加`)
    }
    setModelForm({ name: '', apiBase: '', apiKey: '', isBuiltIn: false, modelName: '' })
    setShowModelForm(false)
    setIsSaving(false)
  }

  const handleDeleteModel = async (model: ModelConfig) => {
    if (model.id) {
      try {
        await apiClient.deleteModel(model.id)
      } catch (err) {
        console.error('Failed to delete model:', err)
      }
    }
    removeModel(model.name)
  }

  // ===== Rule handlers =====
  const handleSaveRule = async () => {
    if (!ruleForm.name.trim() || !ruleForm.content.trim() || isSaving) return
    setIsSaving(true)
    try {
      const result = await apiClient.createRule({
        name: ruleForm.name.trim(),
        content: ruleForm.content.trim(),
        is_enabled: ruleForm.is_enabled,
      })
      setRules([...rules, result.rule])
      showToast('success', `规则「${ruleForm.name.trim()}」已保存`)
    } catch (err) {
      console.error('Failed to save rule:', err)
      showToast('error', `保存失败：${err instanceof Error ? err.message : '未知错误'}`)
    }
    setRuleForm({ name: '', content: '', is_enabled: true })
    setShowRuleForm(false)
    setIsSaving(false)
  }

  const handleUpdateRule = async (rule: DBRule) => {
    try {
      const result = await apiClient.updateRule(rule.id, {
        name: rule.name,
        content: rule.content,
        is_enabled: rule.is_enabled,
      })
      setRules(rules.map((r) => (r.id === rule.id ? result.rule : r)))
    } catch (err) {
      console.error('Failed to update rule:', err)
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    try {
      await apiClient.deleteRule(ruleId)
      setRules(rules.filter((r) => r.id !== ruleId))
    } catch (err) {
      console.error('Failed to delete rule:', err)
    }
  }

  const handleToggleRule = async (rule: DBRule) => {
    const updated = { ...rule, is_enabled: !rule.is_enabled }
    try {
      const result = await apiClient.updateRule(rule.id, {
        name: updated.name,
        content: updated.content,
        is_enabled: updated.is_enabled,
      })
      setRules(rules.map((r) => (r.id === rule.id ? result.rule : r)))
    } catch (err) {
      console.error('Failed to toggle rule:', err)
    }
  }

  if (!showSettings) return null

  const customModels = models.filter((m) => !m.isBuiltIn)

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center animate-fade-in overflow-y-auto"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', paddingTop: '5vh', paddingBottom: '5vh' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) setShowSettings(false)
      }}
    >
      <div
        className="w-full max-w-3xl rounded-xl shadow-2xl animate-slide-up flex flex-col my-auto"
        style={{
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-light)',
          maxHeight: '90vh',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b shrink-0"
          style={{ borderColor: 'var(--border-light)' }}
        >
          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
            设置
          </h3>
          <button className="icon-btn" onClick={() => setShowSettings(false)}>
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-5 pt-3 shrink-0">
          <button
            className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              color: activeTab === 'models' ? '#7c6cff' : '#666',
              backgroundColor: activeTab === 'models' ? '#f0ebff' : 'transparent',
            }}
            onClick={() => setActiveTab('models')}
          >
            <Cpu size={14} />
            模型配置
          </button>
          <button
            className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              color: activeTab === 'rules' ? '#7c6cff' : '#666',
              backgroundColor: activeTab === 'rules' ? '#f0ebff' : 'transparent',
            }}
            onClick={() => setActiveTab('rules')}
          >
            <BookOpen size={14} />
            规则配置
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* ===== Models Tab ===== */}
          {activeTab === 'models' && (
            <div>
              {/* Model List */}
              <div className="space-y-2 mb-4">
                {customModels.length === 0 ? (
                  <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
                    暂无自定义模型
                  </div>
                ) : (
                  customModels.map((model) => (
                    <div
                      key={model.name}
                      className="flex items-center gap-3 p-3 rounded-lg group"
                      style={{
                        backgroundColor: 'var(--bg-secondary)',
                        border: '1px solid var(--border-light)',
                      }}
                    >
                      <Cpu size={16} style={{ color: '#7c6cff' }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                          {model.name}
                        </div>
                        <div className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                          {model.modelName} · {model.apiBase}
                        </div>
                      </div>
                      <button
                        className="icon-btn shrink-0 opacity-0 group-hover:opacity-100"
                        style={{ width: '24px', height: '24px' }}
                        onClick={() => handleDeleteModel(model)}
                        title="删除模型"
                      >
                        <Trash2 size={14} style={{ color: '#e74c3c' }} />
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* Add Model Form */}
              {showModelForm ? (
                <div className="p-4 rounded-lg space-y-3 animate-slide-down" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-light)' }}>
                  <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>添加新模型</div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>模型名称</label>
                      <input
                        type="text"
                        className="input-field text-sm"
                        placeholder="例如：My GPT-4"
                        value={modelForm.name}
                        onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })}
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>模型标识 (model_name)</label>
                      <input
                        type="text"
                        className="input-field text-sm"
                        placeholder="例如：gpt-4-turbo"
                        value={modelForm.modelName}
                        onChange={(e) => setModelForm({ ...modelForm, modelName: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>API URL</label>
                      <input
                        type="text"
                        className="input-field text-sm"
                        placeholder="https://api.openai.com/v1"
                        value={modelForm.apiBase}
                        onChange={(e) => setModelForm({ ...modelForm, apiBase: e.target.value })}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>API Token</label>
                      <input
                        type="password"
                        className="input-field text-sm"
                        placeholder="sk-..."
                        value={modelForm.apiKey}
                        onChange={(e) => setModelForm({ ...modelForm, apiKey: e.target.value })}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-primary flex-1 text-xs"
                      onClick={handleSaveModel}
                      disabled={!modelForm.name.trim() || !modelForm.apiBase.trim() || isSaving}
                      style={{ opacity: modelForm.name.trim() && modelForm.apiBase.trim() && !isSaving ? 1 : 0.5 }}
                    >
                      {isSaving ? '保存中...' : '保存'}
                    </button>
                    <button className="btn btn-secondary text-xs" onClick={() => setShowModelForm(false)}>
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors w-full justify-center"
                  style={{
                    color: '#7c6cff',
                    border: '1px dashed #d0c8ff',
                    backgroundColor: 'transparent',
                  }}
                  onClick={() => setShowModelForm(true)}
                >
                  <Plus size={14} />
                  添加自定义模型
                </button>
              )}
            </div>
          )}

          {/* ===== Rules Tab ===== */}
          {activeTab === 'rules' && (
            <div>
              <div className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
                规则会作为系统提示词的一部分注入到 Agent 的上下文中，用于自定义 Agent 的行为。
              </div>

              {/* Rule List */}
              <div className="space-y-2 mb-4">
                {rules.length === 0 ? (
                  <div className="text-center py-8 text-sm" style={{ color: 'var(--text-muted)' }}>
                    暂无规则
                  </div>
                ) : (
                  rules.map((rule) => (
                    <div
                      key={rule.id}
                      className="p-3 rounded-lg group"
                      style={{
                        backgroundColor: 'var(--bg-secondary)',
                        border: '1px solid var(--border-light)',
                        opacity: rule.is_enabled ? 1 : 0.5,
                      }}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <BookOpen size={14} style={{ color: '#7c6cff' }} />
                        <span className="text-sm font-medium flex-1 truncate" style={{ color: 'var(--text-primary)' }}>
                          {rule.name}
                        </span>
                        <button
                          className="icon-btn shrink-0"
                          style={{ width: '24px', height: '24px' }}
                          onClick={() => handleToggleRule(rule)}
                          title={rule.is_enabled ? '禁用' : '启用'}
                        >
                          <Power size={14} style={{ color: rule.is_enabled ? '#27ae60' : '#999' }} />
                        </button>
                        <button
                          className="icon-btn shrink-0 opacity-0 group-hover:opacity-100"
                          style={{ width: '24px', height: '24px' }}
                          onClick={() => handleDeleteRule(rule.id)}
                          title="删除规则"
                        >
                          <Trash2 size={14} style={{ color: '#e74c3c' }} />
                        </button>
                      </div>
                      <div className="text-xs whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                        {rule.content}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Add Rule Form */}
              {showRuleForm ? (
                <div className="p-4 rounded-lg space-y-3 animate-slide-down" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-light)' }}>
                  <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>添加新规则</div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>规则名称</label>
                    <input
                      type="text"
                      className="input-field text-sm"
                      placeholder="例如：coding-style"
                      value={ruleForm.name}
                      onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })}
                      autoFocus
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1" style={{ color: '#888' }}>规则内容</label>
                    <textarea
                      className="input-field text-sm"
                      placeholder="输入规则内容，例如：使用 TypeScript 编写代码，遵循 ESLint 规范..."
                      value={ruleForm.content}
                      onChange={(e) => setRuleForm({ ...ruleForm, content: e.target.value })}
                      rows={5}
                      style={{ resize: 'vertical' }}
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-primary flex-1 text-xs"
                      onClick={handleSaveRule}
                      disabled={!ruleForm.name.trim() || !ruleForm.content.trim() || isSaving}
                      style={{ opacity: ruleForm.name.trim() && ruleForm.content.trim() && !isSaving ? 1 : 0.5 }}
                    >
                      {isSaving ? '保存中...' : '保存'}
                    </button>
                    <button className="btn btn-secondary text-xs" onClick={() => setShowRuleForm(false)}>
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className="flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors w-full justify-center"
                  style={{
                    color: '#7c6cff',
                    border: '1px dashed #d0c8ff',
                    backgroundColor: 'transparent',
                  }}
                  onClick={() => setShowRuleForm(true)}
                >
                  <Plus size={14} />
                  添加规则
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-5 py-3 border-t shrink-0"
          style={{ borderColor: 'var(--border-light)' }}
        >
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            设置保存在本地 SQLite 数据库中
          </div>
          <button className="btn btn-primary text-sm" onClick={() => setShowSettings(false)}>
            完成
          </button>
        </div>
      </div>

      {/* Toast Notification */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 z-[60] animate-slide-up flex items-center gap-2.5 px-4 py-3 rounded-lg shadow-lg"
          style={{
            backgroundColor: toast.type === 'success' ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${toast.type === 'success' ? '#86efac' : '#fca5a5'}`,
            color: toast.type === 'success' ? '#166534' : '#991b1b',
          }}
        >
          {toast.type === 'success' ? (
            <Check size={16} style={{ color: '#22c55e' }} />
          ) : (
            <X size={16} style={{ color: '#ef4444' }} />
          )}
          <span className="text-sm font-medium">{toast.message}</span>
        </div>
      )}
    </div>
  )
}
