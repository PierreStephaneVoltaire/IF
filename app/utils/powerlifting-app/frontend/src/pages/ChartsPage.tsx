import StrengthProgressChart from '@/components/charts/StrengthProgressChart'
import VolumeChart from '@/components/charts/VolumeChart'
import WeightChart from '@/components/charts/WeightChart'
import IntensityChart from '@/components/charts/IntensityChart'
import RpeChart from '@/components/charts/RpeChart'

export default function ChartsPage() {
  return (
    <div className="space-y-4 h-[calc(100vh-180px)] md:h-[calc(100vh-140px)] flex flex-col">
      <div className="shrink-0">
        <h1 className="text-2xl font-bold">Charts</h1>
        <p className="text-muted-foreground text-sm">
          Visualize your training progress over time
        </p>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        <StrengthProgressChart />
        <VolumeChart />
        <WeightChart />
        <IntensityChart />
      </div>

      <div className="shrink-0 h-[200px] md:h-[180px]">
        <RpeChart />
      </div>
    </div>
  )
}
