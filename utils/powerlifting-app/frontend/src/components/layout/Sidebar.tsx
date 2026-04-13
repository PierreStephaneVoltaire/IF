import { useLocation, NavLink as RouterNavLink } from 'react-router-dom'
import {
  NavLink,
  Menu,
  Stack,
  Group,
  ScrollArea,
  ActionIcon,
  Text,
} from '@mantine/core'
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

interface SidebarProps {
  mobile?: boolean
}

interface NavItem {
  to: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon: React.ComponentType<any>
  label: string
}

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/designer', icon: ClipboardList, label: 'Designer' },
  { to: '/list', icon: List, label: 'List' },
  { to: '/charts', icon: BarChart3, label: 'Charts' },
  { to: '/analysis', icon: Activity, label: 'Analysis' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
]

const SECONDARY_NAV_ITEMS: NavItem[] = [
  { to: '/timeline', icon: GitBranch, label: 'Timeline' },
  { to: '/supplements', icon: Pill, label: 'Supplements' },
  { to: '/biometrics', icon: Utensils, label: 'Biometrics' },
  { to: '/competitions', icon: Trophy, label: 'Competitions' },
  { to: '/maxes', icon: TrendingUp, label: 'Maxes' },
  { to: '/glossary', icon: BookOpen, label: 'Glossary' },
  { to: '/videos', icon: Film, label: 'Videos' },
]

const ALL_NAV_ITEMS: NavItem[] = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/designer', icon: ClipboardList, label: 'Designer' },
  { to: '/list', icon: List, label: 'List' },
  { to: '/timeline', icon: GitBranch, label: 'Timeline' },
  { to: '/charts', icon: BarChart3, label: 'Charts' },
  { to: '/analysis', icon: Activity, label: 'Analysis' },
  { to: '/supplements', icon: Pill, label: 'Supplements' },
  { to: '/biometrics', icon: Utensils, label: 'Biometrics' },
  { to: '/competitions', icon: Trophy, label: 'Competitions' },
  { to: '/maxes', icon: TrendingUp, label: 'Maxes' },
  { to: '/glossary', icon: BookOpen, label: 'Glossary' },
  { to: '/tools', icon: Wrench, label: 'Tools' },
  { to: '/videos', icon: Film, label: 'Videos' },
]

function DesktopSidebar() {
  const location = useLocation()

  return (
    <ScrollArea h="100%" offsetScrollbars>
      <Stack gap={4} p="md">
        {ALL_NAV_ITEMS.map(({ to, icon: Icon, label }) => {
          const isActive =
            to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(to)

          return (
            <NavLink
              key={to}
              component={RouterNavLink}
              to={to}
              end={to === '/'}
              label={label}
              leftSection={<Icon size={20} />}
              active={isActive}
              variant="light"
              color="blue"
              style={{ borderRadius: 'var(--mantine-radius-md)' }}
            />
          )
        })}
      </Stack>
    </ScrollArea>
  )
}

function MobileMoreMenu() {
  const location = useLocation()

  return (
    <Menu shadow="md" position="top-end" withArrow offset={8}>
      <Menu.Target>
        <ActionIcon
          variant="subtle"
          size="lg"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            height: 'auto',
            width: 'auto',
            padding: '4px 8px',
          }}
        >
          <MoreHorizontal size={20} />
          <Text fz={10} lh={1}>More</Text>
        </ActionIcon>
      </Menu.Target>

      <Menu.Dropdown>
        {SECONDARY_NAV_ITEMS.map(({ to, icon: Icon, label }) => {
          const isActive =
            to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(to)

          return (
            <Menu.Item
              key={to}
              component={RouterNavLink}
              to={to}
              leftSection={<Icon size={16} />}
              color={isActive ? 'blue' : undefined}
            >
              {label}
            </Menu.Item>
          )
        })}
      </Menu.Dropdown>
    </Menu>
  )
}

function MobileSidebar() {
  const location = useLocation()

  return (
    <Group justify="space-around" wrap="nowrap" p="xs">
      {PRIMARY_NAV_ITEMS.map(({ to, icon: Icon, label }) => {
        const isActive =
          to === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(to)

        return (
          <ActionIcon
            key={to}
            component={RouterNavLink}
            to={to}
            end={to === '/'}
            variant={isActive ? 'filled' : 'subtle'}
            color={isActive ? 'blue' : 'gray'}
            size="lg"
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              height: 'auto',
              width: 'auto',
              padding: '4px 8px',
              minHeight: 44,
            }}
          >
            <Icon size={20} />
            <Text fz={10} lh={1}>{label}</Text>
          </ActionIcon>
        )
      })}
      <MobileMoreMenu />
    </Group>
  )
}

export default function Sidebar({ mobile = false }: SidebarProps) {
  return mobile ? <MobileSidebar /> : <DesktopSidebar />
}
