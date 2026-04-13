import { useState, useEffect } from 'react'
import { Plus, Trash2, Save, Trophy, Target, CheckCircle } from 'lucide-react'
import {
  Stack, Group, Text, Button, Paper, Badge, Modal, SimpleGrid,
  TextInput, NumberInput, Select, Textarea, Accordion,
} from '@mantine/core'
import { DatePickerInput } from '@mantine/dates'
import { useProgramStore } from '@/store/programStore'
import { useUiStore } from '@/store/uiStore'
import { calculateDots } from '@/utils/dots'
import type { Competition, LiftResults } from '@powerlifting/types'

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

export default function CompetitionsPage() {
  const { program, updateCompetitions, migrateLastComp, completeCompetition } = useProgramStore()
  const { pushToast } = useUiStore()
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
    if (program?.competitions) {
      const sorted = [...program.competitions].sort((a, b) => a.date.localeCompare(b.date))
      setCompetitions(sorted)
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

  function updateComp(date: string, updates: Partial<Competition>) {
    setCompetitions((prev) =>
      prev.map((c) => (c.date === date ? { ...c, ...updates } : c))
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
    const dots = calculateDots(total, bodyweight, 'male')

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
          <Text fw={700} size="xl">Competitions</Text>
          <Text c="dimmed" size="sm">
            Track upcoming and past competitions with DOTS scores
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

      {/* Competition Cards */}
      {sortedCompetitions.length > 0 ? (
        <Accordion variant="separated">
          {sortedCompetitions.map((comp) => {
            const dotsResult = calculateDotsScore(comp)
            const trophyColor = comp.status === 'completed' ? 'green'
              : comp.status === 'confirmed' ? 'blue'
              : 'yellow'

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
                        {comp.federation || 'No federation'}
                      </Text>
                    </Stack>
                  </Group>
                </Accordion.Control>

                <Accordion.Panel>
                  <Stack gap="md">
                    {/* Basic Info */}
                    <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="md">
                      <TextInput
                        label="Name"
                        value={comp.name}
                        onChange={(e) => updateComp(comp.date, { name: e.currentTarget.value })}
                      />
                      <DatePickerInput
                        label="Date"
                        value={new Date(comp.date + 'T00:00:00')}
                        onChange={(d) => {
                          const newDate = d ? d.toISOString().slice(0, 10) : comp.date
                          if (competitions.some((c) => c.date === newDate && c.date !== comp.date)) {
                            pushToast({ message: 'A competition on this date already exists', type: 'error' })
                            return
                          }
                          updateComp(comp.date, { date: newDate })
                        }}
                      />
                      <TextInput
                        label="Federation"
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

                    {/* Weight & Location */}
                    <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
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
                    </SimpleGrid>

                    {/* Lifts (Targets or Results) */}
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

                    {/* DOTS Score */}
                    {dotsResult && (
                      <Paper bg="var(--mantine-color-default)" p="sm" radius="md">
                        <Group gap="sm">
                          <Target size={16} style={{ color: 'var(--mantine-color-blue-6)' }} />
                          <Text size="sm">
                            <Text span c="dimmed">{dotsResult.label} DOTS:</Text>{' '}
                            <Text span fw={700} ff="monospace">{dotsResult.dots.toFixed(2)}</Text>
                          </Text>
                        </Group>
                      </Paper>
                    )}

                    {/* Notes */}
                    <Textarea
                      label="Notes"
                      value={comp.notes || ''}
                      onChange={(e) => updateComp(comp.date, { notes: e.currentTarget.value })}
                      rows={3}
                      placeholder="Competition notes..."
                      autosize
                    />

                    {/* Status badge */}
                    <Group>
                      <Badge variant="light" color={STATUS_COLORS[comp.status]}>
                        {STATUS_LABELS[comp.status]}
                      </Badge>
                      {dotsResult && (
                        <Text size="sm" ff="monospace">
                          {dotsResult.label}: {dotsResult.dots.toFixed(1)}
                        </Text>
                      )}
                    </Group>

                    {/* Actions */}
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

      {/* Complete Competition Modal */}
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
