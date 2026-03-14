import { useState } from 'react'
import { Calculator, Scale, Percent, ArrowLeftRight } from 'lucide-react'
import clsx from 'clsx'
import PlateCalculator from '@/components/tools/PlateCalculator'
import DotsCalculator from '@/components/tools/DotsCalculator'
import WeightTracker from '@/components/tools/WeightTracker'
import PercentTable from '@/components/tools/PercentTable'
import UnitConverter from '@/components/tools/UnitConverter'

const tools = [
  { id: 'plate', label: 'Plate Calculator', icon: Calculator },
  { id: 'dots', label: 'DOTS Calculator', icon: Calculator },
  { id: 'weight', label: 'Weight Tracker', icon: Scale },
  { id: 'percent', label: '% of Max', icon: Percent },
  { id: 'converter', label: 'kg/lb Converter', icon: ArrowLeftRight },
] as const

export default function ToolsPage() {
  const [selectedTool, setSelectedTool] = useState<string>(tools[0].id)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {tools.map((tool) => (
          <button
            key={tool.id}
            onClick={() => setSelectedTool(tool.id)}
            className={clsx(
              'px-4 py-2 rounded-md text-sm font-medium transition-colors',
              selectedTool === tool.id
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80'
            )}
          >
            {tool.label}
          </button>
        ))}
      </div>

      <div>
        {selectedTool === 'plate' && <PlateCalculator />}
        {selectedTool === 'dots' && <DotsCalculator />}
        {selectedTool === 'weight' && <WeightTracker />}
        {selectedTool === 'percent' && <PercentTable />}
        {selectedTool === 'converter' && <UnitConverter />}
      </div>
    </div>
  )
}
