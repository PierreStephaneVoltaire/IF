import { useState, useEffect } from 'react'
import { Stack, Title, Paper, Text, SimpleGrid, TextInput, Group, Loader, Center } from '@mantine/core'
import { useProgramStore } from '@/store/programStore'
import { fetchWeeklyAnalysis, type WeeklyAnalysis } from '@/api/analytics'
import { updateMetaField } from '@/api/client'
import { Trophy } from 'lucide-react'

export default function AttemptSelector() {
  const { program, version } = useProgramStore()
  const [data, setData] = useState<WeeklyAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [attemptPctRaw, setAttemptPctRaw] = useState({ opener: '0.90', second: '0.955', third: '1.00' })
  const [attemptPctErrors, setAttemptPctErrors] = useState<{ opener: string | null; second: string | null; third: string | null }>({ opener: null, second: null, third: null })
  const [attemptPct, setAttemptPct] = useState({ opener: 0.90, second: 0.955, third: 1.00 })
  const [savingAttempt, setSavingAttempt] = useState(false)

  useEffect(() => {
    setLoading(true)
    // 4 weeks is a good window to get reliable attempt selection data based on e1RM
    fetchWeeklyAnalysis(4, 'current')
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const metaPct = program?.meta?.attempt_pct
    if (metaPct) {
      setAttemptPct({ opener: metaPct.opener, second: metaPct.second, third: metaPct.third })
      setAttemptPctRaw({ opener: String(metaPct.opener), second: String(metaPct.second), third: String(metaPct.third) })
    }
  }, [program?.meta?.attempt_pct])

  useEffect(() => {
    const timer = setTimeout(() => {
      const keys: Array<'opener' | 'second' | 'third'> = ['opener', 'second', 'third']
      const newErrors = { opener: null as string | null, second: null as string | null, third: null as string | null }
      const newNums = { ...attemptPct }
      let allValid = true
      for (const key of keys) {
        const raw = attemptPctRaw[key]
        const v = parseFloat(raw)
        if (raw === '' || isNaN(v) || v < 0 || v > 1) {
          newErrors[key] = 'Enter a value between 0 and 1 (e.g. 0.90)'
          allValid = false
        } else {
          newErrors[key] = null
          newNums[key] = v
        }
      }
      setAttemptPctErrors(newErrors)
      if (allValid) {
        setAttemptPct(newNums)
        setSavingAttempt(true)
        updateMetaField(version, 'attempt_pct', newNums)
          .then(() => fetchWeeklyAnalysis(4, 'current').then(setData))
          .finally(() => setSavingAttempt(false))
      }
    }, 400)
    return () => clearTimeout(timer)
  }, [attemptPctRaw, attemptPct, version])

  if (loading && !data) {
    return <Center mih="50vh"><Loader /></Center>
  }

  return (
    <Stack gap="md">
      <Title order={2}>Attempt Selector</Title>
      
      {data?.attempt_selection ? (
        <Paper withBorder p="md">
          <Group gap="xs" mb="xs">
            <Trophy size={18} />
            <Text fw={500}>Competition Attempt Percentages</Text>
          </Group>
          <Text size="xs" c="dimmed" mb="sm">Based on projected competition maxes. Enter as decimal (e.g. 0.90 for 90%).</Text>
          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
            {[
              { key: 'opener' as const, label: 'Opener', hint: 'Should feel easy under worst conditions' },
              { key: 'second' as const, label: 'Second', hint: 'A confident single, builds momentum' },
              { key: 'third' as const, label: 'Third', hint: 'Your projected max — go for it' },
            ].map(({ key, label, hint }) => (
              <TextInput
                key={key}
                id={`attempt-pct-${key}`}
                label={label}
                size="sm"
                value={attemptPctRaw[key]}
                onChange={(e) => setAttemptPctRaw(p => ({ ...p, [key]: e.target.value }))}
                error={attemptPctErrors[key]}
                description={!attemptPctErrors[key] ? hint : undefined}
              />
            ))}
          </SimpleGrid>
          {savingAttempt && <Text size="xs" c="dimmed" mt="xs">Saving...</Text>}
          <SimpleGrid cols={{ base: 2, sm: 4 }} mt="sm">
            {Object.entries(data.attempt_selection)
              .filter(([k]) => k !== 'total' && k !== 'attempt_pct_used')
              .map(([lift, attempts]) => (
                <Stack key={lift} gap={2} align="center" p="sm" style={{ borderRadius: 'var(--mantine-radius-sm)', background: 'var(--mantine-color-default-hover)' }}>
                  <Text fw={500} style={{ textTransform: 'capitalize' }}>{lift}</Text>
                  <Text size="sm" fw={700}>
                    {(attempts as any).opener} / {(attempts as any).second} / {(attempts as any).third} kg
                  </Text>
                </Stack>
              ))}
          </SimpleGrid>
          {data.attempt_selection.total !== undefined && (
            <Group justify="center" mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
              <Text fw={700} size="lg">Projected total: {data.attempt_selection.total} kg</Text>
            </Group>
          )}
        </Paper>
      ) : (
        <Paper withBorder p="md">
          <Text c="dimmed">No projection data available to calculate attempts. Make sure you have estimated 1RMs logged.</Text>
        </Paper>
      )}
    </Stack>
  )
}
