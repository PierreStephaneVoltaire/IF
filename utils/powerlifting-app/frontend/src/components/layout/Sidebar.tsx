import { useState, useRef, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Calendar,
  List,
  GitBranch,
  BarChart3,
  BookOpen,
  Wrench,
  Pill,
  Utensils,
  Trophy,
  TrendingUp,
  Activity,
  Film,
  MoreHorizontal,
  ClipboardList,
} from 'lucide-react'
import { clsx } from 'clsx'

interface SidebarProps {
  mobile?: boolean
}

const PRIMARY_NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/designer', icon: ClipboardList, label: 'Designer' },
  { to: '/list', icon: List, label: 'List' },
  { to: '/charts', icon: BarChart3, label: 'Charts' },
  { to: '/analysis', icon: Activity, label: 'Analysis' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
]

const SECONDARY_NAV_ITEMS = [
  { to: '/timeline', icon: GitBranch, label: 'Timeline' },
  { to: '/supplements', icon: Pill, label: 'Supplements' },
  { to: '/diet', icon: Utensils, label: 'Diet Notes' },
  { to: '/competitions', icon: Trophy, label: 'Competitions' },
  { to: '/maxes', icon: TrendingUp, label: 'Maxes' },
  { to: '/glossary', icon: BookOpen, label: 'Glossary' },
  { to: '/videos', icon: Film, label: 'Videos' },
]

const ALL_NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/designer', icon: ClipboardList, label: 'Designer' },
  { to: '/list', icon: List, label: 'List' },
  { to: '/timeline', icon: GitBranch, label: 'Timeline' },
  { to: '/charts', icon: BarChart3, label: 'Charts' },
  { to: '/analysis', icon: Activity, label: 'Analysis' },
  { to: '/supplements', icon: Pill, label: 'Supplements' },
  { to: '/diet', icon: Utensils, label: 'Diet Notes' },
  { to: '/competitions', icon: Trophy, label: 'Competitions' },
  { to: '/maxes', icon: TrendingUp, label: 'Maxes' },
  { to: '/glossary', icon: BookOpen, label: 'Glossary' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
  { to: '/videos', icon: Film, label: 'Videos' },
]

function MoreMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={ref} className="relative flex flex-col items-center">
      <button
        onClick={() => setOpen((v) => !v)}
        className={clsx(
          'flex flex-col items-center gap-1 min-h-[44px] px-2 py-1 rounded-md transition-colors',
          open
            ? 'bg-accent text-accent-foreground'
            : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
        )}
      >
        <MoreHorizontal className="w-5 h-5" />
        <span className="text-[10px] leading-tight">More</span>
      </button>

      {open && (
        <div className="absolute bottom-full mb-2 right-0 bg-card border border-border rounded-lg shadow-lg py-1 z-[60] min-w-[140px]">
          {SECONDARY_NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'text-primary bg-primary/10'
                    : 'text-foreground hover:bg-accent hover:text-accent-foreground'
                )
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Sidebar({ mobile = false }: SidebarProps) {
  if (mobile) {
    return (
      <nav className="flex gap-1 flex-row justify-around p-2">
        {PRIMARY_NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex flex-col items-center gap-1 min-h-[44px] px-2 py-1 rounded-md transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <Icon className="w-5 h-5" />
            <span className="text-[10px] leading-tight">{label}</span>
          </NavLink>
        ))}
        <MoreMenu />
      </nav>
    )
  }

  return (
    <nav className="flex gap-1 flex-col p-4">
      {ALL_NAV_ITEMS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )
          }
        >
          <Icon className="w-5 h-5" />
          <span className="text-sm">{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
