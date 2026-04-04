import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { GoalProgressBar } from '../components';
import { formatCurrency } from '../utils/formatters';

export function Goals() {
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const isLoading = useFinanceStore((state) => state.isLoading);
  const snapshot = useSnapshot();

  useEffect(() => {
    if (!snapshot) {
      fetchCurrentSnapshot();
    }
  }, [snapshot, fetchCurrentSnapshot]);

  if (isLoading && !snapshot) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No data available.</p>
      </div>
    );
  }

  const { goals } = snapshot;

  const allGoals = [
    ...goals.short_term.map(g => ({ ...g, term: 'short' as const })),
    ...goals.medium_term.map(g => ({ ...g, term: 'medium' as const })),
    ...goals.long_term.map(g => ({ ...g, term: 'long' as const })),
  ];

  const totalTarget = allGoals.reduce((sum, g) => sum + g.target_amount, 0);
  const totalCurrent = allGoals.reduce((sum, g) => sum + g.current_amount, 0);
  const overallProgress = totalTarget > 0 ? (totalCurrent / totalTarget) * 100 : 0;

  const criticalGoals = allGoals.filter(g => g.priority === 'critical');
  const overdueGoals = allGoals.filter(g => g.deadline && new Date(g.deadline) < new Date());

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Goals</h1>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Goals</p>
          <p className="text-2xl font-bold text-gray-800">{allGoals.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Target</p>
          <p className="text-2xl font-bold text-blue-600">{formatCurrency(totalTarget)}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Saved</p>
          <p className="text-2xl font-bold text-green-600">{formatCurrency(totalCurrent)}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Overall Progress</p>
          <p className="text-2xl font-bold text-purple-600">{overallProgress.toFixed(1)}%</p>
        </div>
      </div>

      {/* Alerts */}
      {(criticalGoals.length > 0 || overdueGoals.length > 0) && (
        <div className="space-y-3">
          {criticalGoals.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h3 className="font-medium text-red-800">
                {criticalGoals.length} Critical Priority Goal{criticalGoals.length > 1 ? 's' : ''}
              </h3>
              <p className="text-sm text-red-600">
                {criticalGoals.map(g => g.title).join(', ')}
              </p>
            </div>
          )}
          {overdueGoals.length > 0 && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <h3 className="font-medium text-orange-800">
                {overdueGoals.length} Overdue Goal{overdueGoals.length > 1 ? 's' : ''}
              </h3>
              <p className="text-sm text-orange-600">
                {overdueGoals.map(g => g.title).join(', ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Short-term Goals */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-700">Short-term</h2>
          <span className="text-sm text-gray-500">(0-1 year)</span>
          <span className="ml-auto text-sm text-gray-500">
            {goals.short_term.length} goal{goals.short_term.length !== 1 ? 's' : ''}
          </span>
        </div>
        {goals.short_term.length === 0 ? (
          <p className="text-gray-500 text-center py-4 bg-gray-50 rounded-lg">No short-term goals</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {goals.short_term.map((goal) => (
              <GoalProgressBar key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </div>

      {/* Medium-term Goals */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-700">Medium-term</h2>
          <span className="text-sm text-gray-500">(1-5 years)</span>
          <span className="ml-auto text-sm text-gray-500">
            {goals.medium_term.length} goal{goals.medium_term.length !== 1 ? 's' : ''}
          </span>
        </div>
        {goals.medium_term.length === 0 ? (
          <p className="text-gray-500 text-center py-4 bg-gray-50 rounded-lg">No medium-term goals</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {goals.medium_term.map((goal) => (
              <GoalProgressBar key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </div>

      {/* Long-term Goals */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-gray-700">Long-term</h2>
          <span className="text-sm text-gray-500">(5+ years)</span>
          <span className="ml-auto text-sm text-gray-500">
            {goals.long_term.length} goal{goals.long_term.length !== 1 ? 's' : ''}
          </span>
        </div>
        {goals.long_term.length === 0 ? (
          <p className="text-gray-500 text-center py-4 bg-gray-50 rounded-lg">No long-term goals</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {goals.long_term.map((goal) => (
              <GoalProgressBar key={goal.id} goal={goal} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Goals;
