import { User, Bot } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/types'
import { ToolCallCard } from './ToolCallCard'

interface MessageBubbleProps {
  message: ChatMessage
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn(
      'flex gap-3 animate-fade-in',
      isUser ? 'flex-row-reverse' : 'flex-row'
    )}>
      {/* 头像 */}
      <div className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
        isUser ? 'bg-blue-600 text-white' : 'bg-gray-800 text-white'
      )}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* 消息内容 */}
      <div className={cn(
        'flex max-w-[80%] flex-col gap-2',
        isUser ? 'items-end' : 'items-start'
      )}>
        {/* 工具调用卡片 */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex w-full flex-col gap-1.5">
            {message.toolCalls.map((tc, idx) => (
              <ToolCallCard key={idx} toolCall={tc} />
            ))}
          </div>
        )}

        {/* 文本内容 */}
        {message.content && (
          <div className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'rounded-tr-sm bg-blue-600 text-white'
              : 'rounded-tl-sm bg-gray-100 text-gray-800'
          )}>
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.streaming && (
              <span className="ml-1 inline-block h-4 w-1.5 animate-pulse bg-gray-400 align-middle" />
            )}
          </div>
        )}

        {/* 思考中状态 */}
        {message.thinking && !message.content && (
          <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2.5 text-sm text-gray-500">
            <span className="flex gap-1">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '300ms' }} />
            </span>
            <span>正在思考...</span>
          </div>
        )}

        {/* 时间戳 */}
        <span className="text-xs text-gray-400">
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  )
}
