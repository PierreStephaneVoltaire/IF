import { Link } from 'react-router-dom'
import { GitBranch, ClipboardList } from 'lucide-react'

export default function DesignerLanding() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Program Designer</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          to="/designer/phases"
          className="bg-card border border-border rounded-lg p-6 min-h-[200px] flex flex-col justify-between hover:border-primary/50 transition-colors"
        >
          <div>
            <div className="flex items-center gap-3 mb-3">
              <GitBranch className="w-8 h-8 text-primary" />
              <h2 className="text-xl font-semibold">Phase Design</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Manage training phases, set week ranges and RPE targets, and organize your training blocks.
            </p>
          </div>
          <p className="text-xs text-primary mt-4">Open phase designer →</p>
        </Link>

        <Link
          to="/designer/sessions"
          className="bg-card border border-border rounded-lg p-6 min-h-[200px] flex flex-col justify-between hover:border-primary/50 transition-colors"
        >
          <div>
            <div className="flex items-center gap-3 mb-3">
              <ClipboardList className="w-8 h-8 text-primary" />
              <h2 className="text-xl font-semibold">Session Design</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              Plan and manage training sessions by week, add exercises, and set planned sets and reps.
            </p>
          </div>
          <p className="text-xs text-primary mt-4">Open session designer →</p>
        </Link>
      </div>
    </div>
  )
}
