import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useProgramStore } from '@/store/programStore'
import AppShell from '@/components/layout/AppShell'
import Dashboard from '@/pages/Dashboard'
import CalendarPage from '@/pages/CalendarPage'
import ListPage from '@/pages/ListPage'
import TimelinePage from '@/pages/TimelinePage'
import ChartsPage from '@/pages/ChartsPage'
import GlossaryPage from '@/pages/GlossaryPage'
import ToolsPage from '@/pages/ToolsPage'

export default function App() {
  const { loadProgram, version } = useProgramStore()

  useEffect(() => {
    loadProgram(version).catch(console.error)
  }, [version, loadProgram])

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/list" element={<ListPage />} />
        <Route path="/timeline" element={<TimelinePage />} />
        <Route path="/charts" element={<ChartsPage />} />
        <Route path="/glossary" element={<GlossaryPage />} />
        <Route path="/tools" element={<ToolsPage />} />
      </Routes>
    </AppShell>
  )
}
