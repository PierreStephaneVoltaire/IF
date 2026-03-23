import { Fragment } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { X, Sun, Moon, Monitor } from 'lucide-react'
import { useUiStore } from '@/store/uiStore'
import { useSettingsStore, type Theme } from '@/store/settingsStore'
import { clsx } from 'clsx'

const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export default function SettingsDrawer() {
  const { drawerOpen, drawerType, closeDrawer } = useUiStore()
  const { theme, setTheme, sex, setSex, barWeightKg, setBarWeight } = useSettingsStore()

  const isOpen = drawerOpen && drawerType === 'settings'

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-[70]" onClose={closeDrawer}>
        <Transition.Child
          as={Fragment}
          enter="ease-in-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in-out duration-300"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <Transition.Child
                as={Fragment}
                enter="transform transition ease-in-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-300"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <Dialog.Panel className="pointer-events-auto w-screen max-w-sm">
                  <div className="flex h-full flex-col bg-background shadow-xl">
                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                      <Dialog.Title className="text-lg font-semibold">
                        Settings
                      </Dialog.Title>
                      <button
                        onClick={closeDrawer}
                        className="p-2 rounded-md hover:bg-accent"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-6">
                      {/* Theme */}
                      <div>
                        <label className="text-sm font-medium mb-3 block">
                          Appearance
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                          {themeOptions.map((option) => {
                            const Icon = option.icon
                            return (
                              <button
                                key={option.value}
                                onClick={() => setTheme(option.value)}
                                className={clsx(
                                  'flex flex-col items-center gap-2 p-3 rounded-lg border transition-colors',
                                  theme === option.value
                                    ? 'border-primary bg-primary/10 text-primary'
                                    : 'border-border hover:bg-accent'
                                )}
                              >
                                <Icon className="w-5 h-5" />
                                <span className="text-xs font-medium">{option.label}</span>
                              </button>
                            )
                          })}
                        </div>
                      </div>

                      {/* Sex for DOTS calculation */}
                      <div>
                        <label className="text-sm font-medium mb-3 block">
                          Sex (for DOTS calculation)
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            onClick={() => setSex('male')}
                            className={clsx(
                              'py-2 px-4 rounded-lg border transition-colors text-sm font-medium',
                              sex === 'male'
                                ? 'border-primary bg-primary/10 text-primary'
                                : 'border-border hover:bg-accent'
                            )}
                          >
                            Male
                          </button>
                          <button
                            onClick={() => setSex('female')}
                            className={clsx(
                              'py-2 px-4 rounded-lg border transition-colors text-sm font-medium',
                              sex === 'female'
                                ? 'border-primary bg-primary/10 text-primary'
                                : 'border-border hover:bg-accent'
                            )}
                          >
                            Female
                          </button>
                        </div>
                      </div>

                      {/* Bar Weight */}
                      <div>
                        <label className="text-sm font-medium mb-2 block">
                          Bar Weight (kg)
                        </label>
                        <input
                          type="number"
                          value={barWeightKg}
                          onChange={(e) => setBarWeight(parseFloat(e.target.value) || 20)}
                          className="w-full px-3 py-2 border border-border rounded-lg bg-background"
                        />
                        <p className="text-xs text-muted-foreground mt-1">
                          Used for plate calculator. Standard: 20kg (men's), 15kg (women's)
                        </p>
                      </div>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
