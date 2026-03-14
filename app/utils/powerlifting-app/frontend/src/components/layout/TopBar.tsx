import { useState } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { Copy, Settings, ChevronDown } from 'lucide-react'

export default function TopBar() {
  const { program, version, isLoading, forkVersion } = useProgramStore()
  const { unit, toggleUnit } = useSettingsStore()
  const { openDrawer } = useUiStore()
  const [showVersionMenu, setShowVersionMenu] = useState(false)
  const [forking, setForking] = useState(false)

  const handleFork = async () => {
    if (forking) return
    setForking(true)
    try {
      await forkVersion()
      setShowVersionMenu(false)
    } catch (err) {
      console.error('Fork failed:', err)
    } finally {
      setForking(false)
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur-sm">
      <div className="flex items-center justify-between px-4 py-3">
        {/* Left: Version selector */}
        <div className="relative">
          <button
            onClick={() => setShowVersionMenu(!showVersionMenu)}
            className="flex items-center gap-2 px-3 py-2 rounded-md hover:bg-accent transition-colors"
            disabled={isLoading}
          >
            <span className="font-medium">
              {program?.meta?.version_label || version}
            </span>
            <ChevronDown className="w-4 h-4" />
          </button>

          {showVersionMenu && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-card border border-border rounded-md shadow-lg z-50">
              <div className="p-2">
                <button
                  onClick={handleFork}
                  disabled={forking}
                  className="flex items-center gap-2 w-full px-3 py-2 text-left text-sm rounded hover:bg-accent"
                >
                  <Copy className="w-4 h-4" />
                  {forking ? 'Forking...' : 'Fork this version'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Unit toggle + Settings */}
        <div className="flex items-center gap-2">
          <button
            onClick={toggleUnit}
            className="px-3 py-2 text-sm font-medium rounded-md hover:bg-accent transition-colors"
          >
            {unit.toUpperCase()}
          </button>

          <button
            onClick={() => openDrawer('settings')}
            className="p-2 rounded-md hover:bg-accent transition-colors"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  )
}
