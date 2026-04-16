import { Drawer, SegmentedControl, NumberInput, Text, Stack, Group, Button } from '@mantine/core'
import { useUiStore } from '@/store/uiStore'
import { useSettingsStore, type Theme } from '@/store/settingsStore'
import { useProgramStore } from '@/store/programStore'
import { Sun, Moon, Monitor } from 'lucide-react'

const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export default function SettingsDrawer() {
  const { drawerOpen, drawerType, closeDrawer } = useUiStore()
  const { theme, setTheme, sex, setSex, barWeightKg, setBarWeight } = useSettingsStore()
  const { setSex: programSetSex } = useProgramStore()

  const isOpen = drawerOpen && drawerType === 'settings'

  return (
    <Drawer
      opened={isOpen}
      onClose={closeDrawer}
      title="Settings"
      position="right"
      size="sm"
      shadow="md"
    >
      <Stack gap="lg">
        {/* Theme */}
        <div>
          <Text size="sm" fw={500} mb="xs">
            Appearance
          </Text>
          <Group gap="xs">
            {themeOptions.map((option) => {
              const Icon = option.icon
              const active = theme === option.value
              return (
                <Button
                  key={option.value}
                  variant={active ? 'filled' : 'outline'}
                  size="sm"
                  onClick={() => setTheme(option.value)}
                  leftSection={<Icon size={16} />}
                >
                  {option.label}
                </Button>
              )
            })}
          </Group>
        </div>

        {/* Sex for DOTS calculation */}
        <div>
          <Text size="sm" fw={500} mb="xs">
            Sex (for DOTS calculation)
          </Text>
          <SegmentedControl
            value={sex}
            onChange={(val) => {
              const newSex = val as 'male' | 'female';
              setSex(newSex);
              programSetSex(newSex).catch(console.error);
            }}
            data={[
              { label: 'Male', value: 'male' },
              { label: 'Female', value: 'female' },
            ]}
            fullWidth
          />
        </div>

        {/* Bar Weight */}
        <div>
          <Text size="sm" fw={500} mb="xs">
            Bar Weight (kg)
          </Text>
          <NumberInput
            value={barWeightKg}
            onChange={(val) => setBarWeight(typeof val === 'number' ? val : 20)}
            min={0}
            max={50}
            step={0.25}
          />
          <Text size="xs" c="dimmed" mt={4}>
            Used for plate calculator. Standard: 20kg (men's), 15kg (women's)
          </Text>
        </div>
      </Stack>
    </Drawer>
  )
}
