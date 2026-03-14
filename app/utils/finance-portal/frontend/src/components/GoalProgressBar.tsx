import { Goal } from '@finance-portal/types';
import { formatCurrency, formatDate } from '../utils/formatters';

interface GoalProgressBarProps {
  goal: Goal;
}

export function GoalProgressBar({ goal }: GoalProgressBarProps) {
  const progress = goal.target_amount > 0
    ? Math.min((goal.current_amount / goal.target_amount) * 100, 100)
    : 0;

  const remaining = goal.target_amount - goal.current_amount;
  const isOverdue = goal.deadline && new Date(goal.deadline) < new Date();
  const daysRemaining = goal.deadline
    ? Math.ceil((new Date(goal.deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;

  const priorityColors = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-green-500',
  };

  const progressColors = {
    critical: progress >= 75 ? 'bg-red-300' : 'bg-red-500',
    high: progress >= 75 ? 'bg-orange-300' : 'bg-orange-500',
    medium: progress >= 75 ? 'bg-yellow-300' : 'bg-yellow-500',
    low: progress >= 75 ? 'bg-green-300' : 'bg-green-500',
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${priorityColors[goal.priority]}`} />
          <h4 className="font-medium">{goal.title}</h4>
        </div>
        <span className="text-xs text-gray-500 capitalize">{goal.priority}</span>
      </div>

      {goal.description && (
        <p className="text-sm text-gray-600 mb-3">{goal.description}</p>
      )}

      {/* Progress bar */}
      <div className="mb-2">
        <div className="flex justify-between text-sm mb-1">
          <span className="font-medium">{formatCurrency(goal.current_amount)}</span>
          <span className="text-gray-500">of {formatCurrency(goal.target_amount)}</span>
        </div>
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full ${progressColors[goal.priority]} transition-all duration-300`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="flex justify-between items-center text-xs">
        <div className="flex items-center gap-2">
          <span className="font-medium text-green-600">
            {progress.toFixed(0)}% complete
          </span>
          {remaining > 0 && (
            <span className="text-gray-500">
              ({formatCurrency(remaining)} to go)
            </span>
          )}
        </div>

        {goal.deadline && (
          <span className={`${isOverdue ? 'text-red-600 font-medium' : 'text-gray-500'}`}>
            {isOverdue
              ? 'Overdue'
              : daysRemaining !== null
                ? `${daysRemaining} days left`
                : formatDate(goal.deadline, 'short')}
          </span>
        )}
      </div>

      {goal.category && (
        <span className="inline-block mt-2 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
          {goal.category}
        </span>
      )}
    </div>
  );
}

export default GoalProgressBar;
