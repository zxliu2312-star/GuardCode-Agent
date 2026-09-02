import type { ServerEvent, Plan } from '../types'
import { useAppStore, genId } from '../store/appStore'
import { getWebSocketUrl, apiClient } from '../api/client'

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private currentSessionId: string | null = null
  private isManuallyClosed = false

  private saveToDB(msg: any) {
    const taskId = useAppStore.getState().currentTaskId
    if (!taskId) return
    const metadata: Record<string, any> = {}
    if (msg.model) metadata.model = msg.model
    if (msg.tool) metadata.tool = msg.tool
    if (msg.args) metadata.args = msg.args
    if (msg.result !== undefined) metadata.result = msg.result
    if (msg.success !== undefined) metadata.success = msg.success
    if (msg.error) metadata.error = msg.error
    if (msg.status) metadata.status = msg.status
    if (msg.riskLevel) metadata.riskLevel = msg.riskLevel
    if (msg.level) metadata.level = msg.level

    apiClient.saveMessage(taskId, {
      id: msg.id,
      type: msg.type,
      content: msg.content,
      timestamp: msg.timestamp,
      metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
    }).catch(err => console.error('[WS] Failed to save message to DB:', err))
  }

  private updateTaskStatus(status: string, lastMessage?: string) {
    const state = useAppStore.getState()
    const taskId = state.currentTaskId
    if (!taskId) return
    state.updateTaskStatus(taskId, status as any)
    apiClient.updateTaskStatus(taskId, status, lastMessage).catch(err =>
      console.error('[WS] Failed to update task status:', err)
    )
  }

  connect(sessionId: string) {
    if (this.currentSessionId === sessionId && this.ws?.readyState === WebSocket.OPEN) {
      console.log('[WS] Already connected to session:', sessionId)
      return
    }

    this.currentSessionId = sessionId
    this.isManuallyClosed = false

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.onopen = null
      this.ws.onmessage = null
      this.ws.onerror = null
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }

    const url = getWebSocketUrl(sessionId)
    console.log('[WS] Connecting to:', url)

    try {
      this.ws = new WebSocket(url)
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err)
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      console.log('[WS] Connected successfully')
      this.reconnectAttempts = 0
      useAppStore.getState().setWsConnected(true)
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ServerEvent
        this.handleEvent(data)
      } catch (err) {
        console.error('[WS] Failed to parse message:', err, event.data)
      }
    }

    this.ws.onerror = (event) => {
      console.error('[WS] Error:', event)
    }

    this.ws.onclose = (event) => {
      console.log('[WS] Disconnected. Code:', event.code, 'Reason:', event.reason)
      useAppStore.getState().setWsConnected(false)
      this.ws = null

      // 4004 = Session not found, don't retry (historical tasks)
      if (event.code === 4004) {
        console.log('[WS] Session not found, not retrying')
        return
      }

      if (!this.isManuallyClosed && this.currentSessionId && this.reconnectAttempts < 10) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000)
    this.reconnectAttempts++
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    this.reconnectTimer = setTimeout(() => {
      if (this.currentSessionId && !this.isManuallyClosed) {
        this.connect(this.currentSessionId)
      }
    }, delay)
  }

  disconnect() {
    this.isManuallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    useAppStore.getState().setWsConnected(false)
  }

  private handleEvent(event: ServerEvent) {
    const state = useAppStore.getState()
    const { type } = event
    const data = event as any
    const message = data.message

    switch (type) {
      case 'tool_call': {
        const tool = data.tool || 'unknown'
        const args = data.args || {}
        const riskLevel = data.risk_level || 'safe'
        const toolMsg = {
          id: genId(),
          type: 'tool_call' as const,
          tool,
          args,
          status: 'running' as const,
          riskLevel,
          timestamp: Date.now(),
        }
        state.addMessage(toolMsg)
        this.saveToDB(toolMsg)
        break
      }

      case 'tool_result': {
        const tool = data.tool || 'unknown'
        const resultObj = data.result
        const result = resultObj?.result ?? data.result
        const success = resultObj?.success ?? true
        const error = resultObj?.error

        const resultMsg = {
          id: genId(),
          type: 'tool_result' as const,
          tool,
          result,
          success,
          error,
          timestamp: Date.now(),
        }
        state.addMessage(resultMsg)
        this.saveToDB(resultMsg)

        if (tool === 'run_command' || tool === 'execute_command') {
          const resultData = result as Record<string, unknown> | undefined
          const stdout = (resultData?.stdout as string) || ''
          const stderr = (resultData?.stderr as string) || ''
          const exitCode = (resultData?.exit_code as number) ?? 0
          const command = data.command || (data.args && data.args.command) || ''
          state.addTerminalOutput({
            id: genId(),
            command,
            stdout,
            stderr,
            exitCode,
            timestamp: Date.now(),
          })
        }
        break
      }

      case 'confirm_request': {
        state.setPendingConfirm({
          request_id: data.request_id || genId(),
          tool: data.tool || '',
          args: data.args || {},
          message: message || '请确认是否执行此操作',
          riskLevel: data.risk_level || 'moderate',
        })
        break
      }

      case 'feedback_request': {
        state.setPendingFeedback({
          request_id: data.request_id || genId(),
          tool: data.tool || '',
          args: data.args || {},
          message: message || '请提供反馈',
        })
        break
      }

      case 'plan_created': {
        const plan = data.plan as Plan | null
        if (plan) {
          state.setPendingPlan(plan)
        }
        break
      }

      case 'mode_changed': {
        const mode = data.mode as 'PLAN' | 'WORK' | 'FEEDBACK' | 'RESEARCH'
        if (mode) {
          state.setMode(mode)
        }
        break
      }

      case 'context_compress': {
        const compressMsg = {
          id: genId(),
          type: 'system' as const,
          content: '上下文已压缩，以节省 token 使用',
          level: 'info' as const,
          timestamp: Date.now(),
        }
        state.addMessage(compressMsg)
        this.saveToDB(compressMsg)
        break
      }

      case 'model_call': {
        break
      }

      case 'llm_start': {
        const model = data.model || 'unknown'
        const assistantMsg = {
          id: genId(),
          type: 'assistant' as const,
          content: '',
          model,
          timestamp: Date.now(),
        }
        state.addMessage(assistantMsg)
        // Don't save yet - content is empty, will be saved on llm_done
        break
      }

      case 'llm_chunk': {
        const content = data.content || ''
        const messages = state.chat.messages
        const lastAssistant = [...messages].reverse().find((m) => m.type === 'assistant')
        if (lastAssistant) {
          state.appendToMessage(lastAssistant.id, content)
        }
        break
      }

      case 'llm_done': {
        const content = data.content || ''
        const toolCalls = data.tool_calls || []
        if (!content && toolCalls.length > 0) {
          const messages = state.chat.messages
          const lastAssistant = [...messages].reverse().find((m) => m.type === 'assistant' && !m.content)
          if (lastAssistant) {
            state.updateMessage(lastAssistant.id, { content: '正在执行工具...' })
          }
        }
        // Save the final assistant message to DB
        {
          const messages = state.chat.messages
          const lastAssistant = [...messages].reverse().find((m) => m.type === 'assistant')
          if (lastAssistant && lastAssistant.content) {
            this.saveToDB(lastAssistant)
          }
        }
        break
      }

      case 'info': {
        const infoMsg = {
          id: genId(),
          type: 'system' as const,
          content: message || '',
          level: 'info' as const,
          timestamp: Date.now(),
        }
        state.addMessage(infoMsg)
        this.saveToDB(infoMsg)
        break
      }

      case 'risk_warning': {
        const warnMsg = {
          id: genId(),
          type: 'system' as const,
          content: message || '检测到风险操作',
          level: 'warning' as const,
          timestamp: Date.now(),
        }
        state.addMessage(warnMsg)
        this.saveToDB(warnMsg)
        break
      }

      case 'done': {
        state.setRunning(false)
        state.setTaskStartedAt(null)
        this.updateTaskStatus('completed', data.content || message)
        const doneContent = data.content || message
        if (doneContent) {
          const currentMessages = state.chat.messages
          const lastMsg = currentMessages[currentMessages.length - 1]
          if (lastMsg && lastMsg.type === 'assistant' && lastMsg.content) {
            break
          }
        }
        const doneMsg = {
          id: genId(),
          type: 'system' as const,
          content: doneContent || '任务已完成',
          level: 'info' as const,
          timestamp: Date.now(),
        }
        state.addMessage(doneMsg)
        this.saveToDB(doneMsg)
        break
      }

      case 'stopped': {
        state.setRunning(false)
        state.setTaskStartedAt(null)
        this.updateTaskStatus('stopped', message)
        const stoppedMsg = {
          id: genId(),
          type: 'system' as const,
          content: message || '任务已停止',
          level: 'warning' as const,
          timestamp: Date.now(),
        }
        state.addMessage(stoppedMsg)
        this.saveToDB(stoppedMsg)
        break
      }

      case 'blocked': {
        state.setRunning(false)
        this.updateTaskStatus('failed', message)
        const blockedMsg = {
          id: genId(),
          type: 'system' as const,
          content: message || '任务被阻塞',
          level: 'warning' as const,
          timestamp: Date.now(),
        }
        state.addMessage(blockedMsg)
        this.saveToDB(blockedMsg)
        break
      }

      case 'error': {
        state.setRunning(false)
        state.setTaskStartedAt(null)
        this.updateTaskStatus('failed', message)
        const errorMsg = {
          id: genId(),
          type: 'system' as const,
          content: message || '发生错误',
          level: 'error' as const,
          timestamp: Date.now(),
        }
        state.addMessage(errorMsg)
        this.saveToDB(errorMsg)
        break
      }

      default: {
        console.warn('[WS] Unknown event type:', type, event)
      }
    }
  }

  sendRaw(data: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
      return true
    }
    console.warn('[WS] Cannot send, connection not open. ReadyState:', this.ws?.readyState)
    return false
  }

  sendStart(task: string, model?: string, apiBase?: string, apiKey?: string): boolean {
    return this.sendRaw({
      type: 'start',
      task,
      model,
      api_base: apiBase,
      api_key: apiKey,
    })
  }

  sendConfirm(requestId: string, approved: boolean, whitelist: boolean = false): boolean {
    return this.sendRaw({
      type: 'confirm_response',
      request_id: requestId,
      approved: approved,
      whitelist: whitelist,
    })
  }

  sendPlanApproved(plan: Plan): boolean {
    return this.sendRaw({
      type: 'plan_approved',
      plan,
    })
  }

  sendPlanRejected(feedback: string): boolean {
    return this.sendRaw({
      type: 'plan_rejected',
      feedback,
    })
  }

  sendFeedback(requestId: string, action: 'continue' | 'adjust' | 'stop', feedback?: string): boolean {
    return this.sendRaw({
      type: 'feedback_response',
      request_id: requestId,
      action,
      feedback,
    })
  }

  sendStop(): boolean {
    return this.sendRaw({
      type: 'stop',
    })
  }
}

export const wsService = new WebSocketService()
