import { ChatPanel } from '@/components/ChatPanel'
import { DeviceDashboard } from '@/components/DeviceDashboard'

function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-50">
      {/* 左侧聊天面板 */}
      <div className="flex flex-1 flex-col border-r border-gray-200 bg-white">
        <ChatPanel />
      </div>

      {/* 右侧设备监控面板 */}
      <div className="hidden w-80 flex-col overflow-y-auto bg-gray-50 p-4 lg:flex">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-gray-700">设备监控</h2>
          <p className="text-xs text-gray-400">实时设备状态与温度监控</p>
        </div>
        <DeviceDashboard />
      </div>
    </div>
  )
}

export default App
