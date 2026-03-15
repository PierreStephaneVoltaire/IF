import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { useDiaryStore } from '../store/diaryStore'
import { formatDate } from '../utils/formatters'
import type { DiarySignal } from '@diary-portal/types'

// Get line color based on score
function getLineColor(score: number): string {
  if (score >= 7) return '#22c55e' // green-500
  if (score >= 5) return '#eab308' // yellow-500
  return '#ef4444' // red-500
}

// Prepare chart data from signals
function prepareChartData(signals: DiarySignal[]) {
  return signals.map((signal) => ({
    date: formatDate(signal.computed_at),
    score: signal.score,
    trend: signal.trend,
    themes: signal.themes,
    life_load: signal.life_load,
    social_battery: signal.social_battery,
    note: signal.note,
    lineColor: getLineColor(signal.score),
  }))
}

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{
    payload: {
      date: string
      score: number
      trend: string
      themes: string[]
      life_load: string
      social_battery: string
      note: string
    }
  }>
}) {
  if (!active || !payload?.length) return null

  const data = payload[0].payload

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg max-w-xs">
      <div className="text-gray-400 text-xs mb-2">{data.date}</div>
      <div className="text-xl font-bold mb-2">{data.score.toFixed(1)}</div>
      <div className="space-y-1 text-sm">
        <div className="text-gray-400">
          Trend: <span className="text-gray-200">{data.trend.replace(/_/g, ' ')}</span>
        </div>
        {data.themes.length > 0 && (
          <div className="text-gray-400">
            Themes: <span className="text-gray-200">{data.themes.join(', ')}</span>
          </div>
        )}
        <div className="text-gray-400">
          Life Load: <span className="text-gray-200">{data.life_load}</span>
        </div>
        <div className="text-gray-400">
          Social: <span className="text-gray-200">{data.social_battery}</span>
        </div>
        {data.note && (
          <div className="text-gray-400 italic mt-2 pt-2 border-t border-gray-700">
            "{data.note}"
          </div>
        )}
      </div>
    </div>
  )
}

export function ScoreChart() {
  const { signalHistory, loading } = useDiaryStore()

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 animate-pulse">
        <div className="h-64 bg-gray-800 rounded"></div>
      </div>
    )
  }

  if (signalHistory.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 text-center">
        <p className="text-gray-500">
          No signals yet. Write your first entry and the agent will process it
          during the next heartbeat.
        </p>
      </div>
    )
  }

  const chartData = prepareChartData(signalHistory)

  // Calculate average score for color
  const avgScore =
    chartData.reduce((sum, d) => sum + d.score, 0) / chartData.length

  return (
    <div className="bg-gray-900 rounded-lg p-6">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="date"
            stroke="#6b7280"
            tick={{ fill: '#6b7280', fontSize: 12 }}
            tickLine={{ stroke: '#6b7280' }}
          />
          <YAxis
            domain={[0, 10]}
            stroke="#6b7280"
            tick={{ fill: '#6b7280', fontSize: 12 }}
            tickLine={{ stroke: '#6b7280' }}
          />
          <Tooltip content={<CustomTooltip />} />

          {/* Reference bands at 3 and 7 */}
          <ReferenceLine y={7} stroke="#22c55e" strokeDasharray="5 5" strokeOpacity={0.3} />
          <ReferenceLine y={3} stroke="#ef4444" strokeDasharray="5 5" strokeOpacity={0.3} />

          <Line
            type="monotone"
            dataKey="score"
            stroke={getLineColor(avgScore)}
            strokeWidth={2}
            dot={{ fill: getLineColor(avgScore), strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: getLineColor(avgScore) }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex justify-center gap-6 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-green-500"></div>
          <span>Good (7+)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-yellow-500"></div>
          <span>Moderate (5-7)</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-red-500"></div>
          <span>Low (&lt;5)</span>
        </div>
      </div>
    </div>
  )
}
