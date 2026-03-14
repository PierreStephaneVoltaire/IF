import { useEffect } from 'react'
import { useDiaryStore } from './store/diaryStore'
import { WritePanel } from './components/WritePanel'
import { CurrentSignalCard } from './components/CurrentSignalCard'
import { ScoreChart } from './components/ScoreChart'
import { SignalHistoryTable } from './components/SignalHistoryTable'
import { EntryCountBadge } from './components/EntryCountBadge'

function App() {
  const { fetchLatestSignal, fetchSignalHistory, fetchEntryCount } =
    useDiaryStore()

  useEffect(() => {
    // Fetch all data on mount
    fetchLatestSignal()
    fetchSignalHistory(90)
    fetchEntryCount()
  }, [fetchLatestSignal, fetchSignalHistory, fetchEntryCount])

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
        {/* Header */}
        <header className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-gray-100">Diary Portal</h1>
          <p className="text-gray-500 text-sm">
            Write it down. Let it go. See your emotional weather.
          </p>
        </header>

        {/* Write Panel - Top */}
        <section className="space-y-4">
          <WritePanel />
          <EntryCountBadge />
        </section>

        {/* Divider */}
        <hr className="border-gray-800" />

        {/* Current Signal Card */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4">
            Current Signal
          </h2>
          <CurrentSignalCard />
        </section>

        {/* Score Chart */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4">
            Signal History
          </h2>
          <ScoreChart />
        </section>

        {/* Signal History Table */}
        <section>
          <h2 className="text-lg font-semibold text-gray-300 mb-4">
            History Log
          </h2>
          <SignalHistoryTable />
        </section>

        {/* Footer */}
        <footer className="text-center text-gray-600 text-xs pt-8 pb-4">
          <p>Entries expire after 3 days. Only signals persist.</p>
          <p className="mt-1">
            Signal computation happens automatically during heartbeat cycles.
          </p>
        </footer>
      </div>
    </div>
  )
}

export default App
