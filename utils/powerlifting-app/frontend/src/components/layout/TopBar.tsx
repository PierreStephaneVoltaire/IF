import { useState, useEffect } from 'react'
import { Menu, Button, Group } from '@mantine/core'
import { useProgramStore } from '@/store/programStore'
import { useSettingsStore } from '@/store/settingsStore'
import { useUiStore } from '@/store/uiStore'
import { Copy, Settings, ChevronDown, Check } from 'lucide-react'

export default function TopBar() {
  const { program, version, versions, isLoading, forkVersion, loadVersions, loadProgram } = useProgramStore()
  const { unit, toggleUnit } = useSettingsStore()
  const { openDrawer } = useUiStore()
  const [forking, setForking] = useState(false)

  useEffect(() => {
    loadVersions()
  }, [loadVersions])

  const handleFork = async () => {
    if (forking) return
    setForking(true)
    try {
      await forkVersion()
      await loadVersions()
    } catch (err) {
      console.error('Fork failed:', err)
    } finally {
      setForking(false)
    }
  }

  const handleSelectVersion = async (newVersion: string) => {
    if (newVersion === version) return
    await loadProgram(newVersion)
  }

  return (
    <Group justify="space-between" h="100%" px="md">
      {/* Left: Version selector */}
      <Menu shadow="md" width={220} position="bottom-start">
        <Menu.Target>
          <Button
            variant="subtle"
            rightSection={<ChevronDown size={16} />}
            loading={isLoading}
          >
            {program?.meta?.version_label || version}
          </Button>
        </Menu.Target>

        <Menu.Dropdown>
          {versions.map((v) => (
            <Menu.Item
              key={v.version}
              onClick={() => handleSelectVersion(v.version)}
              fw={v.version === 'current' ? 600 : 400}
              rightSection={
                v.version === version ? <Check size={16} /> : null
              }
            >
              {v.version_label || v.version}
            </Menu.Item>
          ))}

          {versions.length === 0 && (
            <Menu.Item disabled>No versions found</Menu.Item>
          )}

          <Menu.Divider />

          <Menu.Item
            onClick={handleFork}
            disabled={forking}
            leftSection={<Copy size={16} />}
          >
            {forking ? 'Forking...' : 'Fork this version'}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>

      {/* Right: Unit toggle + Settings */}
      <Group gap="xs">
        <Button variant="subtle" size="sm" onClick={toggleUnit}>
          {unit.toUpperCase()}
        </Button>

        <Button
          variant="subtle"
          size="sm"
          onClick={() => openDrawer('settings')}
        >
          <Settings size={20} />
        </Button>
      </Group>
    </Group>
  )
}
