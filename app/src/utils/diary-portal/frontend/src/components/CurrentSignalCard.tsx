import { useDiaryStore } from '../store/diaryStore'
import {
  formatTrend,
  getTrendArrow,
  getTrendColor,
  formatScore,
  getScoreColor,
  formatLifeLoad,
  getLifeLoadColor,
  formatSocialBattery,
  getSocialBatteryColor,
  formatRelativeTime,
} from '../utils/formatters'
import { Battery, Activity, Tag } from 'lucide-react'

export function CurrentSignalCard() {
  const { currentSignal, loading } = useDiaryStore()

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 animate-pulse">
        <div className="h-8 bg-gray-800 rounded w-1/3 mb-4"></div>
        <div className="h-16 bg-gray-800 rounded w-1/2"></div>
      </div>
    )
  }

  if (!currentSignal) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 text-center">
        <p className="text-gray-500">
          No signals yet. Write your first entry and the agent will process it
          during the next heartbeat.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 rounded-lg p-6 space-y-6">
      {/* Score and Trend */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-gray-500 text-sm mb-1">Mental Health Score</div>
          <div className={`text-5xl font-bold ${getScoreColor(currentSignal.score)}`}>
            {formatScore(currentSignal.score)}
            <span className="text-gray-600 text-lg">/10</span>
          </div>
        </div>

        <div className="text-right">
          <div className="text-gray-500 text-sm mb-1">Trend</div>
          <div className={`text-xl font-medium ${getTrendColor(currentSignal.trend)}`}>
            {getTrendArrow(currentSignal.trend)} {formatTrend(currentSignal.trend)}
          </div>
        </div>
      </div>

      {/* Themes */}
      {currentSignal.themes.length > 0 && (
        <div>
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
            <Tag className="w-4 h-4" />
            Themes
          </div>
          <div className="flex flex-wrap gap-2">
            {currentSignal.themes.map((theme, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-gray-800 text-gray-300 rounded text-sm"
              >
                {theme}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Life Load and Social Battery */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Activity className="w-4 h-4" />
            Life Load
          </div>
          <div className={`font-medium ${getLifeLoadColor(currentSignal.life_load)}`}>
            {formatLifeLoad(currentSignal.life_load)}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 text-gray-500 text-sm mb-1">
            <Battery className="w-4 h-4" />
            Social Battery
          </div>
          <div className={`font-medium ${getSocialBatteryColor(currentSignal.social_battery)}`}>
            {formatSocialBattery(currentSignal.social_battery)}
          </div>
        </div>
      </div>

      {/* Agent Note */}
      {currentSignal.note && (
        <div className="pt-4 border-t border-gray-800">
          <div className="text-gray-500 text-sm mb-1">Agent Note</div>
          <p className="text-gray-300 text-sm italic">"{currentSignal.note}"</p>
        </div>
      )}

      {/* Meta */}
      <div className="flex justify-between text-xs text-gray-600">
        <span>Based on {currentSignal.entry_count_used} entries</span>
        <span>{formatRelativeTime(currentSignal.computed_at)}</span>
      </div>
    </div>
  )
}
