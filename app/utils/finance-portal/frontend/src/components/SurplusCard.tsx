import { useSnapshot } from '../store/financeStore';
import { formatCurrency, getGainLossClass } from '../utils/formatters';

export function SurplusCard() {
  const snapshot = useSnapshot();

  if (!snapshot) {
    return (
      <div className="bg-white rounded-lg shadow p-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="h-8 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  const { monthly_cashflow } = snapshot;
  const surplus = monthly_cashflow.monthly_surplus;
  const income = monthly_cashflow.net_monthly_income;
  const totalOutflow = monthly_cashflow.total_outflow;

  const savingsRate = income > 0 ? ((surplus / income) * 100) : 0;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-gray-700">Monthly Surplus</h3>
        <span className={`text-xs px-2 py-1 rounded ${
          surplus >= 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
        }`}>
          {savingsRate.toFixed(1)}% savings rate
        </span>
      </div>

      <div className="mb-4">
        <span className={`text-3xl font-bold ${getGainLossClass(surplus)}`}>
          {formatCurrency(surplus, { showSign: true })}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Net Income</span>
          <span className="font-medium">{formatCurrency(income)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Total Outflow</span>
          <span className="font-medium text-red-600">-{formatCurrency(totalOutflow)}</span>
        </div>
      </div>

      {/* Progress bar showing outflow vs income */}
      <div className="mt-4">
        <div className="flex h-2 rounded-full overflow-hidden bg-gray-200">
          {income > 0 && (
            <>
              <div
                className="bg-blue-500"
                style={{ width: `${Math.min((surplus / income) * 100, 100)}%` }}
                title="Surplus"
              />
              <div
                className="bg-orange-500"
                style={{ width: `${Math.min((totalOutflow / income) * 100, 100)}%` }}
                title="Outflow"
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default SurplusCard;
