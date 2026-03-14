import StrengthProgressChart from '@/components/charts/StrengthProgressChart'
import VolumeChart from '@/components/charts/VolumeChart'
import WeightChart from '@/components/charts/WeightChart'
import IntensityChart from '@/components/charts/IntensityChart'
import RpeChart from '@/components/charts/RpeChart'

export default function ChartsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Charts</h1>
        <p className="text-muted-foreground">
          Visualize your training progress over time
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <StrengthProgressChart />
        <VolumeChart />
        <WeightChart />
        <IntensityChart />
      </div>

      <RpeChart />
    </div>
  )
}
