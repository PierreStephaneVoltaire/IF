import { create } from 'zustand'
import type { Program, Session, Exercise, MaxEntry, WeightEntry, ProgramListItem, SupplementPhase, DietNote, Competition, SessionVideo, LiftResults } from '@powerlifting/types'
import * as api from '@/api/client'

interface ProgramState {
  program: Program | null
  version: string
  versions: ProgramListItem[]
  isLoading: boolean
  error: string | null
  isDirty: boolean
  activeSessionDate: string | null

  // Actions
  loadProgram: (version: string) => Promise<void>
  loadVersions: () => Promise<void>
  setActiveSession: (date: string | null) => void
  createSession: (session: Partial<Session> & { date: string }) => Promise<void>
  deleteSession: (date: string) => Promise<void>
  updateSession: (date: string, session: Session) => void
  updateExercise: (
    date: string,
    exerciseIndex: number,
    field: keyof Exercise,
    value: unknown
  ) => void
  addExercise: (date: string, exercise: Exercise) => void
  removeExercise: (date: string, exerciseIndex: number) => void
  rescheduleSession: (oldDate: string, newDate: string, newDay: string) => Promise<void>
  markComplete: (
    date: string,
    data: { rpe?: number; bodyWeightKg?: number; notes?: string }
  ) => Promise<void>
  saveSession: (date: string) => Promise<void>
  updateMaxes: (maxes: {
    squat_kg: number
    bench_kg: number
    deadlift_kg: number
  }) => Promise<void>
  updateBodyWeight: (weightKg: number) => Promise<void>
  updatePhases: (phases: Phase[]) => Promise<void>
  addWeightEntry: (entry: WeightEntry) => Promise<void>
  removeWeightEntry: (date: string) => Promise<void>
  forkVersion: (label?: string) => Promise<string>
  reset: () => void

  // Supplements
  updateSupplementPhases: (phases: SupplementPhase[]) => Promise<void>

  // Diet Notes
  updateDietNotes: (dietNotes: DietNote[]) => Promise<void>

  // Competitions
  updateCompetitions: (competitions: Competition[]) => Promise<void>
  migrateLastComp: () => Promise<void>
  completeCompetition: (date: string, results: LiftResults, bodyWeightKg: number) => Promise<void>

  // Videos
  removeSessionVideo: (sessionDate: string, videoId: string) => void
}

export const useProgramStore = create<ProgramState>((set, get) => ({
  program: null,
  version: 'current',
  versions: [],
  isLoading: false,
  error: null,
  isDirty: false,
  activeSessionDate: null,

  loadProgram: async (version) => {
    set({ isLoading: true, error: null })
    try {
      const program = await api.fetchProgram(version)
      set({ program, version, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false })
    }
  },

  loadVersions: async () => {
    try {
      const versions = await api.fetchPrograms()
      // Sort by version number descending (newest first)
      versions.sort((a, b) => b.version.localeCompare(a.version))
      set({ versions })
    } catch (e) {
      console.error('Failed to load versions:', e)
    }
  },

  setActiveSession: (date) => set({ activeSessionDate: date }),

  createSession: async (sessionData) => {
    const { version } = get()
    const newSession = await api.createSession(version, sessionData)

    // Reload program to get updated sessions with derived fields
    await get().loadProgram(version)
    return newSession
  },

  deleteSession: async (date) => {
    const { version } = get()
    await api.deleteSession(version, date)

    // Update local state
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.filter((s) => s.date !== date)
      return { program: { ...state.program, sessions } }
    })
  },

  updateSession: (date, session) =>
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) =>
        s.date === date ? session : s
      )
      return { program: { ...state.program, sessions }, isDirty: true }
    }),

  updateExercise: (date, exerciseIndex, field, value) =>
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) => {
        if (s.date !== date) return s
        const exercises = [...s.exercises]
        ;(exercises[exerciseIndex] as any)[field] = value
        return { ...s, exercises }
      })
      return { program: { ...state.program, sessions }, isDirty: true }
    }),

  addExercise: (date, exercise) =>
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) => {
        if (s.date !== date) return s
        return { ...s, exercises: [...s.exercises, exercise] }
      })
      return { program: { ...state.program, sessions }, isDirty: true }
    }),

  removeExercise: (date, exerciseIndex) =>
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) => {
        if (s.date !== date) return s
        const exercises = s.exercises.filter((_, i) => i !== exerciseIndex)
        return { ...s, exercises }
      })
      return { program: { ...state.program, sessions }, isDirty: true }
    }),

  rescheduleSession: async (oldDate, newDate, newDay) => {
    const { version, program } = get()
    if (!program) return

    await api.rescheduleSession(version, oldDate, newDate, newDay)

    // Update local state
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) =>
        s.date === oldDate ? { ...s, date: newDate, day: newDay } : s
      )
      return { program: { ...state.program, sessions } }
    })
  },

  markComplete: async (date, data) => {
    const { version } = get()
    await api.completeSession(version, date, data)

    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) =>
        s.date === date
          ? {
              ...s,
              completed: true,
              session_rpe: data.rpe ?? s.session_rpe,
              body_weight_kg: data.bodyWeightKg ?? s.body_weight_kg,
              session_notes: data.notes ?? s.session_notes,
            }
          : s
      )
      return { program: { ...state.program, sessions } }
    })
  },

  saveSession: async (date) => {
    const { program, version } = get()
    if (!program) return

    const session = program.sessions.find((s) => s.date === date)
    if (!session) return

    await api.updateSession(version, date, session)
    set({ isDirty: false })
  },

  updateMaxes: async (maxes) => {
    const { version } = get()
    await api.updateTargetMaxes(version, maxes)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          meta: {
            ...state.program.meta,
            target_squat_kg: maxes.squat_kg,
            target_bench_kg: maxes.bench_kg,
            target_dl_kg: maxes.deadlift_kg,
            target_total_kg: maxes.squat_kg + maxes.bench_kg + maxes.deadlift_kg,
          },
        },
      }
    })
  },

  updateBodyWeight: async (weightKg: number) => {
    const { version } = get()
    await api.updateBodyWeight(version, weightKg)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          meta: {
            ...state.program.meta,
            current_body_weight_kg: weightKg,
            current_body_weight_lb: weightKg * 2.20462,
          },
        },
      }
    })
  },

  updatePhases: async (phases: Phase[]) => {
    const { version } = get()
    await api.updatePhases(version, phases)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          phases,
        },
      }
    })
  },

  addWeightEntry: async (entry) => {
    const { version } = get()
    await api.addWeightEntry(version, entry)
  },

  removeWeightEntry: async (date) => {
    const { version } = get()
    await api.removeWeightEntry(version, date)
  },

  forkVersion: async (label) => {
    const { version } = get()
    const newVersion = await api.forkProgram(version, label)
    await get().loadProgram(newVersion)
    return newVersion
  },

  // Supplements
  updateSupplementPhases: async (phases) => {
    const { version } = get()
    await api.updateSupplementPhases(version, phases)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          supplement_phases: phases,
        },
      }
    })
  },

  // Diet Notes
  updateDietNotes: async (dietNotes) => {
    const { version } = get()
    await api.updateDietNotes(version, dietNotes)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          diet_notes: dietNotes,
        },
      }
    })
  },

  // Competitions
  updateCompetitions: async (competitions) => {
    const { version } = get()
    await api.updateCompetitions(version, competitions)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          competitions,
        },
      }
    })
  },

  migrateLastComp: async () => {
    const { version } = get()
    const competitions = await api.migrateLastComp(version)

    set((state) => {
      if (!state.program) return state
      return {
        program: {
          ...state.program,
          competitions,
        },
      }
    })
  },

  completeCompetition: async (date, results, bodyWeightKg) => {
    const { version } = get()
    await api.completeCompetition(version, date, results, bodyWeightKg)

    set((state) => {
      if (!state.program) return state
      const competitions = state.program.competitions.map((c) =>
        c.date === date
          ? { ...c, status: 'completed' as const, results, body_weight_kg: bodyWeightKg }
          : c
      )
      return {
        program: {
          ...state.program,
          competitions,
        },
      }
    })
  },

  // Videos
  removeSessionVideo: (sessionDate, videoId) => {
    set((state) => {
      if (!state.program) return state
      const sessions = state.program.sessions.map((s) => {
        if (s.date !== sessionDate) return s
        const videos = (s.videos || []).filter((v) => v.video_id !== videoId)
        return { ...s, videos: videos.length > 0 ? videos : undefined }
      })
      return { program: { ...state.program, sessions } }
    })
  },

  reset: () =>
    set({
      program: null,
      version: 'current',
      versions: [],
      isLoading: false,
      error: null,
      isDirty: false,
      activeSessionDate: null,
    }),
}))
