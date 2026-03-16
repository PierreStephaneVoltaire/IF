import { useState, useEffect } from 'react'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { Copy, Settings, ChevronDown, Check } from 'lucide-react'

export default function TopBar() {
  const { program, version, versions, isLoading, forkVersion, loadVersions, loadProgram } = useProgramStore()
  const { unit, toggleUnit } = useSettingsStore()
  const { openDrawer } = useUiStore()
  const [showVersionMenu, setShowVersionMenu] = useState(false)
  const [forking, setForking] = useState(false)

  // Load versions on mount
  useEffect(() => {
    loadVersions()
  }, [loadVersions])

  const handleFork = async () => {
    if (forking) return
    setForking(true)
    try {
      await forkVersion()
      await loadVersions() // Refresh the list
      setShowVersionMenu(false)
    } catch (err) {
      console.error('Fork failed:', err)
    } finally {
      setForking(false)
    }
  }

  const handleSelectVersion = async (newVersion: string) => {
    if (newVersion === version) {
      setShowVersionMenu(false)
      return
    }
    await loadProgram(newVersion)
    setShowVersionMenu(false)
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
            <div className="absolute top-full left-0 mt-1 w-56 bg-card border border-border rounded-md shadow-lg z-50 max-h-80 overflow-y-auto">
              {/* Version list */}
              <div className="p-1 border-b border-border">
                {versions.map((v) => (
                  <button
                    key={v.version}
                    onClick={() => handleSelectVersion(v.version)}
                    className={`flex items-center justify-between w-full px-3 py-2 text-left text-sm rounded hover:bg-accent ${
                      v.version === 'current' ? 'font-semibold' : ''
                    }`}
                  >
                    <span>{v.version_label || v.version}</span>
                    {v.version === version && (
                      <Check className="w-4 h-4 text-primary" />
                    )}
                  </button>
                ))}
                {versions.length === 0 && (
                  <div className="px-3 py-2 text-sm text-muted-foreground">
                    No versions found
                  </div>
                )}
              </div>

              {/* Fork button */}
              <div className="p-1">
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
