import { Loader2, CheckCircle2, AlertCircle, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ToolCall } from '@/types'

interface ToolCallCardProps {
  toolCall: ToolCall
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const isCalling = toolCall.status === 'calling'
  const isError = toolCall.status === 'error'

  return (
    <div className={cn(
      'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm',
      isCalling ? 'border-blue-200 bg-blue-50' :
      isError ? 'border-red-200 bg-red-50' :
      'border-gray-200 bg-gray-50'
    )}>
      <div className={cn(
        'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
        isCalling ? 'bg-blue-100 text-blue-600' :
        isError ? 'bg-red-100 text-red-600' :
        'bg-green-100 text-green-600'
      )}>
        {isCalling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> :
         isError ? <AlertCircle className="h-3.5 w-3.5" /> :
         <CheckCircle2 className="h-3.5 w-3.5" />}
      </div>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <Wrench className="h-3.5 w-3.5 shrink-0 text-gray-400" />
        <span className="truncate font-medium text-gray-700">{toolCall.display}</span>
        <span className="shrink-0 text-xs text-gray-400">{toolCall.tool}</span>
      </div>
      {toolCall.summary && !isCalling && (
        <span className="shrink-0 text-xs text-gray-500">{toolCall.summary}</span>
      )}
      {isCalling && (
        <span className="shrink-0 text-xs text-blue-500 animate-pulse-slow">执行中...</span>
      )}
    </div>
  )
}
