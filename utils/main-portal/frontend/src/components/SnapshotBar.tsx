import type { FinanceData, HealthData } from '../types'
import { formatCurrency, formatDaysUntil } from '../utils/formatters'

interface SnapshotBarProps {
  finance: FinanceData | null
  health: HealthData | null
  loading?: boolean
}

export function SnapshotBar({ finance, health, loading }: SnapshotBarProps) {
  if (loading) {
    return (
      <div className="flex flex-wrap items-center gap-6 px-4 py-3 border-b border-border animate-pulse">
        <div className="h-5 w-32 bg-muted-foreground/20 rounded" />
        <div className="h-5 w-28 bg-muted-foreground/20 rounded" />
        <div className="h-5 w-24 bg-muted-foreground/20 rounded" />
      </div>
    )
  }

  const items: { label: string; value: string; color?: string }[] = []

  if (finance) {
    items.push({
      label: 'Net Worth',
      value: formatCurrency(finance.net_worth),
      color: finance.net_worth >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400',
    })
    items.push({
      label: 'Surplus',
      value: formatCurrency(finance.monthly_surplus) + '/mo',
      color: finance.monthly_surplus >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400',
    })
  }

  if (health) {
    items.push({
      label: 'Week',
      value: health.current_week,
    })
    if (health.days_to_comp !== null) {
      items.push({
        label: 'Comp',
        value: formatDaysUntil(health.days_to_comp),
        color: health.days_to_comp <= 14 ? 'text-orange-600 dark:text-orange-400' : undefined,
      })
    }
  }

  if (items.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap items-center gap-6 px-4 py-3 border-b border-border text-sm">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-muted-foreground">{item.label}:</span>
          <span className={`font-medium ${item.color || ''}`}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}
