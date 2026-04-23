import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { fetchWeightLog, updateMetaField, reviewLiftProfile, rewriteLiftProfile, estimateLiftProfileStimulus, type LiftProfileReview } from '@/api/client'
import { daysUntil, sessionsThisCalendarWeek } from '@/utils/dates'
import { displayWeight, toDisplayUnit, fromDisplayUnit } from '@/utils/units'
import { phaseColor } from '@/utils/phases'
import { CalendarDays, Target, Scale, Trophy, TrendingUp, Edit2, Save, X, Plus, Trash2, Download, Dumbbell, Ruler, Sparkles } from 'lucide-react'
import {
  Stack,
  Group,
  Text,
  Paper,
  SimpleGrid,
  Button,
  ActionIcon,
  NumberInput,
  TextInput,
  Textarea,
  SegmentedControl,
  Progress,
  Badge,
  Loader,
  Box,
  Modal,
  Alert,
  Divider,
} from '@mantine/core'
import type { Phase, WeightEntry, LiftProfile } from '@powerlifting/types'

const LIFT_ORDER = ['squat', 'bench', 'deadlift'] as const
const PROFILE_ESTIMATE_READY_SCORE = 55

const LIFT_LABELS: Record<LiftProfile['lift'], string> = {
  squat: 'Squat',
  bench: 'Bench',
  deadlift: 'Deadlift',
}

const LIFT_STYLE_PLACEHOLDERS: Record<LiftProfile['lift'], string> = {
  squat: 'e.g. High bar, hip width stance, knees track over toes, upright torso. Belt squat occasionally for back relief.',
  bench: 'e.g. Close grip for ROM, moderate arch, explosive leg drive, bar slightly below nipples, let bar sink slightly before explode.',
  deadlift: 'e.g. Conventional, double overhand / mixed grip at heavy, slight wedge off floor, lockout hip drive.',
}

const STICKING_PLACEHOLDERS: Record<LiftProfile['lift'], string> = {
  squat: 'e.g. Out of the hole just below parallel, hamstring activation drops',
  bench: 'e.g. Off the chest - initial drive phase, first 2-3 inches',
  deadlift: 'e.g. Below the knee transitioning off the floor, hip-hinge not engaged early enough',
}

const DEFAULT_PROFILE = (lift: LiftProfile['lift']): LiftProfile => ({
  lift,
  style_notes: '',
  sticking_points: '',
  primary_muscle: '',
  volume_tolerance: 'moderate',
  stimulus_coefficient: 1,
})

const normalizeLiftProfile = (profile: LiftProfile): LiftProfile => ({
  ...DEFAULT_PROFILE(profile.lift),
  ...profile,
  stimulus_coefficient: Math.max(1, Math.min(2, profile.stimulus_coefficient ?? 1)),
})

const mergeLiftProfiles = (profiles: LiftProfile[] = []): LiftProfile[] =>
  LIFT_ORDER.map(lift => normalizeLiftProfile(profiles.find(p => p.lift === lift) ?? DEFAULT_PROFILE(lift)))

const coefficientValue = (value: string | number): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.max(1, Math.min(2, value)) : 1

export default function Dashboard() {
  const { program, version, isLoading, updateMaxes, updateBodyWeight, updatePhases, updateLiftProfiles } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [editingMaxes, setEditingMaxes] = useState(false)
  const [editingWeight, setEditingWeight] = useState(false)
  const [editingPhases, setEditingPhases] = useState(false)
  const [editingLiftProfiles, setEditingLiftProfiles] = useState(false)
  const [localMaxes, setLocalMaxes] = useState({ squat: 0, bench: 0, deadlift: 0 })
  const [localWeight, setLocalWeight] = useState(0)
  const [localPhases, setLocalPhases] = useState<Phase[]>([])
  const [localLiftProfiles, setLocalLiftProfiles] = useState<LiftProfile[]>([])
  const [weightLog, setWeightLog] = useState<WeightEntry[]>([])
  const [editingMeasurements, setEditingMeasurements] = useState(false)
  const [localHeight, setLocalHeight] = useState<number | ''>('')
  const [localWingspan, setLocalWingspan] = useState<number | ''>('')
  const [localLegLength, setLocalLegLength] = useState<number | ''>('')
  const [profileGuideOpen, setProfileGuideOpen] = useState(false)
  const [profileGuideDraft, setProfileGuideDraft] = useState<LiftProfile | null>(null)
  const [profileGuideReview, setProfileGuideReview] = useState<LiftProfileReview | null>(null)
  const [profileGuideLoading, setProfileGuideLoading] = useState(false)
  const [profileGuideRewriting, setProfileGuideRewriting] = useState(false)
  const [profileGuideEstimating, setProfileGuideEstimating] = useState(false)

  useEffect(() => {
    if (version) {
      fetchWeightLog(version)
        .then(setWeightLog)
        .catch((e) => console.error('Failed to load weight log:', e))
    }
  }, [version])

  useEffect(() => {
    if (program?.lift_profiles) {
      setLocalLiftProfiles(mergeLiftProfiles(program.lift_profiles))
    } else {
      setLocalLiftProfiles(mergeLiftProfiles())
    }
  }, [program?.lift_profiles])

  if (isLoading || !program) {
    return (
      <Group justify="center" mih="50vh">
        <Loader />
      </Group>
    )
  }

  const { meta, sessions, phases, competitions } = program
  const thisWeekSessions = sessionsThisCalendarWeek(sessions)
  const completedThisWeek = thisWeekSessions.filter((s) => s.completed).length

  const upcomingComps = competitions
    .filter((c) => c.status !== 'skipped' && new Date(c.date) >= new Date())
    .sort((a, b) => a.date.localeCompare(b.date))

  const latestWeightKg = weightLog.length > 0 ? weightLog[0].kg : meta.current_body_weight_kg

  const actualMaxes = { squat: 0, bench: 0, deadlift: 0 }
  for (const session of sessions) {
    if (!session.completed) continue
    if ((session.block || 'current') !== 'current') continue
    for (const exercise of session.exercises) {
      if (exercise.kg == null) continue
      const name = exercise.name.toLowerCase()
      if (name.includes('squat') && exercise.kg > actualMaxes.squat) actualMaxes.squat = exercise.kg
      if (name.includes('bench') && exercise.kg > actualMaxes.bench) actualMaxes.bench = exercise.kg
      if (name.includes('deadlift') && exercise.kg > actualMaxes.deadlift) actualMaxes.deadlift = exercise.kg
    }
  }

  const currentPhase = thisWeekSessions[0]?.phase

  const startEditingMaxes = () => {
    setLocalMaxes({ squat: meta.target_squat_kg, bench: meta.target_bench_kg, deadlift: meta.target_dl_kg })
    setEditingMaxes(true)
  }

  const saveMaxes = async () => {
    try {
      await updateMaxes({ squat_kg: localMaxes.squat, bench_kg: localMaxes.bench, deadlift_kg: localMaxes.deadlift })
      pushToast({ message: 'Target maxes updated', type: 'success' })
      setEditingMaxes(false)
    } catch (err) {
      pushToast({ message: 'Failed to update maxes', type: 'error' })
    }
  }

  const startEditingWeight = () => {
    setLocalWeight(latestWeightKg)
    setEditingWeight(true)
  }

  const saveWeight = async () => {
    try {
      await updateBodyWeight(localWeight)
      pushToast({ message: 'Body weight updated', type: 'success' })
      setEditingWeight(false)
    } catch (err) {
      pushToast({ message: 'Failed to update weight', type: 'error' })
    }
  }

  const startEditingMeasurements = () => {
    setLocalHeight(meta.height_cm ?? '')
    setLocalWingspan(meta.arm_wingspan_cm ?? '')
    setLocalLegLength(meta.leg_length_cm ?? '')
    setEditingMeasurements(true)
  }

  const saveMeasurements = async () => {
    try {
      await Promise.all([
        updateMetaField(version, 'height_cm', localHeight === '' ? null : localHeight),
        updateMetaField(version, 'arm_wingspan_cm', localWingspan === '' ? null : localWingspan),
        updateMetaField(version, 'leg_length_cm', localLegLength === '' ? null : localLegLength),
      ])
      await useProgramStore.getState().loadProgram(version)
      pushToast({ message: 'Measurements updated', type: 'success' })
      setEditingMeasurements(false)
    } catch (err) {
      pushToast({ message: 'Failed to update measurements', type: 'error' })
    }
  }

  const startEditingPhases = () => {
    setLocalPhases([...phases])
    setEditingPhases(true)
  }

  const savePhases = async () => {
    try {
      await updatePhases(localPhases)
      pushToast({ message: 'Phases updated', type: 'success' })
      setEditingPhases(false)
    } catch (err) {
      pushToast({ message: 'Failed to update phases', type: 'error' })
    }
  }

  const updatePhase = (index: number, field: keyof Phase, value: string | number) => {
    setLocalPhases(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], [field]: value }
      return updated
    })
  }

  const addPhase = () => {
    const lastPhase = localPhases[localPhases.length - 1]
    const newStart = lastPhase ? lastPhase.end_week + 1 : 1
    setLocalPhases(prev => [...prev, { name: 'New Phase', intent: '', start_week: newStart, end_week: newStart + 3 }])
  }

  const removePhase = (index: number) => setLocalPhases(prev => prev.filter((_, i) => i !== index))

  const startEditingLiftProfiles = () => {
    setLocalLiftProfiles(mergeLiftProfiles(program?.lift_profiles))
    setEditingLiftProfiles(true)
  }

  const saveLiftProfiles = async () => {
    try {
      await updateLiftProfiles(localLiftProfiles)
      pushToast({ message: 'Lift profiles saved', type: 'success' })
      setEditingLiftProfiles(false)
    } catch (err) {
      pushToast({ message: 'Failed to save lift profiles', type: 'error' })
    }
  }

  const updateLocalProfile = (lift: LiftProfile['lift'], updates: Partial<LiftProfile>) => {
    setLocalLiftProfiles(prev =>
      prev.map(p => p.lift === lift ? { ...p, ...updates } : p)
    )
  }

  const reviewProfileDraft = async (profile: LiftProfile) => {
    setProfileGuideLoading(true)
    try {
      const review = await reviewLiftProfile(profile)
      setProfileGuideReview(review)
    } catch (err) {
      pushToast({ message: 'AI profile review failed', type: 'error' })
    } finally {
      setProfileGuideLoading(false)
    }
  }

  const openProfileGuide = async (profile: LiftProfile) => {
    const merged = mergeLiftProfiles(localLiftProfiles.length ? localLiftProfiles : program?.lift_profiles)
    const draft = normalizeLiftProfile(merged.find(p => p.lift === profile.lift) ?? profile)
    const shouldAutoReview = Math.abs((draft.stimulus_coefficient ?? 1) - 1) < 0.001
    setLocalLiftProfiles(merged)
    setEditingLiftProfiles(true)
    setProfileGuideDraft(draft)
    setProfileGuideReview(null)
    setProfileGuideOpen(true)
    if (shouldAutoReview) {
      await reviewProfileDraft(draft)
    }
  }

  const updateProfileGuideDraft = (updates: Partial<LiftProfile>) => {
    setProfileGuideDraft(prev => prev ? { ...prev, ...updates } : prev)
  }

  const runProfileGuideReview = async () => {
    if (!profileGuideDraft) return
    await reviewProfileDraft(profileGuideDraft)
  }

  const runRewriteProfile = async () => {
    if (!profileGuideDraft) return
    setProfileGuideRewriting(true)
    try {
      const result = await rewriteLiftProfile(profileGuideDraft)
      const updated = normalizeLiftProfile({ ...profileGuideDraft, ...result })
      setProfileGuideDraft(updated)
      updateLocalProfile(updated.lift, updated)
      await reviewProfileDraft(updated)
      pushToast({ message: 'Lift profile rewritten', type: 'success' })
    } catch (err) {
      pushToast({ message: 'AI rewrite failed', type: 'error' })
    } finally {
      setProfileGuideRewriting(false)
    }
  }

  const runEstimateStimulus = async () => {
    if (!profileGuideDraft) return
    const score = profileGuideReview?.completeness_score ?? 0
    if (score < PROFILE_ESTIMATE_READY_SCORE) {
      pushToast({ message: `Profile score needs ${PROFILE_ESTIMATE_READY_SCORE}% before estimating stimulus`, type: 'error' })
      return
    }
    setProfileGuideEstimating(true)
    try {
      const result = await estimateLiftProfileStimulus(profileGuideDraft)
      const updated = normalizeLiftProfile({
        ...profileGuideDraft,
        stimulus_coefficient: result.stimulus_coefficient,
        stimulus_coefficient_confidence: result.stimulus_coefficient_confidence,
        stimulus_coefficient_reasoning: result.stimulus_coefficient_reasoning,
        stimulus_coefficient_updated_at: result.stimulus_coefficient_updated_at,
      })
      setProfileGuideDraft(updated)
      updateLocalProfile(updated.lift, updated)
      pushToast({ message: 'Stimulus coefficient applied', type: 'success' })
    } catch (err) {
      pushToast({ message: 'AI stimulus estimate failed', type: 'error' })
    } finally {
      setProfileGuideEstimating(false)
    }
  }

  const applyProfileGuide = () => {
    if (!profileGuideDraft) return
    updateLocalProfile(profileGuideDraft.lift, profileGuideDraft)
    setProfileGuideOpen(false)
    pushToast({ message: 'Profile staged. Save lift profiles to persist it.', type: 'success' })
  }

  const displayProfiles = (program?.lift_profiles?.length
    ? mergeLiftProfiles(program.lift_profiles)
    : mergeLiftProfiles()
  )
  const profileGuideScore = profileGuideReview?.completeness_score ?? 0
  const profileGuideCanEstimate = profileGuideScore >= PROFILE_ESTIMATE_READY_SCORE

  return (
    <Stack gap={24}>
      <Group justify="space-between">
        <Text fz="h1" fw={700}>Dashboard</Text>
        <Button
          component="a"
          href="/api/export/xlsx"
          download="program_history.xlsx"
          leftSection={<Download size={16} />}
          size="sm"
        >
          Export Excel
        </Button>
      </Group>

      {/* Stats Grid */}
      <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="md">
        {/* Upcoming Competitions */}
        {upcomingComps.length > 0 && (
          <Paper withBorder p="md">
            <Group gap="xs" mb="sm">
              <Trophy size={20} />
              <Text fw={500}>Upcoming Competitions</Text>
            </Group>
            <Stack gap="xs">
              {upcomingComps.map((comp) => (
                <Group key={comp.date} justify="space-between">
                  <Group gap="xs" style={{ minWidth: 0 }}>
                    <Badge
                      variant="light"
                      color={comp.status === 'confirmed' ? 'green' : 'yellow'}
                      size="sm"
                    >
                      {comp.status}
                    </Badge>
                    <Text size="sm" truncate>{comp.name}</Text>
                  </Group>
                  <Text size="sm" fw={500} ml="xs">{daysUntil(comp.date)}d</Text>
                </Group>
              ))}
            </Stack>
          </Paper>
        )}

        {/* Target Maxes */}
        <Paper withBorder p="md">
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <Target size={20} />
              <Text fw={500}>Target Maxes</Text>
            </Group>
            {editingMaxes ? (
              <Group gap={4}>
                <ActionIcon variant="subtle" color="blue" onClick={saveMaxes}><Save size={16} /></ActionIcon>
                <ActionIcon variant="subtle" onClick={() => setEditingMaxes(false)}><X size={16} /></ActionIcon>
              </Group>
            ) : (
              <ActionIcon variant="subtle" onClick={startEditingMaxes}><Edit2 size={16} /></ActionIcon>
            )}
          </Group>
          {editingMaxes ? (
            <Stack gap="xs">
              {(['squat', 'bench', 'deadlift'] as const).map((lift) => (
                <Group key={lift} gap="xs">
                  <Text size="sm" w={64} tt="capitalize">{lift}</Text>
                  <NumberInput
                    style={{ flex: 1 }}
                    value={toDisplayUnit(localMaxes[lift], unit)}
                    onChange={(v) => setLocalMaxes(prev => ({ ...prev, [lift]: fromDisplayUnit(typeof v === 'number' ? v : 0, unit) }))}
                    decimalScale={1}
                    size="sm"
                  />
                  <Text size="xs" c="dimmed">{unit}</Text>
                </Group>
              ))}
              <Group justify="space-between" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }} pt={4} mt={4}>
                <Text size="sm" fw={500}>Total</Text>
                <Text size="sm" fw={700}>{displayWeight(localMaxes.squat + localMaxes.bench + localMaxes.deadlift, unit)}</Text>
              </Group>
            </Stack>
          ) : (
            <Stack gap={4}>
              <Group justify="space-between"><Text size="sm">Squat</Text><Text size="sm" fw={500}>{displayWeight(meta.target_squat_kg, unit)}</Text></Group>
              <Group justify="space-between"><Text size="sm">Bench</Text><Text size="sm" fw={500}>{displayWeight(meta.target_bench_kg, unit)}</Text></Group>
              <Group justify="space-between"><Text size="sm">Deadlift</Text><Text size="sm" fw={500}>{displayWeight(meta.target_dl_kg, unit)}</Text></Group>
              <Group justify="space-between" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }} pt={4} mt={4}>
                <Text size="sm" fw={500}>Total</Text>
                <Text size="sm" fw={700}>{displayWeight(meta.target_total_kg, unit)}</Text>
              </Group>
            </Stack>
          )}
        </Paper>

        {/* Actual Maxes */}
        {(actualMaxes.squat > 0 || actualMaxes.bench > 0 || actualMaxes.deadlift > 0) && (
          <Paper withBorder p="md">
            <Group gap="xs" mb="sm">
              <TrendingUp size={20} />
              <Text fw={500}>Actual Maxes</Text>
            </Group>
            <Stack gap="xs">
              {[
                { label: 'Squat', actual: actualMaxes.squat, target: meta.target_squat_kg },
                { label: 'Bench', actual: actualMaxes.bench, target: meta.target_bench_kg },
                { label: 'Deadlift', actual: actualMaxes.deadlift, target: meta.target_dl_kg },
              ].map(({ label, actual, target }) =>
                actual > 0 ? (
                  <Box key={label}>
                    <Group justify="space-between" mb={2}>
                      <Text size="sm">{label}: {displayWeight(actual, unit)}</Text>
                      <Text size="sm" c="dimmed">Target: {displayWeight(target, unit)}</Text>
                    </Group>
                    <Progress
                      value={Math.min(100, (actual / target) * 100)}
                      color={actual >= target ? 'green' : 'blue'}
                      size="sm"
                    />
                  </Box>
                ) : null
              )}
              {(actualMaxes.squat > 0 || actualMaxes.bench > 0 || actualMaxes.deadlift > 0) && (
                <Group justify="space-between" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }} pt={4} mt={4}>
                  <Text size="sm" fw={500}>Total</Text>
                  <Text size="sm" fw={700}>{displayWeight(actualMaxes.squat + actualMaxes.bench + actualMaxes.deadlift, unit)}</Text>
                </Group>
              )}
            </Stack>
          </Paper>
        )}

        {/* Body Weight */}
        <Paper withBorder p="md">
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <Scale size={20} />
              <Text fw={500}>Body Weight</Text>
            </Group>
            {editingWeight ? (
              <Group gap={4}>
                <ActionIcon variant="subtle" color="blue" onClick={saveWeight}><Save size={16} /></ActionIcon>
                <ActionIcon variant="subtle" onClick={() => setEditingWeight(false)}><X size={16} /></ActionIcon>
              </Group>
            ) : (
              <ActionIcon variant="subtle" onClick={startEditingWeight}><Edit2 size={16} /></ActionIcon>
            )}
          </Group>
          {editingWeight ? (
            <Group gap="xs">
              <NumberInput
                style={{ flex: 1 }}
                value={toDisplayUnit(localWeight, unit)}
                onChange={(v) => setLocalWeight(fromDisplayUnit(typeof v === 'number' ? v : 0, unit))}
                decimalScale={1}
                size="lg"
                fw={700}
              />
              <Text size="sm" c="dimmed">{unit}</Text>
            </Group>
          ) : (
            <Text fz="h1" fw={700}>{displayWeight(latestWeightKg, unit)}</Text>
          )}
          <Text size="sm" c="dimmed">Target: {meta.weight_class_kg} kg class</Text>
          <Progress
            value={Math.min(100, (latestWeightKg / meta.weight_class_kg) * 100)}
            mt="sm"
            size="md"
          />
        </Paper>

        {/* Anthropometrics */}
        <Paper withBorder p="md">
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <Ruler size={20} />
              <Text fw={500}>Anthropometrics</Text>
            </Group>
            {editingMeasurements ? (
              <Group gap={4}>
                <ActionIcon variant="subtle" color="blue" onClick={saveMeasurements}><Save size={16} /></ActionIcon>
                <ActionIcon variant="subtle" onClick={() => setEditingMeasurements(false)}><X size={16} /></ActionIcon>
              </Group>
            ) : (
              <ActionIcon variant="subtle" onClick={startEditingMeasurements}><Edit2 size={16} /></ActionIcon>
            )}
          </Group>
          {editingMeasurements ? (
            <Stack gap="xs">
              <Group gap="xs">
                <Text size="sm" w={96}>Height</Text>
                <NumberInput
                  style={{ flex: 1 }}
                  value={localHeight}
                  onChange={(v) => setLocalHeight(typeof v === 'number' ? v : '')}
                  decimalScale={1}
                  placeholder="--"
                  size="sm"
                />
                <Text size="xs" c="dimmed">cm</Text>
              </Group>
              <Group gap="xs">
                <Text size="sm" w={96}>Arm Wingspan</Text>
                <NumberInput
                  style={{ flex: 1 }}
                  value={localWingspan}
                  onChange={(v) => setLocalWingspan(typeof v === 'number' ? v : '')}
                  decimalScale={1}
                  placeholder="--"
                  size="sm"
                />
                <Text size="xs" c="dimmed">cm</Text>
              </Group>
              <Group gap="xs">
                <Text size="sm" w={96}>Leg Length</Text>
                <NumberInput
                  style={{ flex: 1 }}
                  value={localLegLength}
                  onChange={(v) => setLocalLegLength(typeof v === 'number' ? v : '')}
                  decimalScale={1}
                  placeholder="--"
                  size="sm"
                />
                <Text size="xs" c="dimmed">cm</Text>
              </Group>
            </Stack>
          ) : (
            <Stack gap={4}>
              <Group justify="space-between">
                <Text size="sm">Height</Text>
                <Text size="sm" fw={500}>{meta.height_cm ? `${meta.height_cm} cm` : 'Not set'}</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Arm Wingspan</Text>
                <Text size="sm" fw={500}>{meta.arm_wingspan_cm ? `${meta.arm_wingspan_cm} cm` : 'Not set'}</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Leg Length</Text>
                <Text size="sm" fw={500}>{meta.leg_length_cm ? `${meta.leg_length_cm} cm` : 'Not set'}</Text>
              </Group>
            </Stack>
          )}
        </Paper>

        {/* This Week */}
        <Paper withBorder p="md">
          <Group gap="xs" mb="sm">
            <CalendarDays size={20} />
            <Text fw={500}>This Week</Text>
          </Group>
          <Text fz="h1" fw={700}>{completedThisWeek}/{thisWeekSessions.length}</Text>
          <Text size="sm" c="dimmed">sessions completed</Text>
        </Paper>

        {/* Current Phase */}
        {currentPhase && (
          <Paper withBorder p="md">
            <Group gap="xs" mb="sm">
              <TrendingUp size={20} />
              <Text fw={500}>Current Phase</Text>
            </Group>
            <Group gap="xs">
              <Box w={12} h={12} style={{ borderRadius: '50%', backgroundColor: phaseColor(currentPhase, phases) }} />
              <Text fw={500}>{currentPhase.name}</Text>
            </Group>
            <Text size="sm" c="dimmed" mt={4}>{currentPhase.intent}</Text>
          </Paper>
        )}

        {/* Program Phases */}
        <Paper withBorder p="md">
          <Group justify="space-between" mb="sm">
            <Group gap="xs">
              <TrendingUp size={20} />
              <Text fw={500}>Program Phases</Text>
            </Group>
            {editingPhases ? (
              <Group gap={4}>
                <ActionIcon variant="subtle" color="blue" onClick={addPhase}><Plus size={16} /></ActionIcon>
                <ActionIcon variant="subtle" color="blue" onClick={savePhases}><Save size={16} /></ActionIcon>
                <ActionIcon variant="subtle" onClick={() => setEditingPhases(false)}><X size={16} /></ActionIcon>
              </Group>
            ) : (
              <ActionIcon variant="subtle" onClick={startEditingPhases}><Edit2 size={16} /></ActionIcon>
            )}
          </Group>
          {editingPhases ? (
            <Stack gap="xs">
              {localPhases.map((phase, idx) => (
                <Group key={idx} gap="xs" p="xs" style={{ backgroundColor: 'var(--mantine-color-default)', borderRadius: 'var(--mantine-radius-sm)' }}>
                  <Box w={12} h={12} style={{ borderRadius: '50%', backgroundColor: phaseColor(phase, localPhases) }} />
                  <TextInput
                    style={{ flex: 1 }}
                    value={phase.name}
                    onChange={(e) => updatePhase(idx, 'name', e.currentTarget.value)}
                    placeholder="Phase name"
                    size="xs"
                  />
                  <NumberInput
                    w={48}
                    value={phase.start_week}
                    onChange={(v) => updatePhase(idx, 'start_week', typeof v === 'number' ? v : 0)}
                    size="xs"
                    ta="center"
                    hideControls
                  />
                  <Text size="xs">-</Text>
                  <NumberInput
                    w={48}
                    value={phase.end_week}
                    onChange={(v) => updatePhase(idx, 'end_week', typeof v === 'number' ? v : 0)}
                    size="xs"
                    ta="center"
                    hideControls
                  />
                  <ActionIcon variant="subtle" color="red" onClick={() => removePhase(idx)}><Trash2 size={12} /></ActionIcon>
                </Group>
              ))}
            </Stack>
          ) : (
            <Stack gap={4}>
              {phases.map((phase, idx) => (
                <Group key={idx} gap="xs">
                  <Box w={12} h={12} style={{ borderRadius: '50%', backgroundColor: phaseColor(phase, phases) }} />
                  <Text size="sm">W{phase.start_week}-W{phase.end_week}: {phase.name}</Text>
                </Group>
              ))}
            </Stack>
          )}
        </Paper>
      </SimpleGrid>

      {/* Lift Profiles Section */}
      <Paper withBorder p="md">
        <Group justify="space-between" mb="md">
          <Group gap="xs">
            <Dumbbell size={20} />
            <Text fw={500}>Lift Style Profiles</Text>
          </Group>
          <Group gap={4}>
            {LIFT_ORDER.map((lift) => (
              <Button
                key={lift}
                component={Link}
                to={`/lift-profiles/${lift}`}
                variant="subtle"
                size="compact-sm"
                leftSection={<Edit2 size={14} />}
              >
                {LIFT_LABELS[lift]}
              </Button>
            ))}
          </Group>
        </Group>

        {editingLiftProfiles ? (
          <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="lg">
            {localLiftProfiles.map((profile) => (
              <Stack key={profile.lift} gap="sm" style={{ minWidth: 0 }}>
                <Group justify="space-between" align="center" style={{ borderBottom: '1px solid var(--mantine-color-default-border)', paddingBottom: 4 }}>
                  <Text size="sm" fw={500} tt="capitalize">{LIFT_LABELS[profile.lift]}</Text>
                  <Button
                    component={Link}
                    to={`/lift-profiles/${profile.lift}`}
                    variant="subtle"
                    size="compact-xs"
                    leftSection={<Sparkles size={12} />}
                  >
                    Open Profile
                  </Button>
                </Group>

                {/* Style Notes */}
                <Stack gap={4}>
                  <Text size="xs" c="dimmed">Style & Setup</Text>
                  <Textarea
                    rows={2}
                    value={profile.style_notes}
                    onChange={(e) => updateLocalProfile(profile.lift, { style_notes: e.currentTarget.value })}
                    placeholder={LIFT_STYLE_PLACEHOLDERS[profile.lift]}
                    size="xs"
                    styles={{ input: { maxWidth: '100%', minWidth: 0, width: '100%', overflowY: 'auto', resize: 'vertical' } }}
                  />
                </Stack>

                {/* Sticking Points */}
                <Stack gap={4}>
                  <Text size="xs" c="dimmed">Sticking Points</Text>
                  <Textarea
                    rows={2}
                    value={profile.sticking_points}
                    onChange={(e) => updateLocalProfile(profile.lift, { sticking_points: e.currentTarget.value })}
                    placeholder={STICKING_PLACEHOLDERS[profile.lift]}
                    size="xs"
                    styles={{ input: { maxWidth: '100%', minWidth: 0, width: '100%', overflowY: 'auto', resize: 'vertical' } }}
                  />
                </Stack>

                {/* Primary Muscle */}
                <Stack gap={4}>
                  <Text size="xs" c="dimmed">Primary Muscle Driving the Lift</Text>
                  <TextInput
                    value={profile.primary_muscle}
                    onChange={(e) => updateLocalProfile(profile.lift, { primary_muscle: e.currentTarget.value })}
                    placeholder={profile.lift === 'squat' ? 'e.g. Quad dominant' : profile.lift === 'bench' ? 'e.g. Tricep dominant' : 'e.g. Glute dominant'}
                    size="xs"
                  />
                </Stack>

                {/* Volume Tolerance */}
                <Stack gap={4}>
                  <Text size="xs" c="dimmed">Volume Recovery Tolerance</Text>
                  <SegmentedControl
                    fullWidth
                    size="xs"
                    data={[
                      { label: 'Low', value: 'low' },
                      { label: 'Moderate', value: 'moderate' },
                      { label: 'High', value: 'high' },
                    ]}
                    value={profile.volume_tolerance}
                    onChange={(v) => updateLocalProfile(profile.lift, { volume_tolerance: v as 'low' | 'moderate' | 'high' })}
                  />
                </Stack>

                <Stack gap={4}>
                  <Text size="xs" c="dimmed">Stimulus Coefficient</Text>
                  <NumberInput
                    min={1}
                    max={2}
                    step={0.05}
                    decimalScale={2}
                    value={profile.stimulus_coefficient ?? 1}
                    onChange={(v) => updateLocalProfile(profile.lift, { stimulus_coefficient: coefficientValue(v) })}
                    size="xs"
                  />
                  {profile.stimulus_coefficient_reasoning && (
                    <Text size="xs" c="dimmed" lineClamp={3}>{profile.stimulus_coefficient_reasoning}</Text>
                  )}
                </Stack>
              </Stack>
            ))}
          </SimpleGrid>
        ) : (
          <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="md">
            {displayProfiles.map((profile) => {
              const hasData = profile.style_notes || profile.sticking_points || profile.primary_muscle
              return (
                <Stack key={profile.lift} gap="xs" style={{ minWidth: 0 }}>
                  <Text size="sm" fw={500} tt="capitalize" style={{ borderBottom: '1px solid var(--mantine-color-default-border)', paddingBottom: 4 }}>{LIFT_LABELS[profile.lift]}</Text>
                  {hasData ? (
                    <>
                      {profile.style_notes && (
                        <div>
                          <Text size="xs" c="dimmed" mb={2}>Style</Text>
                          <Text size="xs" style={{ lineHeight: 1.6 }}>{profile.style_notes}</Text>
                        </div>
                      )}
                      {profile.sticking_points && (
                        <div>
                          <Text size="xs" c="dimmed" mb={2}>Sticking Points</Text>
                          <Text size="xs" c="orange" style={{ lineHeight: 1.6 }}>{profile.sticking_points}</Text>
                        </div>
                      )}
                      {profile.primary_muscle && (
                        <div>
                          <Text size="xs" c="dimmed" mb={2}>Primary Driver</Text>
                          <Text size="xs" fw={500}>{profile.primary_muscle}</Text>
                        </div>
                      )}
                      <Badge
                        variant="light"
                        color={profile.volume_tolerance === 'low' ? 'red' : profile.volume_tolerance === 'moderate' ? 'yellow' : 'green'}
                        size="sm"
                        tt="capitalize"
                      >
                        {profile.volume_tolerance} volume tolerance
                      </Badge>
                      <Badge variant="light" color="blue" size="sm">
                        Stimulus x{(profile.stimulus_coefficient ?? 1).toFixed(2)}
                      </Badge>
                    </>
                  ) : (
                    <Text size="xs" c="dimmed" fs="italic">No profile yet - click edit to add</Text>
                  )}
                </Stack>
              )
            })}
          </SimpleGrid>
        )}
      </Paper>

      <Modal
        opened={profileGuideOpen}
        onClose={() => setProfileGuideOpen(false)}
        title={profileGuideDraft ? `${LIFT_LABELS[profileGuideDraft.lift]} Lift Profile` : 'Lift Profile'}
        size="lg"
      >
        {profileGuideDraft && (
          <Stack gap="md">
            {profileGuideReview && (
              <Alert
                variant="light"
                color={profileGuideCanEstimate ? 'green' : 'yellow'}
                icon={<Sparkles size={16} />}
              >
                <Group justify="space-between" align="center" mb={(profileGuideReview.missing_details ?? []).length ? 'xs' : 0}>
                  <Text fw={500}>Profile score {profileGuideReview.completeness_score}%</Text>
                  <Badge color={profileGuideCanEstimate ? 'green' : 'yellow'} variant="light">
                    {profileGuideCanEstimate ? 'Estimate ready' : `Needs ${PROFILE_ESTIMATE_READY_SCORE}%`}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed" mb="xs">
                  {profileGuideReview.score_explanation ?? 'Score is 0-100 completeness for estimating a lift-specific INOL stimulus coefficient.'}
                </Text>
                {profileGuideReview.score_breakdown && (
                  <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xs" mb="xs">
                    {Object.entries(profileGuideReview.score_breakdown).map(([key, part]) => (
                      <Paper key={key} withBorder p="xs">
                        <Text size="xs" fw={500} tt="capitalize">{key.replaceAll('_', ' ')}</Text>
                        <Text size="sm" fw={700}>{part.score}/{part.max}</Text>
                        {(part.notes ?? []).slice(0, 2).map((note) => (
                          <Text key={note} size="xs" c="dimmed">{note}</Text>
                        ))}
                      </Paper>
                    ))}
                  </SimpleGrid>
                )}
                {(profileGuideReview.missing_details ?? []).length > 0 && (
                  <Stack gap={4}>
                    {(profileGuideReview.missing_details ?? []).map((detail) => (
                      <Text key={detail} size="xs">{detail}</Text>
                    ))}
                  </Stack>
                )}
                {(profileGuideReview.suggestions ?? []).length > 0 && (
                  <Stack gap={4} mt="xs">
                    {(profileGuideReview.suggestions ?? []).map((suggestion) => (
                      <Text key={suggestion} size="xs" c="dimmed">{suggestion}</Text>
                    ))}
                  </Stack>
                )}
              </Alert>
            )}

            <Textarea
              label="Style & Setup"
              rows={3}
              value={profileGuideDraft.style_notes}
              onChange={(e) => updateProfileGuideDraft({ style_notes: e.currentTarget.value })}
              placeholder={LIFT_STYLE_PLACEHOLDERS[profileGuideDraft.lift]}
              styles={{ input: { maxWidth: '100%', minWidth: 0, width: '100%', maxHeight: '28vh', overflowY: 'auto', resize: 'vertical' } }}
            />

            <Textarea
              label="Sticking Points"
              rows={2}
              value={profileGuideDraft.sticking_points}
              onChange={(e) => updateProfileGuideDraft({ sticking_points: e.currentTarget.value })}
              placeholder={STICKING_PLACEHOLDERS[profileGuideDraft.lift]}
              styles={{ input: { maxWidth: '100%', minWidth: 0, width: '100%', maxHeight: '24vh', overflowY: 'auto', resize: 'vertical' } }}
            />

            <TextInput
              label="Primary Muscle Driver"
              value={profileGuideDraft.primary_muscle}
              onChange={(e) => updateProfileGuideDraft({ primary_muscle: e.currentTarget.value })}
              placeholder={profileGuideDraft.lift === 'squat' ? 'Quad dominant' : profileGuideDraft.lift === 'bench' ? 'Tricep dominant' : 'Glute dominant'}
            />

            <Group grow align="flex-end">
              <SegmentedControl
                fullWidth
                data={[
                  { label: 'Low', value: 'low' },
                  { label: 'Moderate', value: 'moderate' },
                  { label: 'High', value: 'high' },
                ]}
                value={profileGuideDraft.volume_tolerance}
                onChange={(v) => updateProfileGuideDraft({ volume_tolerance: v as 'low' | 'moderate' | 'high' })}
              />
              <NumberInput
                label="Stimulus Coefficient"
                min={1}
                max={2}
                step={0.05}
                decimalScale={2}
                value={profileGuideDraft.stimulus_coefficient ?? 1}
                onChange={(v) => updateProfileGuideDraft({ stimulus_coefficient: coefficientValue(v) })}
              />
            </Group>

            {profileGuideDraft.stimulus_coefficient_reasoning && (
              <Alert variant="light" color="blue">
                <Text size="sm">{profileGuideDraft.stimulus_coefficient_reasoning}</Text>
                {profileGuideDraft.stimulus_coefficient_confidence && (
                  <Badge mt="xs" variant="light" color="blue">
                    {profileGuideDraft.stimulus_coefficient_confidence} confidence
                  </Badge>
                )}
              </Alert>
            )}

            <Divider />

            <Text size="xs" c="dimmed">
              Estimate unlocks at {PROFILE_ESTIMATE_READY_SCORE}% profile score. Rewrite only cleans the text; estimate only applies the stimulus coefficient.
            </Text>

            <Group justify="space-between" gap="sm">
              <Button
                variant="light"
                leftSection={<Sparkles size={16} />}
                loading={profileGuideLoading}
                onClick={runProfileGuideReview}
              >
                Review
              </Button>
              <Group gap="sm">
                <Button
                  variant="light"
                  leftSection={<Sparkles size={16} />}
                  loading={profileGuideRewriting}
                  onClick={runRewriteProfile}
                >
                  Rewrite
                </Button>
                <Button
                  variant="light"
                  leftSection={<Sparkles size={16} />}
                  loading={profileGuideEstimating}
                  disabled={!profileGuideCanEstimate}
                  onClick={runEstimateStimulus}
                >
                  Estimate Stimulus
                </Button>
                <Button onClick={applyProfileGuide}>Apply</Button>
              </Group>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  )
}
