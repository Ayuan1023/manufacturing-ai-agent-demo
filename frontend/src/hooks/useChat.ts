import { useState, useRef, useCallback } from 'react'
import type { ChatMessage, ToolCall } from '@/types'
import { generateId } from '@/lib/utils'

const API_BASE = '/api'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    // 添加 AI 消息占位
    const aiMsg: ChatMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      toolCalls: [],
      timestamp: Date.now(),
      streaming: true,
    }

    setMessages(prev => [...prev, userMsg, aiMsg])
    setIsLoading(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, session_id: sessionId || undefined }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '请求失败' }))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentToolCalls: ToolCall[] = []

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        let currentData = ''

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            currentData = line.slice(5).trim()
          } else if (line === '' && currentEvent && currentData) {
            // 处理完整事件
            try {
              const data = JSON.parse(currentData)

              if (currentEvent === 'start') {
                if (data.session_id && !sessionId) {
                  setSessionId(data.session_id)
                }
              } else if (currentEvent === 'thinking') {
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, thinking: true } : m
                ))
              } else if (currentEvent === 'tool_call') {
                currentToolCalls.push({
                  tool_call_id: data.tool_call_id,
                  tool: data.tool,
                  display: data.display,
                  status: 'calling',
                  args: data.args,
                })
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, thinking: false, toolCalls: [...currentToolCalls] } : m
                ))
              } else if (currentEvent === 'tool_result') {
                // 按 tool_call_id 精确匹配，同一工具多次调用不会混淆
                const idx = currentToolCalls.findIndex(t => t.tool_call_id === data.tool_call_id)
                if (idx >= 0) {
                  currentToolCalls[idx] = { ...currentToolCalls[idx], status: 'completed', summary: data.summary }
                } else {
                  // 兼容无 tool_call_id 的旧格式，按工具名+状态匹配
                  const fallbackIdx = currentToolCalls.findIndex(t => t.tool === data.tool && t.status === 'calling')
                  if (fallbackIdx >= 0) {
                    currentToolCalls[fallbackIdx] = { ...currentToolCalls[fallbackIdx], status: 'completed', summary: data.summary }
                  }
                }
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, toolCalls: [...currentToolCalls] } : m
                ))
              } else if (currentEvent === 'token') {
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, thinking: false, content: m.content + data.content } : m
                ))
              } else if (currentEvent === 'done') {
                if (data.session_id && !sessionId) {
                  setSessionId(data.session_id)
                }
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, streaming: false, thinking: false, toolCalls: data.tool_calls || currentToolCalls } : m
                ))
              } else if (currentEvent === 'error') {
                setMessages(prev => prev.map(m =>
                  m.id === aiMsg.id ? { ...m, content: `错误: ${data.message}`, streaming: false, thinking: false } : m
                ))
              }
            } catch (e) {
              console.warn('SSE 数据解析失败:', e, '原始数据:', currentData)
            }
            currentEvent = ''
            currentData = ''
          }
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === aiMsg.id ? { ...m, content: `错误: ${error.message}`, streaming: false } : m
        ))
      }
    } finally {
      setIsLoading(false)
      abortRef.current = null
    }
  }, [isLoading, sessionId])

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort()
    setIsLoading(false)
    setMessages(prev => prev.map(m => m.streaming ? { ...m, streaming: false } : m))
  }, [])

  const clearChat = useCallback(() => {
    setMessages([])
    setSessionId('')
  }, [])

  return { messages, isLoading, sessionId, sendMessage, stopGeneration, clearChat }
}
