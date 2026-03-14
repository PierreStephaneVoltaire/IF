import { useDiaryStore } from '../store/diaryStore'
import {
  formatDate,
  formatTrend,
  getTrendArrow,
  getTrendColor,
  getScoreColor,
  getScoreBgColor,
} from '../utils/formatters'

export function SignalHistoryTable() {
  const { signalHistory, loading } = useDiaryStore()

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 animate-pulse">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-gray-800 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (signalHistory.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 text-center">
        <p className="text-gray-500">No signal history yet.</p>
      </div>
    )
  }

  // Sort by date descending for table
  const sortedHistory = [...signalHistory].sort(
    (a, b) => b.computed_at.localeCompare(a.computed_at)
  )

  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <div className="max-h-80 overflow-y-auto">
        <table className="w-full">
          <thead className="bg-gray-800 sticky top-0">
            <tr>
              <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">
                Date
              </th>
              <th className="text-center px-4 py-3 text-gray-400 text-sm font-medium">
                Score
              </th>
              <th className="text-center px-4 py-3 text-gray-400 text-sm font-medium">
                Trend
              </th>
              <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">
                Themes
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {sortedHistory.map((signal) => (
              <tr key={signal.sk} className="hover:bg-gray-800/50">
                <td className="px-4 py-3 text-gray-300 text-sm">
                  {formatDate(signal.computed_at)}
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-block px-2 py-1 rounded text-sm font-medium ${getScoreColor(
                      signal.score
                    )} ${getScoreBgColor(signal.score)}`}
                  >
                    {signal.score.toFixed(1)}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`text-sm ${getTrendColor(signal.trend)}`}>
                    {getTrendArrow(signal.trend)} {formatTrend(signal.trend)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {signal.themes.slice(0, 3).map((theme: string, i: number) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-gray-800 text-gray-400 rounded text-xs"
                      >
                        {theme}
                      </span>
                    ))}
                    {signal.themes.length > 3 && (
                      <span className="text-gray-600 text-xs">
                        +{signal.themes.length - 3}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
