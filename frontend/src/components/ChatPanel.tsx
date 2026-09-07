import { useState, useRef, useEffect } from 'react'
import { Send, Square, Trash2, Sparkles } from 'lucide-react'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'

const QUICK_PROMPTS = [
  '现在有哪些设备告警？',
  'CNC-001状态怎么样？',
  '本周生产情况怎么样？',
  'WO-2026-0001的物料齐套吗？',
  '主轴过热怎么处理？',
  '帮我创建一个工单',
]

export function ChatPanel() {
  const { messages, isLoading, sendMessage, stopGeneration, clearChat } = useChat()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage(input)
    setInput('')
  }

  const handleQuickPrompt = (prompt: string) => {
    if (isLoading) return
    sendMessage(prompt)
  }

  return (
    <div className="flex h-full flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-blue-700">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-800">制造业智能运维 Agent</h1>
            <p className="text-xs text-gray-400">基于 MCP + LangGraph 的智能助手</p>
          </div>
        </div>
        <button
          onClick={clearChat}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <Trash2 className="h-3.5 w-3.5" />
          清空
        </button>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-100 to-blue-200">
              <Sparkles className="h-8 w-8 text-blue-600" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-medium text-gray-700">您好，我是制造业智能运维助手</h2>
              <p className="mt-1 text-sm text-gray-400">可以查询设备状态、生产工单、物料库存、操作规程等</p>
            </div>
            <div className="grid w-full max-w-md grid-cols-2 gap-2">
              {QUICK_PROMPTS.map(prompt => (
                <button
                  key={prompt}
                  onClick={() => handleQuickPrompt(prompt)}
                  className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-xs text-gray-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 快捷提示 */}
      <div className="flex flex-wrap gap-1.5 border-t border-gray-100 px-4 py-2">
        {QUICK_PROMPTS.map(prompt => (
          <button
            key={prompt}
            onClick={() => handleQuickPrompt(prompt)}
            disabled={isLoading}
            className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-500 transition hover:border-blue-300 hover:text-blue-600 disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* 输入框 */}
      <div className="border-t border-gray-200 p-3">
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1 rounded-xl border border-gray-300 bg-white px-3 py-2 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              placeholder="输入您的问题，按 Enter 发送..."
              rows={1}
              className="max-h-32 w-full resize-none bg-transparent text-sm text-gray-700 outline-none placeholder:text-gray-400"
            />
          </div>
          {isLoading ? (
            <button
              type="button"
              onClick={stopGeneration}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500 text-white transition hover:bg-red-600"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </form>
        <p className="mt-1.5 text-center text-xs text-gray-300">
          AI 生成内容仅供参考，关键操作请人工确认
        </p>
      </div>
    </div>
  )
}
