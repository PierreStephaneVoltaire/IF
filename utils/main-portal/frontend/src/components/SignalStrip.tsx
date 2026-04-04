import type { SignalsData } from '../types'
import { getTrendIcon, getTrendColor, getLifeLoadColor, getScoreColor } from '../utils/formatters'

interface SignalStripProps {
  signals: SignalsData | null
  loading?: boolean
}

export function SignalStrip({ signals, loading }: SignalStripProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-muted animate-pulse">
        <div className="h-6 w-20 bg-muted-foreground/20 rounded" />
        <div className="h-6 w-16 bg-muted-foreground/20 rounded" />
        <div className="h-6 w-20 bg-muted-foreground/20 rounded" />
        <div className="h-6 w-16 bg-muted-foreground/20 rounded" />
      </div>
    )
  }

  if (!signals) {
    return (
      <div className="flex items-center gap-4 px-4 py-3 rounded-lg bg-muted text-muted-foreground">
        <span>Signal data unavailable</span>
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-4 px-4 py-3 rounded-lg bg-muted">
      {/* Mental Health Score */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Score:</span>
        <span className={`text-lg font-semibold ${getScoreColor(signals.mental_health_score)}`}>
          {signals.mental_health_score.toFixed(1)}
        </span>
      </div>

      {/* Trend */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Trend:</span>
        <span className={`font-medium ${getTrendColor(signals.trend)}`}>
          {getTrendIcon(signals.trend)} {signals.trend.replace('_', ' ')}
        </span>
      </div>

      {/* Life Load */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Life Load:</span>
        <span className={`px-2 py-0.5 text-xs font-medium rounded capitalize ${getLifeLoadColor(signals.life_load)}`}>
          {signals.life_load.replace('_', ' ')}
        </span>
      </div>

      {/* Social Battery */}
      {signals.social_battery && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Social:</span>
          <span className="text-sm font-medium capitalize">{signals.social_battery}</span>
        </div>
      )}
    </div>
  )
}
