import { useState, useMemo, useEffect } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { displayWeight, toDisplayUnit, fromDisplayUnit, kgToLb } from '@/utils/units'
import { daysUntil, formatDateShort } from '@/utils/dates'
import { clsx } from 'clsx'
import { Plus, Trash2, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import type { WeightEntry } from '@powerlifting/types'
import * as api from '@/api/client'

export default function WeightTracker() {
  const { program, version, addWeightEntry, removeWeightEntry } = useProgramStore()
  const { unit } = useSettingsStore()
  const { pushToast } = useUiStore()

  const [entries, setEntries] = useState<WeightEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [newDate, setNewDate] = useState(new Date().toISOString().split('T')[0])
  const [newWeight, setNewWeight] = useState('')

  // Load weight log
  useEffect(() => {
    async function loadEntries() {
      try {
        const log = await api.fetchWeightLog(version)
        setEntries(log || [])
      } catch (err) {
        console.error('Failed to load weight log:', err)
      } finally {
        setIsLoading(false)
      }
    }
    loadEntries()
  }, [version])

  // Get current body weight and target
  const meta = program?.meta
  const currentBW = meta?.current_body_weight_kg || entries[0]?.kg || 0
  const targetClass = meta?.weight_class_kg || 74
  const confirmBy = meta?.weight_class_confirm_by

  // Calculate weight delta
  const weightDelta = useMemo(() => {
    if (!targetClass || !currentBW) return null
    return {
      kg: parseFloat((currentBW - targetClass).toFixed(2)),
      lb: parseFloat((kgToLb(currentBW - targetClass)).toFixed(1)),
      over: currentBW > targetClass,
    }
  }, [currentBW, targetClass])

  // Calculate rate of change (kg/week)
  const rateOfChange = useMemo(() => {
    if (entries.length < 2) return null
    const sorted = [...entries].sort((a, b) => b.date.localeCompare(a.date))
    const newest = sorted[0]
    const oldest = sorted[sorted.length - 1]
    const daysDiff = Math.abs(new Date(newest.date).getTime() - new Date(oldest.date).getTime()) / (1000 * 60 * 60 * 24)
    if (daysDiff === 0) return null
    const kgDiff = newest.kg - oldest.kg
    return {
      kgPerWeek: parseFloat(((kgDiff / daysDiff) * 7).toFixed(2)),
      losing: kgDiff < 0,
    }
  }, [entries])

  // Peak week estimate
  const peakWeekWeight = useMemo(() => {
    if (!currentBW) return null
    return parseFloat((currentBW * 0.975).toFixed(1))
  }, [currentBW])

  // Days until confirmation
  const daysToConfirm = useMemo(() => {
    if (!confirmBy) return null
    return daysUntil(confirmBy)
  }, [confirmBy])

  // Add entry handler
  const handleAddEntry = async () => {
    if (!newWeight || !newDate) return

    const kg = fromDisplayUnit(Number(newWeight), unit)
    try {
      await api.addWeightEntry(version, { date: newDate, kg })
      setEntries((prev) => [...prev, { date: newDate, kg }].sort((a, b) => b.date.localeCompare(a.date)))
      setNewWeight('')
      pushToast({ message: 'Weight entry added', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to add entry', type: 'error' })
    }
  }

  // Delete entry handler
  const handleDeleteEntry = async (date: string) => {
    try {
      await api.removeWeightEntry(version, date)
      setEntries((prev) => prev.filter((e) => e.date !== date))
      pushToast({ message: 'Entry removed', type: 'success' })
    } catch (err) {
      pushToast({ message: 'Failed to remove entry', type: 'error' })
    }
  }

  // Progress percentage
  const progressPct = useMemo(() => {
    if (!currentBW || !targetClass) return 0
    // If over target, show how far over
    if (currentBW > targetClass) {
      return Math.min(100, ((currentBW - targetClass) / targetClass) * 100)
    }
    // If under target, show how close to ceiling
    return Math.min(100, (currentBW / targetClass) * 100)
  }, [currentBW, targetClass])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold mb-2">Weight Tracker</h2>
        <p className="text-muted-foreground">
          Track body weight progress toward your weight class
        </p>
      </div>

      {/* Progress Card */}
      <div className="bg-card border border-border rounded-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current Weight</p>
            <p className="text-3xl font-bold">{displayWeight(currentBW, unit)}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">Target Class</p>
            <p className="text-3xl font-bold">{targetClass} kg</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="h-4 bg-secondary rounded-full overflow-hidden">
            <div
              className={clsx(
                'h-full transition-all',
                currentBW <= targetClass ? 'bg-primary' : 'bg-destructive'
              )}
              style={{ width: `${Math.min(100, progressPct)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>0</span>
            <span>{displayWeight(targetClass, unit)}</span>
            <span>{displayWeight(targetClass * 1.1, unit)}</span>
          </div>
        </div>

        {/* Delta */}
        {weightDelta && (
          <div className={clsx(
            'flex items-center gap-2 p-3 rounded-md',
            weightDelta.over ? 'bg-destructive/10 text-destructive' : 'bg-primary/10 text-primary'
          )}>
            {weightDelta.over ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )}
            <span className="font-medium">
              {weightDelta.over ? '+' : ''}{displayWeight(Math.abs(weightDelta.kg), unit)} {weightDelta.over ? 'over' : 'under'}
            </span>
          </div>
        )}

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-4 text-center pt-4 border-t border-border">
          <div>
            <p className="text-xs text-muted-foreground">Rate</p>
            <p className={clsx(
              'font-bold',
              rateOfChange?.losing ? 'text-primary' : 'text-destructive'
            )}>
              {rateOfChange ? (
                <>
                  {rateOfChange.losing ? '-' : '+'}{Math.abs(rateOfChange.kgPerWeek).toFixed(2)} kg/wk
                </>
              ) : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Peak Week Est.</p>
            <p className="font-bold">{peakWeekWeight ? displayWeight(peakWeekWeight, unit) : '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Days to Confirm</p>
            <p className={clsx(
              'font-bold',
              daysToConfirm !== null && daysToConfirm < 14 ? 'text-destructive' : ''
            )}>
              {daysToConfirm !== null ? daysToConfirm : '—'}
            </p>
          </div>
        </div>
      </div>

      {/* Add Entry Form */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="font-medium mb-3">Log Weight</h3>
        <div className="flex gap-2">
          <input
            type="date"
            value={newDate}
            onChange={(e) => setNewDate(e.target.value)}
            className="px-3 py-2 border border-border rounded-md bg-background"
          />
          <input
            type="number"
            value={newWeight}
            onChange={(e) => setNewWeight(e.target.value)}
            placeholder={`${unit}`}
            className="flex-1 px-3 py-2 border border-border rounded-md bg-background"
            step={unit === 'kg' ? 0.1 : 0.25}
          />
          <button
            onClick={handleAddEntry}
            disabled={!newWeight || !newDate}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md font-medium disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Weight Log */}
      {entries.length > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b border-border bg-secondary">
            <h3 className="font-medium text-sm">History</h3>
          </div>
          <div className="divide-y divide-border max-h-[300px] overflow-y-auto">
            {entries
              .sort((a, b) => b.date.localeCompare(a.date))
              .slice(0, 20)
              .map((entry) => (
                <div
                  key={entry.date}
                  className="flex items-center justify-between px-4 py-2 hover:bg-accent/50"
                >
                  <div>
                    <p className="font-medium">{formatDateShort(entry.date)}</p>
                    <p className="text-sm text-muted-foreground">{entry.date}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-bold">{displayWeight(entry.kg, unit)}</span>
                    <button
                      onClick={() => handleDeleteEntry(entry.date)}
                      className="p-1 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {entries.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No weight entries yet. Start logging to track progress.
        </div>
      )}
    </div>
  )
}
