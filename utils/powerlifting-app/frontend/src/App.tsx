import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useProgramStore } from '@/store/programStore'
import AppShell from '@/components/layout/AppShell'
import Dashboard from '@/pages/Dashboard'
import CalendarPage from '@/pages/CalendarPage'
import DesignerPage from '@/pages/DesignerPage'
import DesignerLanding from '@/pages/DesignerLanding'
import DesignerPhases from '@/pages/DesignerPhases'
import ListPage from '@/pages/ListPage'
import AnalysisPage from '@/pages/AnalysisPage'
import GlossaryPage from '@/pages/GlossaryPage'
import ToolsPage from '@/pages/ToolsPage'
import SupplementsPage from '@/pages/SupplementsPage'
import BiometricsPage from '@/pages/BiometricsPage'
import CompetitionsPage from '@/pages/CompetitionsPage'
import MaxesPage from '@/pages/MaxesPage'
import VideosPage from '@/pages/VideosPage'
import AboutPage from '@/pages/AboutPage'
import ImportWizardPage from '@/pages/ImportWizardPage'
import TemplateLibraryPage from '@/pages/TemplateLibraryPage'
import TemplateDetailPage from '@/pages/TemplateDetailPage'
import TemplateCreatePage from '@/pages/TemplateCreatePage'
import TemplateEditPage from '@/pages/TemplateEditPage'
import RankingsPage from '@/pages/RankingsPage'

// Tool Components
import PlateCalculator from '@/components/tools/PlateCalculator'
import DotsCalculator from '@/components/tools/DotsCalculator'
import WeightTracker from '@/components/tools/WeightTracker'
import PercentTable from '@/components/tools/PercentTable'
import UnitConverter from '@/components/tools/UnitConverter'
import AttemptSelector from '@/components/tools/AttemptSelector'

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
        <Route path="/designer" element={<DesignerLanding />} />
        <Route path="/designer/phases" element={<DesignerPhases />} />
        <Route path="/designer/sessions" element={<DesignerPage />} />
        <Route path="/list" element={<ListPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/rankings" element={<RankingsPage />} />
        <Route path="/supplements" element={<SupplementsPage />} />
        <Route path="/biometrics" element={<BiometricsPage />} />
        <Route path="/diet" element={<BiometricsPage />} />
        <Route path="/designer/competitions" element={<CompetitionsPage />} />
        <Route path="/designer/glossary" element={<GlossaryPage />} />
        <Route path="/maxes" element={<MaxesPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/tools/plate" element={<PlateCalculator />} />
        <Route path="/tools/dots" element={<DotsCalculator />} />
        <Route path="/tools/weight" element={<WeightTracker />} />
        <Route path="/tools/percent" element={<PercentTable />} />
        <Route path="/tools/converter" element={<UnitConverter />} />
        <Route path="/tools/attempts" element={<AttemptSelector />} />
        <Route path="/videos" element={<VideosPage />} />
        <Route path="/designer/import" element={<ImportWizardPage />} />
        <Route path="/designer/templates" element={<TemplateLibraryPage />} />
        <Route path="/designer/templates/new" element={<TemplateCreatePage />} />
        <Route path="/designer/templates/:sk/edit" element={<TemplateEditPage />} />
        <Route path="/designer/templates/:sk" element={<TemplateDetailPage />} />
        <Route path="/about" element={<AboutPage />} />
      </Routes>
    </AppShell>
  )
}
