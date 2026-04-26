import { ReactNode, useEffect } from 'react'
import { AppShell as MantineAppShell } from '@mantine/core'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import SettingsDrawer from './SettingsDrawer'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  useEffect(() => {
    const handleResize = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <MantineAppShell
      header={{ height: 60 }}
      navbar={{
        width: 256,
        breakpoint: 'md',
        collapsed: { mobile: true },
      }}
      footer={{
        height: 'calc(60px + env(safe-area-inset-bottom, 0px))',
        offset: false,
      }}
      padding="md"
      style={{ 
        minHeight: '100dvh',
        height: 'calc(var(--vh, 1vh) * 100)',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <MantineAppShell.Header>
        <TopBar />
      </MantineAppShell.Header>

      <MantineAppShell.Navbar
        style={{
          height: 'calc(var(--vh, 1vh) * 100 - 60px)',
          maxHeight: 'calc(var(--vh, 1vh) * 100 - 60px)',
        }}
      >
        <Sidebar />
      </MantineAppShell.Navbar>

      <MantineAppShell.Main
        pb={{ base: 'calc(180px + env(safe-area-inset-bottom, 0px))', md: 140 }}
        style={{ flex: 1 }}
      >
        {children}
      </MantineAppShell.Main>

      {/* Mobile bottom navigation */}
      <MantineAppShell.Footer 
        hiddenFrom="md" 
        style={{ 
          position: 'fixed', 
          bottom: 0, 
          left: 0, 
          right: 0, 
          height: 'calc(60px + env(safe-area-inset-bottom, 0px))',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          backgroundColor: 'var(--mantine-color-body)',
          zIndex: 100
        }}
      >
        <Sidebar mobile />
      </MantineAppShell.Footer>

      <SettingsDrawer />
    </MantineAppShell>
  )
}
