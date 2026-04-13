import { Tabs } from '@mantine/core'
import PlateCalculator from '@/components/tools/PlateCalculator'
import DotsCalculator from '@/components/tools/DotsCalculator'
import WeightTracker from '@/components/tools/WeightTracker'
import PercentTable from '@/components/tools/PercentTable'
import UnitConverter from '@/components/tools/UnitConverter'

export default function ToolsPage() {
  return (
    <Tabs defaultValue="plate">
      <Tabs.List>
        <Tabs.Tab value="plate">Plate Calculator</Tabs.Tab>
        <Tabs.Tab value="dots">DOTS Calculator</Tabs.Tab>
        <Tabs.Tab value="weight">Weight Tracker</Tabs.Tab>
        <Tabs.Tab value="percent">% of Max</Tabs.Tab>
        <Tabs.Tab value="converter">kg/lb Converter</Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="plate">
        <PlateCalculator />
      </Tabs.Panel>
      <Tabs.Panel value="dots">
        <DotsCalculator />
      </Tabs.Panel>
      <Tabs.Panel value="weight">
        <WeightTracker />
      </Tabs.Panel>
      <Tabs.Panel value="percent">
        <PercentTable />
      </Tabs.Panel>
      <Tabs.Panel value="converter">
        <UnitConverter />
      </Tabs.Panel>
    </Tabs>
  )
}
