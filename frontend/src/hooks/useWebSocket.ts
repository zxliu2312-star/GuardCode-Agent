import { useEffect, useRef, useCallback, useState } from 'react'
import { useAppStore, genId } from '../store/appStore'
import { getWebSocketUrl, apiClient } from '../api/client'
import type { ServerEvent, Plan } from '../types'

// ===== WebSocket Hook =====

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const [isConnected, setIsConnected] = useState(false)

  const session = useAppStore((s) => s.session)
  const addMessage = useAppStore((s) => s.addMessage)
  const updateMessage = useAppStore((s) => s.updateMessage)
  const appendToMessage = useAppStore((s) => s.appendToMessage)
  const setRunning = useAppStore((s) => s.setRunning)
  const setTaskStartedAt = useAppStore((s) => s.setTaskStartedAt)
  const setMode = useAppStore((s) => s.setMode)
  const setPendingConfirm = useAppStore((s) => s.setPendingConfirm)
  const setPendingFeedback = useAppStore((s) => s.setPendingFeedback)
  const setPendingPlan = useAppStore((s) => s.setPendingPlan)
  const addTerminalOutput = useAppStore((s) => s.addTerminalOutput)

  // Helper: 保存消息到数据库
  const saveMessageToDB = useCallback(async (message: any) => {
    if (!session.sessionId) return
    try {
      // 只保存主要消息类型，不保存临时状态消息
      if (['user', 'assistant', 'tool_call', 'tool_result'].includes(message.type)) {
        await apiClient.saveMessage(session.sessionId, {
          id: message.id,
          type: message.type,
          content: message.content,
          timestamp: message.timestamp,
          metadata: message.type === 'tool_call' || message.type === 'tool_result' 
            ? { tool: message.tool, args: message.args, result: message.result, status: message.status, error: message.error }
            : message.model ? { model: message.model } : undefined,
        })
      }
    } catch (err) {
      console.error('Failed to save message to DB:', err)
    }
  }, [session.sessionId])

  // ===== Handle incoming server events =====
  const handleEvent = useCallback(
    (event: any) => {
      const { type } = event
      // Server sends fields at top level (not nested in data)
      const data = event
      const message = event.message

      switch (type) {
        case 'tool_call': {
          const tool = (data.tool as string) || 'unknown'
          const args = (data.args as Record<string, unknown>) || {}
          const riskLevel = (data.risk_level as 'safe' | 'moderate' | 'dangerous') || 'safe'
          const msg = {
            id: genId(),
            type: 'tool_call' as const,
            tool,
            args,
            status: 'running' as const,
            riskLevel,
            timestamp: Date.now(),
          }
          addMessage(msg)
          saveMessageToDB(msg)
          break
        }

        case 'tool_result': {
          const tool = (data.tool as string) || 'unknown'
          const resultObj = data.result as Record<string, unknown> | undefined
          const result = resultObj?.result ?? data.result
          const success = (resultObj?.success as boolean) ?? true
          const error = resultObj?.error as string | undefined

          const msg = {
            id: genId(),
            type: 'tool_result' as const,
            tool,
            result,
            success,
            error,
            timestamp: Date.now(),
          }
          addMessage(msg)
          saveMessageToDB(msg)

          // If it's a run_command result, add to terminal
          if (tool === 'run_command' || tool === 'execute_command') {
            const resultData = result as Record<string, unknown> | undefined
            const stdout = (resultData?.stdout as string) || ''
            const stderr = (resultData?.stderr as string) || ''
            const exitCode = (resultData?.exit_code as number) ?? 0
            const command = (data.command as string) || (data.args && (data.args as Record<string, unknown>).command as string) || ''
            addTerminalOutput({
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
          setPendingConfirm({
            request_id: (data.request_id as string) || genId(),
            tool: (data.tool as string) || '',
            args: (data.args as Record<string, unknown>) || {},
            message: message || '请确认是否执行此操作',
            riskLevel: (data.risk_level as 'safe' | 'moderate' | 'dangerous') || 'moderate',
          })
          break
        }

        case 'feedback_request': {
          setPendingFeedback({
            request_id: (data.request_id as string) || genId(),
            tool: (data.tool as string) || '',
            args: (data.args as Record<string, unknown>) || {},
            message: message || '请提供反馈',
          })
          break
        }

        case 'plan_created': {
          const plan = (data.plan as Plan) || null
          if (plan) {
            setPendingPlan(plan)
          }
          break
        }

        case 'plan_step_completed': {
          // Could update plan step status here
          const stepId = data.step_id as string
          const status = data.status as string
          console.log(`Plan step ${stepId} ${status}`)
          break
        }

        case 'mode_changed': {
          const mode = data.mode as 'PLAN' | 'WORK' | 'FEEDBACK' | 'RESEARCH'
          if (mode) {
            setMode(mode)
          }
          break
        }

        case 'context_compress': {
          addMessage({
            id: genId(),
            type: 'system',
            content: '上下文已压缩，以节省 token 使用',
            level: 'info',
            timestamp: Date.now(),
          })
          break
        }

        case 'model_call': {
          // Model is being called — don't create a new assistant message here.
          // The llm_start event (from streaming model call) will create the
          // assistant message for typewriter mode. This event is just informational.
          break
        }

        case 'llm_start': {
          // LLM 开始生成 — 创建空的 assistant 消息（打字机模式）
          const model = (data.model as string) || 'unknown'
          const msg = {
            id: genId(),
            type: 'assistant' as const,
            content: '',
            model,
            timestamp: Date.now(),
          }
          addMessage(msg)
          // 注意：暂时不保存空消息，等内容完整后再保存
          break
        }

        case 'llm_chunk': {
          // LLM 流式输出片段 — 追加到最近的 assistant 消息
          const content = (data.content as string) || ''
          // 获取最后一条 assistant 消息并追加内容
          const messages = useAppStore.getState().chat.messages
          const lastAssistant = [...messages].reverse().find((m) => m.type === 'assistant')
          if (lastAssistant) {
            appendToMessage(lastAssistant.id, content)
          }
          break
        }

        case 'llm_done': {
          // LLM 生成完成 - 保存完整的 assistant 消息
          const content = (data.content as string) || ''
          const toolCalls = (data.tool_calls as unknown[]) || []
          
          // 获取最后一条 assistant 消息
          const messages = useAppStore.getState().chat.messages
          const lastAssistant = [...messages].reverse().find((m) => m.type === 'assistant')
          
          if (lastAssistant && lastAssistant.content) {
            // 保存完整的消息到数据库
            saveMessageToDB(lastAssistant)
          }
          
          // 如果内容为空但有 tool_calls，说明模型直接调用了工具
          if (!content && toolCalls.length > 0 && lastAssistant) {
            // 移除空的 assistant 消息
            if (!lastAssistant.content) {
              updateMessage(lastAssistant.id, { content: '正在执行工具...' })
            }
          }
          break
        }

        case 'info': {
          addMessage({
            id: genId(),
            type: 'system',
            content: message || '',
            level: 'info',
            timestamp: Date.now(),
          })
          break
        }

        case 'risk_warning': {
          addMessage({
            id: genId(),
            type: 'system',
            content: message || '检测到风险操作',
            level: 'warning',
            timestamp: Date.now(),
          })
          break
        }

        case 'done': {
          setRunning(false)
          setTaskStartedAt(null)
          // Check if there's content in the done event
          const doneContent = (data.content as string) || message
          if (doneContent) {
            // Check if the last message is an assistant message with content
            // (from streaming). If so, don't add a duplicate system message.
            const currentMessages = useAppStore.getState().chat.messages
            const lastMsg = currentMessages[currentMessages.length - 1]
            if (lastMsg && lastMsg.type === 'assistant' && lastMsg.content) {
              // Content was already streamed, don't add duplicate
              break
            }
          }
          addMessage({
            id: genId(),
            type: 'system',
            content: doneContent || '任务已完成',
            level: 'info',
            timestamp: Date.now(),
          })
          break
        }

        case 'stopped': {
          setRunning(false)
          setTaskStartedAt(null)
          addMessage({
            id: genId(),
            type: 'system',
            content: message || '任务已停止',
            level: 'warning',
            timestamp: Date.now(),
          })
          break
        }

        case 'blocked': {
          setRunning(false)
          addMessage({
            id: genId(),
            type: 'system',
            content: message || '任务被阻塞',
            level: 'warning',
            timestamp: Date.now(),
          })
          break
        }

        case 'error': {
          addMessage({
            id: genId(),
            type: 'system',
            content: message || '发生错误',
            level: 'error',
            timestamp: Date.now(),
          })
          break
        }

        default: {
          console.warn('Unknown server event type:', type, event)
        }
      }
    },
    [addMessage, updateMessage, appendToMessage, setRunning, setTaskStartedAt, setMode, setPendingConfirm, setPendingFeedback, setPendingPlan, addTerminalOutput, saveMessageToDB]
  )

  // ===== Connect WebSocket =====
  const connect = useCallback(() => {
    if (!session.sessionId) return

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const url = getWebSocketUrl(session.sessionId)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      useAppStore.getState().setWsConnected(true)
      reconnectAttemptsRef.current = 0
      console.log('[WebSocket] Connected to', url)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ServerEvent
        handleEvent(data)
      } catch (err) {
        console.error('[WebSocket] Failed to parse message:', err)
      }
    }

    ws.onerror = (err) => {
      console.error('[WebSocket] Error:', err)
    }

    ws.onclose = () => {
      setIsConnected(false)
      useAppStore.getState().setWsConnected(false)
      wsRef.current = null
      console.log('[WebSocket] Disconnected')

      // Auto-reconnect
      if (session.sessionId && reconnectAttemptsRef.current < 10) {
        const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30000)
        reconnectAttemptsRef.current++
        console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`)
        reconnectTimerRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }
  }, [session.sessionId, handleEvent])

  // ===== Connect on session change =====
  useEffect(() => {
    if (session.sessionId) {
      connect()
    }
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [session.sessionId, connect])

  // ===== Send methods =====

  const sendRaw = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
      return true
    }
    console.warn('[WebSocket] Cannot send, connection not open')
    return false
  }, [])

  const sendStart = useCallback(
    (task: string, model?: string, apiBase?: string) => {
      return sendRaw({
        type: 'start',
        task,
        model,
        api_base: apiBase,
      })
    },
    [sendRaw]
  )

  const sendConfirm = useCallback(
    (requestId: string, approved: boolean) => {
      return sendRaw({
        type: 'confirm_response',
        request_id: requestId,
        approved,
      })
    },
    [sendRaw]
  )

  const sendPlanApproved = useCallback(
    (plan: Plan) => {
      return sendRaw({
        type: 'plan_approved',
        plan,
      })
    },
    [sendRaw]
  )

  const sendPlanRejected = useCallback(
    (feedback: string) => {
      return sendRaw({
        type: 'plan_rejected',
        feedback,
      })
    },
    [sendRaw]
  )

  const sendFeedback = useCallback(
    (requestId: string, action: 'continue' | 'adjust' | 'stop', feedback?: string) => {
      return sendRaw({
        type: 'feedback_response',
        request_id: requestId,
        action,
        feedback,
      })
    },
    [sendRaw]
  )

  const sendStop = useCallback(() => {
    return sendRaw({
      type: 'stop',
    })
  }, [sendRaw])

  return {
    isConnected,
    sendStart,
    sendConfirm,
    sendPlanApproved,
    sendPlanRejected,
    sendFeedback,
    sendStop,
  }
}
