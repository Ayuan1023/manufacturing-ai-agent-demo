export interface ToolCall {
  tool_call_id?: string
  tool: string
  display: string
  status: 'calling' | 'completed' | 'error'
  args?: Record<string, any>
  summary?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCall[]
  timestamp: number
  streaming?: boolean
  thinking?: boolean
}

export interface DeviceInfo {
  id: string
  name: string
  type: string
  line: string
  status: '运行' | '告警' | '待机'
}

export interface SSEEvent {
  type: 'start' | 'tool_call' | 'tool_result' | 'token' | 'done' | 'error' | 'thinking'
  data: any
}
