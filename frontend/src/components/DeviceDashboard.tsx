import { useEffect, useRef, useState, useCallback } from 'react'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { Activity, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

// 注册 ECharts 按需模块
echarts.use([BarChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

interface DeviceData {
  id: string
  name: string
  type: string
  line: string
  status: '运行' | '告警' | '待机'
  temperature: number
  temperature_field: string
  power: number
}

const TEMP_FIELD_NAMES: Record<string, string> = {
  spindle_temp: '主轴温度',
  mold_temp: '模具温度',
  motor_temp: '电机温度',
  temperature: '环境温度',
}

export function DeviceDashboard() {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)
  const [devices, setDevices] = useState<DeviceData[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchDevices = useCallback(async () => {
    try {
      const res = await fetch('/api/equipment/status')
      if (!res.ok) throw new Error('获取设备状态失败')
      const data = await res.json()
      setDevices(data.devices || [])
      setLastUpdated(new Date())
    } catch (e) {
      console.error('获取设备状态失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDevices()
    // 每30秒轮询更新
    const interval = setInterval(fetchDevices, 30000)
    return () => clearInterval(interval)
  }, [fetchDevices])

  useEffect(() => {
    if (!chartRef.current || devices.length === 0) return

    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)
    }

    const option: any = {
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = params[0]
          const device = devices[p.dataIndex]
          const fieldName = TEMP_FIELD_NAMES[device?.temperature_field] || '温度'
          return `${device?.id || p.name}<br/>${fieldName}: ${p.value}°C`
        },
      },
      xAxis: {
        type: 'category',
        data: devices.map(d => d.id),
        axisLabel: { fontSize: 10, color: '#666' },
      },
      yAxis: {
        type: 'value',
        name: '温度 (°C)',
        nameTextStyle: { fontSize: 10, color: '#999' },
        axisLabel: { fontSize: 10, color: '#666' },
      },
      series: [
        {
          name: '温度',
          type: 'bar',
          data: devices.map(d => ({
            value: d.temperature,
            itemStyle: {
              color: d.status === '告警' ? '#ef4444' : d.status === '运行' ? '#3b82f6' : '#9ca3af',
              borderRadius: [4, 4, 0, 0],
            },
          })),
          barWidth: '50%',
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: '#ef4444', type: 'dashed', width: 1 },
            data: [{ yAxis: 65, label: { formatter: '告警阈值 65°C', fontSize: 10, color: '#ef4444' } }],
          },
        },
      ],
    }

    chartInstance.current.setOption(option, true)

    const handleResize = () => chartInstance.current?.resize()
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
    }
  }, [devices])

  useEffect(() => {
    return () => {
      chartInstance.current?.dispose()
      chartInstance.current = null
    }
  }, [])

  const runningCount = devices.filter(d => d.status === '运行').length
  const alarmCount = devices.filter(d => d.status === '告警').length

  return (
    <div className="flex flex-col gap-4">
      {/* 状态统计卡片 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-green-100">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </div>
          <div>
            <div className="text-lg font-semibold text-gray-800">{runningCount}</div>
            <div className="text-xs text-gray-500">运行中</div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-100">
            <AlertTriangle className="h-4 w-4 text-red-600" />
          </div>
          <div>
            <div className="text-lg font-semibold text-gray-800">{alarmCount}</div>
            <div className="text-xs text-gray-500">告警</div>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
            <Activity className="h-4 w-4 text-blue-600" />
          </div>
          <div>
            <div className="text-lg font-semibold text-gray-800">{devices.length}</div>
            <div className="text-xs text-gray-500">设备总数</div>
          </div>
        </div>
      </div>

      {/* 温度图表 */}
      <div className="rounded-lg border border-gray-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700">设备温度监控</h3>
          <button
            onClick={fetchDevices}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-500"
          >
            <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
            刷新
          </button>
        </div>
        <div ref={chartRef} className="h-48 w-full" />
        {lastUpdated && (
          <p className="mt-1 text-right text-xs text-gray-400">
            更新于 {lastUpdated.toLocaleTimeString('zh-CN')}
          </p>
        )}
      </div>

      {/* 设备列表 */}
      <div className="rounded-lg border border-gray-200 bg-white p-3">
        <h3 className="mb-2 text-sm font-medium text-gray-700">设备列表</h3>
        <div className="flex flex-col gap-1.5">
          {devices.map(d => (
            <div key={d.id} className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs hover:bg-gray-50">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'h-2 w-2 rounded-full',
                  d.status === '告警' ? 'bg-red-500' : d.status === '运行' ? 'bg-green-500' : 'bg-gray-400'
                )} />
                <span className="font-medium text-gray-700">{d.id}</span>
                <span className="text-gray-400">{d.name}</span>
              </div>
              <div className="flex items-center gap-3 text-gray-500">
                <span>{d.temperature.toFixed(1)}°C</span>
                <span>{d.power.toFixed(1)}kW</span>
                <span className={cn(
                  'rounded px-1.5 py-0.5',
                  d.status === '告警' ? 'bg-red-100 text-red-600' :
                  d.status === '运行' ? 'bg-green-100 text-green-600' :
                  'bg-gray-100 text-gray-600'
                )}>{d.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
