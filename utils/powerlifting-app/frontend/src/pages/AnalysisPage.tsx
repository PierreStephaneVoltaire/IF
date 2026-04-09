import { useState, useEffect } from 'react'
import { Activity, Download, AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'
import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'

function fatigueColor(score: number | null): string {
  if (score === null) return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  if (score >= 0.7) return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  if (score >= 0.4) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
}

function fatigueLabel(score: number | null): string {
  if (score === null) return 'N/A'
  if (score >= 0.7) return 'High'
  if (score >= 0.4) return 'Moderate'
  return 'Low'
}

function complianceColor(pct: number | null): string {
  if (pct === null) return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  if (pct >= 80) return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
  if (pct >= 50) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
}

function rpeTrendIcon(trend?: string) {
  if (!trend) return null
  if (trend === 'up') return <span className="text-red-500 text-xs font-medium">&#9650; rising</span>
  if (trend === 'down') return <span className="text-green-500 text-xs font-medium">&#9660; improving</span>
  return <span className="text-gray-500 text-xs font-medium">&#9644; stable</span>
}

export default function AnalysisPage() {
  const [weeks, setWeeks] = useState(1)
  const [data, setData] = useState<WeeklyAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetchWeeklyAnalysis(weeks)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [weeks])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Weekly Analysis</h1>
        <div className="flex items-center gap-3">
          <select
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            className="px-3 py-1.5 border border-border rounded-md bg-background text-sm"
          >
            <option value={1}>Last 1 week</option>
            <option value={2}>Last 2 weeks</option>
            <option value={4}>Last 4 weeks</option>
            <option value={8}>Last 8 weeks</option>
          </select>
          <a
            href="/fitness/api/export/xlsx"
            download="program_history.xlsx"
            className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90 transition-opacity"
          >
            <Download className="w-4 h-4" />
            Export Excel
          </a>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center min-h-[20vh]">
          <div className="animate-pulse text-muted-foreground">Loading analysis...</div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Top summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Fatigue Index */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Fatigue Index</h3>
              </div>
              <p className={`text-3xl font-bold px-2 py-1 rounded inline-block ${fatigueColor(data.fatigue_index)}`}>
                {data.fatigue_index !== null ? (data.fatigue_index * 100).toFixed(0) + '%' : 'N/A'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {fatigueLabel(data.fatigue_index)} risk
              </p>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                Composite of avg session RPE (40%), week-over-week volume change (35%), and bodyweight trend (25%).
              </p>
            </div>

            {/* Compliance */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Compliance</h3>
              </div>
              <p className={`text-3xl font-bold px-2 py-1 rounded inline-block ${complianceColor(data.compliance)}`}>
                {data.compliance !== null ? data.compliance.toFixed(0) + '%' : 'N/A'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {data.block} block
              </p>
              <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
                Session completion vs planned schedule (50%) and RPE adherence to phase targets (50%).
              </p>
            </div>

            {/* Meet Projection */}
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-primary" />
                <h3 className="font-medium">Projected Total</h3>
              </div>
              {data.projection ? (
                <>
                  <p className="text-3xl font-bold">{data.projection.total.toFixed(1)} kg</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Confidence: {(data.projection.confidence * 100).toFixed(0)}%
                    {data.projection.weeks_to_comp !== undefined && ` (${data.projection.weeks_to_comp.toFixed(1)} weeks to comp)`}
                  </p>
                  {data.projection.method === 'comp_results' && (
                    <p className="text-xs text-muted-foreground mt-1">Based on last competition results</p>
                  )}
                </>
              ) : (
                <p className="text-lg text-muted-foreground">{data.projection_reason || 'No competition date set'}</p>
              )}
            </div>
          </div>

          {/* Per-lift breakdown */}
          {Object.keys(data.lifts).length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="font-medium mb-3">Per-Lift Breakdown</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4">Exercise</th>
                      <th className="text-right py-2 px-4">Progression</th>
                      <th className="text-right py-2 px-4">Volume %</th>
                      <th className="text-right py-2 px-4">Intensity %</th>
                      <th className="text-right py-2 pl-4">RPE Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(data.lifts).map(([name, lift]) => (
                      <tr key={name} className="border-b border-border/50">
                        <td className="py-2 pr-4 font-medium capitalize">{name}</td>
                        <td className="text-right py-2 px-4">
                          {lift.progression_rate_kg_per_week !== undefined && lift.progression_rate_kg_per_week !== null
                            ? <span className={lift.progression_rate_kg_per_week >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {lift.progression_rate_kg_per_week >= 0 ? '+' : ''}{lift.progression_rate_kg_per_week.toFixed(1)} kg/wk
                              </span>
                            : <span className="text-muted-foreground">--</span>}
                        </td>
                        <td className="text-right py-2 px-4">
                          {lift.volume_change_pct !== undefined
                            ? <span className={lift.volume_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {lift.volume_change_pct >= 0 ? '+' : ''}{lift.volume_change_pct.toFixed(0)}%
                              </span>
                            : <span className="text-muted-foreground">--</span>}
                        </td>
                        <td className="text-right py-2 px-4">
                          {lift.intensity_change_pct !== undefined
                            ? <span className={lift.intensity_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                                {lift.intensity_change_pct >= 0 ? '+' : ''}{lift.intensity_change_pct.toFixed(0)}%
                              </span>
                            : <span className="text-muted-foreground">--</span>}
                        </td>
                        <td className="text-right py-2 pl-4">
                          {rpeTrendIcon(lift.rpe_trend) || <span className="text-muted-foreground">--</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Flags */}
          {data.flags.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-yellow-500" />
                <h3 className="font-medium">Flags</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.flags.map((flag) => (
                  <span
                    key={flag}
                    className="px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Footer info */}
          <p className="text-xs text-muted-foreground">
            Week {data.week} ({data.block}) &middot; {data.sessions_analyzed} sessions analyzed
          </p>
        </>
      )}

      {!data && !loading && !error && (
        <div className="flex items-center justify-center min-h-[20vh]">
          <p className="text-muted-foreground">No analysis data available for the selected period.</p>
        </div>
      )}
    </div>
  )
}
