interface PortalCardProps {
  name: string
  icon: string
  href: string
  status: 'reachable' | 'unreachable'
  pendingCount?: number
  lines: string[]
}

export function PortalCard({ name, icon, href, status, pendingCount, lines }: PortalCardProps) {
  const statusDot = status === 'reachable' ? (
    <span className="w-2.5 h-2.5 rounded-full bg-green-500" title="Reachable" />
  ) : (
    <span className="w-2.5 h-2.5 rounded-full bg-gray-400" title="Unreachable" />
  )

  const badge = pendingCount !== undefined && pendingCount > 0 ? (
    <span className="ml-2 px-2 py-0.5 text-xs font-medium rounded-full bg-red-500 text-white">
      {pendingCount}
    </span>
  ) : null

  const content = (
    <div className="group block p-4 rounded-lg border border-border bg-card hover:bg-accent transition-colors">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <h3 className="font-medium text-card-foreground group-hover:text-accent-foreground">
            {name}
          </h3>
          {badge}
        </div>
        {statusDot}
      </div>
      <div className="space-y-1 text-sm text-muted-foreground">
        {lines.map((line, i) => (
          <p key={i}>{line}</p>
        ))}
      </div>
    </div>
  )

  if (status === 'unreachable') {
    return content
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block">
      {content}
    </a>
  )
}
