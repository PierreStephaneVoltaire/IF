import { ReactNode } from 'react'
import { AppShell as MantineAppShell } from '@mantine/core'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import SettingsDrawer from './SettingsDrawer'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <MantineAppShell
      header={{ height: 60 }}
      navbar={{
        width: 256,
        breakpoint: 'md',
        collapsed: { mobile: true },
      }}
      footer={{ height: 60, collapsed: { desktop: true, mobile: false } }}
      padding="md"
      style={{ minHeight: '100dvh' }}
    >
      <MantineAppShell.Header>
        <TopBar />
      </MantineAppShell.Header>

      <MantineAppShell.Navbar>
        <Sidebar />
      </MantineAppShell.Navbar>

      <MantineAppShell.Main pb={100}>{children}</MantineAppShell.Main>

      {/* Mobile bottom navigation */}
      <MantineAppShell.Footer hiddenFrom="md">
        <Sidebar mobile />
      </MantineAppShell.Footer>

      <SettingsDrawer />
    </MantineAppShell>
  )
}
