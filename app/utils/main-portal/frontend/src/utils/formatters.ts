export function formatCurrency(amount: number, currency: string = 'CAD'): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return new Intl.DateTimeFormat('en-CA', {
    month: 'short',
    day: 'numeric',
  }).format(date)
}

export function formatDaysUntil(days: number | null): string {
  if (days === null) return 'N/A'
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  if (days < 0) return `${Math.abs(days)} days ago`
  return `${days} days`
}

export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateStr)
}

export function getTrendIcon(trend: string): string {
  switch (trend) {
    case 'improving': return '↑'
    case 'declining_slow': return '↓'
    case 'declining_fast': return '↓↓'
    case 'stable':
    default: return '→'
  }
}

export function getTrendColor(trend: string): string {
  switch (trend) {
    case 'improving': return 'text-green-500'
    case 'declining_slow': return 'text-yellow-500'
    case 'declining_fast': return 'text-red-500'
    case 'stable':
    default: return 'text-muted-foreground'
  }
}

export function getLifeLoadColor(lifeLoad: string): string {
  switch (lifeLoad) {
    case 'low': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    case 'moderate': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
    case 'high': return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
    case 'very_high': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    default: return 'bg-secondary text-secondary-foreground'
  }
}

export function getScoreColor(score: number): string {
  if (score >= 7) return 'text-green-500'
  if (score >= 5) return 'text-yellow-500'
  if (score >= 3) return 'text-orange-500'
  return 'text-red-500'
}
