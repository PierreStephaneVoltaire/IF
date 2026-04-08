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
import SupplementsPage from '@/pages/SupplementsPage'
import DietNotesPage from '@/pages/DietNotesPage'
import CompetitionsPage from '@/pages/CompetitionsPage'
import MaxesPage from '@/pages/MaxesPage'
import VideosPage from '@/pages/VideosPage'

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
        <Route path="/supplements" element={<SupplementsPage />} />
        <Route path="/diet" element={<DietNotesPage />} />
        <Route path="/competitions" element={<CompetitionsPage />} />
        <Route path="/glossary" element={<GlossaryPage />} />
        <Route path="/maxes" element={<MaxesPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/videos" element={<VideosPage />} />
      </Routes>
    </AppShell>
  )
}
