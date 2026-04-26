import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Save, Trophy, Target, CheckCircle } from 'lucide-react'
import {
  Accordion,
  Badge,
  Button,
  Checkbox,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { useFederationStore } from '@/store/federationStore'
import { useUiStore } from '@/store/uiStore'
import { useSettingsStore } from '@/store/settingsStore'
import { calculateDots } from '@/utils/dots'
import type { Competition, FederationLibrary, LiftResults } from '@powerlifting/types'

const STATUS_COLORS: Record<string, string> = {
  completed: 'green',
  confirmed: 'blue',
  optional: 'yellow',
  skipped: 'gray',
}

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  confirmed: 'Confirmed',
  optional: 'Optional',
  skipped: 'Skipped',
}

const STATUS_OPTIONS = [
  { value: 'optional', label: 'Optional' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'completed', label: 'Completed' },
  { value: 'skipped', label: 'Skipped' },
]

function federationNameById(
  federationId: string | undefined,
  library: FederationLibrary | null,
): string | null {
  if (!federationId) return null
  const federation = library?.federations.find(item => item.id === federationId)
  if (!federation) return null
  return federation.abbreviation || federation.name || null
}

export default function CompetitionsPage() {
  const { program, updateCompetitions, migrateLastComp, completeCompetition } = useProgramStore()
  const { library, loadLibrary } = useFederationStore()
  const { pushToast } = useUiStore()
  const { sex } = useSettingsStore()
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [hasChanges, setHasChanges] = useState(false)
  const [showCompleteModal, setShowCompleteModal] = useState<string | null>(null)
  const [completeForm, setCompleteForm] = useState({
    squat_kg: 0,
    bench_kg: 0,
    deadlift_kg: 0,
    body_weight_kg: 0,
  })

  useEffect(() => {
    loadLibrary().catch(console.error)
  }, [loadLibrary])

  useEffect(() => {
    if (program?.competitions) {
      const sorted = [...program.competitions].sort((a, b) => a.date.localeCompare(b.date))
      setCompetitions(sorted)
      setHasChanges(false)
    }
  }, [program])

  useEffect(() => {
    async function checkMigration() {
      const hasCompletedComp = competitions.some((c) => c.status === 'completed')
      if (!hasCompletedComp && program?.meta?.last_comp) {
        try {
          await migrateLastComp()
          pushToast({ message: 'Migrated past competition data', type: 'success' })
        } catch (err) {
          console.error('Migration failed:', err)
        }
      }
    }
    checkMigration()
  }, [])

  const federationOptions = useMemo(() => {
    return (library?.federations ?? [])
      .filter(item => item.status === 'active')
      .map(item => ({
        value: item.id,
        label: item.abbreviation ? `${item.abbreviation} • ${item.name}` : item.name,
      }))
  }, [library])

  function updateComp(date: string, updates: Partial<Competition>) {
    setCompetitions((prev) =>
      prev.map((c) => (c.date === date ? { ...c, ...updates } : c)),
    )
    setHasChanges(true)
  }

  function addCompetition() {
    const today = new Date().toISOString().split('T')[0]
    const newComp: Competition = {
      name: 'New Competition',
      date: today,
      federation: '',
      status: 'optional',
      weight_class_kg: 75,
      counts_toward_federation_ids: [],
      targets: {
        squat_kg: 0,
        bench_kg: 0,
        deadlift_kg: 0,
        total_kg: 0,
      },
      notes: '',
    }
    setCompetitions((prev) => [...prev, newComp])
    setHasChanges(true)
  }

  function removeCompetition(date: string) {
    if (!confirm('Delete this competition?')) return
    setCompetitions((prev) => prev.filter((c) => c.date !== date))
    setHasChanges(true)
  }

  async function handleSave() {
    try {
      const sorted = [...competitions].sort((a, b) => a.date.localeCompare(b.date))
      await updateCompetitions(sorted)
      setHasChanges(false)
      pushToast({ message: 'Competitions saved', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to save competitions', type: 'error' })
    }
  }

  async function handleMarkComplete(date: string) {
    try {
      const results: LiftResults = {
        squat_kg: completeForm.squat_kg,
        bench_kg: completeForm.bench_kg,
        deadlift_kg: completeForm.deadlift_kg,
        total_kg: completeForm.squat_kg + completeForm.bench_kg + completeForm.deadlift_kg,
      }
      await completeCompetition(date, results, completeForm.body_weight_kg)
      setShowCompleteModal(null)
      pushToast({ message: 'Competition marked as completed', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to mark competition as completed', type: 'error' })
    }
  }

  function openCompleteModal(comp: Competition) {
    setCompleteForm({
      squat_kg: comp.targets?.squat_kg || 0,
      bench_kg: comp.targets?.bench_kg || 0,
      deadlift_kg: comp.targets?.deadlift_kg || 0,
      body_weight_kg: comp.body_weight_kg || comp.weight_class_kg,
    })
    setShowCompleteModal(comp.date)
  }

  function calculateDotsScore(comp: Competition): { dots: number; label: string } | null {
    const total = comp.status === 'completed'
      ? comp.results?.total_kg
      : comp.targets?.total_kg

    if (!total) return null

    const bodyweight = comp.body_weight_kg || comp.weight_class_kg
    const dots = calculateDots(total, bodyweight, sex)

    return {
      dots,
      label: comp.status === 'completed' ? 'Actual' : 'Projected',
    }
  }

  const sortedCompetitions = [...competitions].sort((a, b) => a.date.localeCompare(b.date))

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Stack gap={0}>
          <Group gap="xs">
            <Text component={Link} to="/designer" size="sm" c="dimmed" style={{ textDecoration: 'none' }}>
              Designer
            </Text>
            <Text c="dimmed">/</Text>
            <Title order={2}>Competitions</Title>
          </Group>
          <Text c="dimmed" size="sm" mt={4}>
            Track upcoming and past competitions as meet opportunities, including which federations each meet can count toward.
          </Text>
        </Stack>
        <Group gap="sm">
          {hasChanges && (
            <Button
              leftSection={<Save size={16} />}
              onClick={handleSave}
            >
              Save
            </Button>
          )}
          <Button
            variant="default"
            leftSection={<Plus size={16} />}
            onClick={addCompetition}
          >
            Add Competition
          </Button>
        </Group>
      </Group>

      {sortedCompetitions.length > 0 ? (
        <Accordion variant="separated">
          {sortedCompetitions.map((comp) => {
            const dotsResult = calculateDotsScore(comp)
            const trophyColor = comp.status === 'completed' ? 'green'
              : comp.status === 'confirmed' ? 'blue'
              : 'yellow'
            const hostFederationLabel = federationNameById(comp.federation_id, library) || comp.federation || 'No federation'
            const countsTowardLabels = (comp.counts_toward_federation_ids ?? [])
              .map((federationId) => federationNameById(federationId, library))
              .filter((value): value is string => Boolean(value))
            const countsTowardOptions = federationOptions.filter(item => item.value !== comp.federation_id)

            return (
              <Accordion.Item key={comp.date} value={comp.date}>
                <Accordion.Control>
                  <Group gap="sm" wrap="nowrap">
                    <Trophy size={20} style={{ color: `var(--mantine-color-${trophyColor}-6)` }} />
                    <Stack gap={0}>
                      <Text fw={500}>{comp.name}</Text>
                      <Text size="xs" c="dimmed">
                        {new Date(comp.date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                        })}
                        {' \u2022 '}
                        {hostFederationLabel}
                        {countsTowardLabels.length > 0 ? ` • Counts toward ${countsTowardLabels.join(', ')}` : ''}
                      </Text>
                    </Stack>
                  </Group>
                </Accordion.Control>

                <Accordion.Panel>
                  <Stack gap="md">
                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                      <TextInput
                        label="Name"
                        value={comp.name}
                        onChange={(e) => updateComp(comp.date, { name: e.currentTarget.value })}
                      />
                      <DatePickerInput
                        label="Date"
                        value={comp.date}
                        onChange={(d) => {
                          const newDate = d ?? comp.date
                          if (competitions.some((c) => c.date === newDate && c.date !== comp.date)) {
                            pushToast({ message: 'A competition on this date already exists', type: 'error' })
                            return
                          }
                          updateComp(comp.date, { date: newDate })
                        }}
                      />
                      <TextInput
                        label="Federation Label"
                        value={comp.federation}
                        onChange={(e) => updateComp(comp.date, { federation: e.currentTarget.value })}
                      />
                      <Select
                        label="Status"
                        value={comp.status}
                        onChange={(v) => updateComp(comp.date, { status: v as Competition['status'] })}
                        data={STATUS_OPTIONS}
                      />
                    </SimpleGrid>

                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                      <Select
                        clearable
                        searchable
                        label="Host Federation"
                        value={comp.federation_id || null}
                        data={federationOptions}
                        onChange={(value) => {
                          const federation = library?.federations.find(item => item.id === value)
                          updateComp(comp.date, {
                            federation_id: value || undefined,
                            federation: federation?.name ?? comp.federation,
                            counts_toward_federation_ids: (comp.counts_toward_federation_ids ?? []).filter(item => item !== value),
                          })
                        }}
                      />
                      <MultiSelect
                        searchable
                        clearable
                        label="Counts Toward Federations"
                        value={comp.counts_toward_federation_ids ?? []}
                        data={countsTowardOptions}
                        onChange={(value) => updateComp(comp.date, {
                          counts_toward_federation_ids: value.filter(item => item !== comp.federation_id),
                        })}
                        description="Use this when a meet hosted by one federation can satisfy goals for another federation."
                      />
                    </SimpleGrid>

                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                      <NumberInput
                        label="Weight Class (kg)"
                        value={comp.weight_class_kg}
                        onChange={(v) => updateComp(comp.date, { weight_class_kg: Number(v) || 0 })}
                      />
                      {comp.status === 'completed' && (
                        <NumberInput
                          label="Body Weight (kg)"
                          decimalScale={1}
                          value={comp.body_weight_kg || undefined}
                          onChange={(v) => updateComp(comp.date, { body_weight_kg: v ? Number(v) : undefined })}
                        />
                      )}
                      <TextInput
                        label="Location"
                        value={comp.location || ''}
                        onChange={(e) => updateComp(comp.date, { location: e.currentTarget.value })}
                      />
                      <Checkbox
                        mt={30}
                        label="Hotel required"
                        checked={Boolean(comp.hotel_required)}
                        onChange={(event) => updateComp(comp.date, { hotel_required: event.currentTarget.checked })}
                      />
                    </SimpleGrid>

                    <Stack gap="xs">
                      <Text size="xs" c="dimmed">
                        {comp.status === 'completed' ? 'Results (kg)' : 'Targets (kg)'}
                      </Text>
                      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
                        {(['squat_kg', 'bench_kg', 'deadlift_kg', 'total_kg'] as const).map((lift) => (
                          <NumberInput
                            key={lift}
                            label={lift.replace('_kg', '')}
                            value={
                              comp.status === 'completed'
                                ? comp.results?.[lift] || 0
                                : comp.targets?.[lift] || 0
                            }
                            onChange={(value) => {
                              const v = Number(value) || 0
                              const field = comp.status === 'completed' ? 'results' : 'targets'
                              const currentField = comp[field] || {
                                squat_kg: 0,
                                bench_kg: 0,
                                deadlift_kg: 0,
                                total_kg: 0,
                              }
                              const newLifts = {
                                squat_kg: currentField.squat_kg || 0,
                                bench_kg: currentField.bench_kg || 0,
                                deadlift_kg: currentField.deadlift_kg || 0,
                                [lift]: v,
                              }
                              const newTotal = newLifts.squat_kg + newLifts.bench_kg + newLifts.deadlift_kg
                              updateComp(comp.date, {
                                [field]: {
                                  ...currentField,
                                  [lift]: v,
                                  total_kg: newTotal,
                                },
                              })
                            }}
                            disabled={lift === 'total_kg'}
                          />
                        ))}
                      </SimpleGrid>
                    </Stack>

                    {dotsResult && (
                      <Paper bg="var(--mantine-color-default)" p="sm" radius="md">
                        <Stack gap={4}>
                          <Group gap="sm">
                            <Target size={16} style={{ color: 'var(--mantine-color-blue-6)' }} />
                            <Text size="sm">
                              <Text span c="dimmed">{dotsResult.label} DOTS:</Text>{' '}
                              <Text span fw={700} ff="monospace">{dotsResult.dots.toFixed(2)}</Text>
                            </Text>
                          </Group>
                        </Stack>
                      </Paper>
                    )}

                    <Textarea
                      label="Notes"
                      value={comp.notes || ''}
                      onChange={(e) => updateComp(comp.date, { notes: e.currentTarget.value })}
                      rows={3}
                      placeholder="Competition notes..."
                      autosize
                    />

                    <Group>
                      <Badge variant="light" color={STATUS_COLORS[comp.status]}>
                        {STATUS_LABELS[comp.status]}
                      </Badge>
                      <Badge variant="light" color="grape">
                        Host: {hostFederationLabel}
                      </Badge>
                      {countsTowardLabels.length > 0 && (
                        <Badge variant="light" color="blue">
                          Counts toward: {countsTowardLabels.join(', ')}
                        </Badge>
                      )}
                      {dotsResult && (
                        <Text size="sm" ff="monospace">
                          {dotsResult.label}: {dotsResult.dots.toFixed(1)}
                        </Text>
                      )}
                    </Group>

                    <Group justify="space-between" pt="sm">
                      {comp.status !== 'completed' && new Date(comp.date) < new Date() && (
                        <Button
                          variant="light"
                          color="green"
                          size="sm"
                          leftSection={<CheckCircle size={14} />}
                          onClick={() => openCompleteModal(comp)}
                        >
                          Mark as Completed
                        </Button>
                      )}
                      <Button
                        variant="light"
                        color="red"
                        size="sm"
                        ml="auto"
                        leftSection={<Trash2 size={14} />}
                        onClick={() => removeCompetition(comp.date)}
                      >
                        Delete
                      </Button>
                    </Group>
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            )
          })}
        </Accordion>
      ) : (
        <Group justify="center" py={48}>
          <Text c="dimmed">No competitions yet. Click "Add Competition" to get started.</Text>
        </Group>
      )}

      <Modal
        opened={showCompleteModal !== null}
        onClose={() => setShowCompleteModal(null)}
        title="Mark Competition as Completed"
        size="md"
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Enter the actual results from the competition.
          </Text>

          <Stack gap="sm">
            <NumberInput
              label="Squat (kg)"
              value={completeForm.squat_kg}
              onChange={(v) => setCompleteForm((p) => ({ ...p, squat_kg: Number(v) || 0 }))}
            />
            <NumberInput
              label="Bench (kg)"
              value={completeForm.bench_kg}
              onChange={(v) => setCompleteForm((p) => ({ ...p, bench_kg: Number(v) || 0 }))}
            />
            <NumberInput
              label="Deadlift (kg)"
              value={completeForm.deadlift_kg}
              onChange={(v) => setCompleteForm((p) => ({ ...p, deadlift_kg: Number(v) || 0 }))}
            />
            <NumberInput
              label="Body Weight at Weigh-in (kg)"
              decimalScale={1}
              value={completeForm.body_weight_kg}
              onChange={(v) => setCompleteForm((p) => ({ ...p, body_weight_kg: Number(v) || 0 }))}
            />
          </Stack>

          <Group justify="flex-end" gap="sm" pt="sm">
            <Button variant="default" onClick={() => setShowCompleteModal(null)}>
              Cancel
            </Button>
            <Button onClick={() => showCompleteModal && handleMarkComplete(showCompleteModal)}>
              Complete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
