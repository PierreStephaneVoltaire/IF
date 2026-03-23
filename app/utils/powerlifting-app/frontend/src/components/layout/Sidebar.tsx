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
} from 'lucide-react'
import { clsx } from 'clsx'

interface SidebarProps {
  mobile?: boolean
}

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/list', icon: List, label: 'List' },
  { to: '/timeline', icon: GitBranch, label: 'Timeline' },
  { to: '/charts', icon: BarChart3, label: 'Charts' },
  { to: '/supplements', icon: Pill, label: 'Supplements' },
  { to: '/diet', icon: Utensils, label: 'Diet Notes' },
  { to: '/competitions', icon: Trophy, label: 'Competitions' },
  { to: '/glossary', icon: BookOpen, label: 'Glossary' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
]

export default function Sidebar({ mobile = false }: SidebarProps) {
  return (
    <nav
      className={clsx(
        'flex gap-1',
        mobile
          ? 'flex-row justify-around p-2'
          : 'flex-col p-4'
      )}
    >
      {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
              mobile ? 'flex-col gap-1 py-2 px-4' : '',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )
          }
        >
          <Icon className="w-5 h-5" />
          <span className={clsx('text-sm', mobile && 'text-xs')}>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
