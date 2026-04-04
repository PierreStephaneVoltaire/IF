import StrengthProgressChart from '@/components/charts/StrengthProgressChart'
import VolumeChart from '@/components/charts/VolumeChart'
import WeightChart from '@/components/charts/WeightChart'
import IntensityChart from '@/components/charts/IntensityChart'
import RpeChart from '@/components/charts/RpeChart'

export default function ChartsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Charts</h1>
        <p className="text-muted-foreground text-sm">
          Visualize your training progress over time
        </p>
      </div>

      {/* Mobile: Stack all charts vertically with min height */}
      {/* Desktop: 2x2 grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="min-h-[300px]">
          <StrengthProgressChart />
        </div>
        <div className="min-h-[300px]">
          <VolumeChart />
        </div>
        <div className="min-h-[300px]">
          <WeightChart />
        </div>
        <div className="min-h-[300px]">
          <IntensityChart />
        </div>
      </div>

      <div className="min-h-[250px]">
        <RpeChart />
      </div>
    </div>
  )
}
