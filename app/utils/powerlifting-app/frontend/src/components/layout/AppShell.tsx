import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background">
      {/* Mobile bottom nav handled by Sidebar on mobile */}
      <div className="flex">
        {/* Desktop sidebar */}
        <aside className="hidden md:flex md:flex-col md:w-64 md:fixed md:inset-y-0 border-r border-border bg-card">
          <Sidebar />
        </aside>

        {/* Main content */}
        <div className="flex-1 md:ml-64">
          <TopBar />
          <main className="p-4 md:p-6">
            {children}
          </main>
        </div>
      </div>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 md:hidden border-t border-border bg-card z-50">
        <Sidebar mobile />
      </nav>
    </div>
  )
}
