import re

with open('frontend/src/pages/AnalysisPage.tsx', 'r') as f:
    content = f.read()

# Extract AiAnalysis section
ai_start = content.find('          {/* ─── Exercise ROI Correlation')
ai_end = content.find('          {/* Formula Reference */}')

ai_jsx = content[ai_start:ai_end]

ai_file_content = f"""import {{ useState, useEffect }} from 'react'
import {{ Paper, Group, Text, Badge, Button, Loader, Box, Table, Accordion, Stack, SimpleGrid }} from '@mantine/core'
import {{ Brain, RefreshCw, Trophy }} from 'lucide-react'
import {{ fetchCorrelationReport, fetchProgramEvaluation, type CorrelationReport, type ProgramEvaluationReport }} from '@/api/analytics'
import {{ useProgramStore }} from '@/store/programStore'

const CORR_DIR_BADGE: Record<string, string> = {{
  positive: 'green',
  negative: 'red',
  unclear: 'gray',
}}

const CORR_STRENGTH_BADGE: Record<string, string> = {{
  strong: 'green',
  moderate: 'blue',
  weak: 'yellow',
}}

interface AiAnalysisProps {{
  effectiveWeeks: number
  weeksMode: number | 'block'
}}

export default function AiAnalysis({{ effectiveWeeks, weeksMode }}: AiAnalysisProps) {{
  const {{ program }} = useProgramStore()

  const [corrReport, setCorrReport] = useState<CorrelationReport | null>(null)
  const [corrLoading, setCorrLoading] = useState(false)
  const [corrError, setCorrError] = useState<string | null>(null)

  const [evalReport, setEvalReport] = useState<ProgramEvaluationReport | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  useEffect(() => {{
    if (effectiveWeeks < 4) {{
      setCorrReport(null)
      return
    }}
    setCorrLoading(true)
    setCorrError(null)
    fetchCorrelationReport(effectiveWeeks, 'current')
      .then(setCorrReport)
      .catch((e) => setCorrError(e.message))
      .finally(() => setCorrLoading(false))
  }}, [effectiveWeeks])

  useEffect(() => {{
    if (weeksMode !== 'block') {{
      setEvalReport(null)
      setEvalError(null)
      return
    }}
    const completedCount = program?.sessions?.filter(s => (s.block ?? 'current') === 'current' && s.completed).length ?? 0
    if (completedCount < 4) {{
      setEvalReport(null)
      return
    }}
    setEvalLoading(true)
    setEvalError(null)
    fetchProgramEvaluation(false)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false))
  }}, [weeksMode, program?.meta?.program_start])

  const refreshEvaluation = () => {{
    if (weeksMode !== 'block') return
    setEvalLoading(true)
    setEvalError(null)
    setEvalReport(null)
    fetchProgramEvaluation(true)
      .then(setEvalReport)
      .catch((e) => setEvalError(e.message))
      .finally(() => setEvalLoading(false))
  }}

  const refreshCorrelation = () => {{
    if (effectiveWeeks < 4) return
    setCorrLoading(true)
    setCorrError(null)
    setCorrReport(null)
    fetchCorrelationReport(effectiveWeeks, 'current')
      .then(setCorrReport)
      .catch((e) => setCorrError(e.message))
      .finally(() => setCorrLoading(false))
  }}

  return (
    <>
{ai_jsx}    </>
  )
}}
"""

with open('frontend/src/components/analysis/AiAnalysis.tsx', 'w') as f:
    f.write(ai_file_content)

# Extract WeeklyData section
weekly_start = content.find('          {/* Per-lift breakdown */}')
weekly_end = content.find('          {/* Fatigue Dimensions */}')

weekly_jsx = content[weekly_start:weekly_end]

weekly_file_content = f"""import {{ Fragment, useState }} from 'react'
import {{ Paper, Text, Box, Table, Group, Button, Badge, SimpleGrid, Stack }} from '@mantine/core'
import {{ ResponsiveContainer, PieChart, Pie, Cell, Tooltip, BarChart, CartesianGrid, XAxis, YAxis, Bar }} from 'recharts'
import type {{ WeeklyAnalysis }} from '@/api/analytics'

const CHART_COLORS = [
  '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#14b8a6', '#6366f1',
]

function rpeTrendIcon(trend: number | undefined | null) {{
  if (trend === undefined || trend === null) return null
  if (trend > 0.1) return <Text span fz="sm" c="red" title="RPE increasing">↗</Text>
  if (trend < -0.1) return <Text span fz="sm" c="green" title="RPE decreasing">↘</Text>
  return <Text span fz="sm" c="dimmed" title="RPE stable">→</Text>
}}

interface WeeklyDataProps {{
  data: WeeklyAnalysis
  viewMode: 'raw' | 'graph'
  perLiftDetails: Record<string, any>
  muscleGroupSets: Record<string, number>
  muscleGroupAvgWeekly: {{ sets: Record<string, number>; volume: Record<string, number> }}
}}

export default function WeeklyData({{ data, viewMode, perLiftDetails, muscleGroupSets, muscleGroupAvgWeekly }}: WeeklyDataProps) {{
  const [expandedLifts, setExpandedLifts] = useState<Set<string>>(new Set())

  return (
    <>
{weekly_jsx}    </>
  )
}}
"""

with open('frontend/src/components/analysis/WeeklyData.tsx', 'w') as f:
    f.write(weekly_file_content)

# Now modify AnalysisPage.tsx to remove these sections and add imports
new_content = content[:weekly_start] + "          <WeeklyData data={data} viewMode={viewMode} perLiftDetails={perLiftDetails} muscleGroupSets={muscleGroupSets} muscleGroupAvgWeekly={muscleGroupAvgWeekly} />\\n\\n" + content[weekly_end:ai_start] + "          <AiAnalysis effectiveWeeks={effectiveWeeks} weeksMode={weeksMode} />\\n\\n" + content[ai_end:]

# remove ai state and effects
import re

# Remove states
new_content = re.sub(r'  // Correlation report state.*?(?=  // Compute effective weeks)', '', new_content, flags=re.DOTALL)
new_content = re.sub(r'  // Fetch correlation report when weeks >= 4.*?(?=  return \()', '', new_content, flags=re.DOTALL)
new_content = re.sub(r'const CORR_DIR_BADGE.*?}\n', '', new_content, flags=re.DOTALL)
new_content = re.sub(r'const CORR_STRENGTH_BADGE.*?}\n', '', new_content, flags=re.DOTALL)

# Add imports
import_statement = "import WeeklyData from '@/components/analysis/WeeklyData'\\nimport AiAnalysis from '@/components/analysis/AiAnalysis'\\n"
new_content = new_content.replace("import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'", import_statement + "import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'")

# Write back
with open('frontend/src/pages/AnalysisPage.tsx', 'w') as f:
    f.write(new_content)

