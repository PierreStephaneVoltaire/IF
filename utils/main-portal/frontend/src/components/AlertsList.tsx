interface AlertsListProps {
  alerts: string[]
  loading?: boolean
}

export function AlertsList({ alerts, loading }: AlertsListProps) {
  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-10 w-full bg-muted-foreground/10 rounded" />
        <div className="h-10 w-3/4 bg-muted-foreground/10 rounded" />
      </div>
    )
  }

  if (alerts.length === 0) {
    return (
      <div className="px-4 py-3 rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800">
        <p className="text-sm text-green-700 dark:text-green-300">
          No alerts — everything looks good
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
        <span className="text-orange-500">!</span>
        Alerts
      </h3>
      <ul className="space-y-1">
        {alerts.map((alert, i) => (
          <li
            key={i}
            className="px-3 py-2 rounded-md bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 text-sm text-orange-800 dark:text-orange-200"
          >
            {alert}
          </li>
        ))}
      </ul>
    </div>
  )
}
