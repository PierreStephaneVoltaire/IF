import { MonthlyCashflow } from '@finance-portal/types';
import { formatCurrency } from '../utils/formatters';

interface CashflowSankeyProps {
  cashflow: MonthlyCashflow;
}

export function CashflowSankey({ cashflow }: CashflowSankeyProps) {
  const income = cashflow.net_monthly_income;
  const totalFixed = cashflow.total_fixed;
  const totalDebt = cashflow.total_debt_payments;
  const totalSavings = cashflow.total_savings_investments;
  const totalVariable = cashflow.total_variable_budget;
  const surplus = cashflow.monthly_surplus;

  if (income <= 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-4">Cashflow Breakdown</h3>
        <p className="text-gray-500 text-center py-4">No income data available</p>
      </div>
    );
  }

  const flows = [
    { label: 'Fixed Expenses', amount: totalFixed, color: 'bg-blue-500' },
    { label: 'Debt Payments', amount: totalDebt, color: 'bg-red-500' },
    { label: 'Savings & Investments', amount: totalSavings, color: 'bg-green-500' },
    { label: 'Variable Budget', amount: totalVariable, color: 'bg-orange-500' },
  ];

  const positiveFlows = flows.filter(f => f.amount > 0);
  const totalOutflow = positiveFlows.reduce((sum, f) => sum + f.amount, 0);

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold text-gray-700 mb-4">Cashflow Breakdown</h3>

      <div className="space-y-4">
        {/* Income bar */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium text-gray-700">Net Income</span>
            <span className="font-semibold">{formatCurrency(income)}</span>
          </div>
          <div className="h-8 bg-gray-200 rounded-lg overflow-hidden flex">
            {positiveFlows.map((flow, index) => (
              <div
                key={index}
                className={`${flow.color} h-full transition-all duration-300`}
                style={{ width: `${(flow.amount / income) * 100}%` }}
                title={`${flow.label}: ${formatCurrency(flow.amount)}`}
              />
            ))}
            {surplus > 0 && (
              <div
                className="bg-emerald-400 h-full"
                style={{ width: `${(surplus / income) * 100}%` }}
                title={`Surplus: ${formatCurrency(surplus)}`}
              />
            )}
          </div>
        </div>

        {/* Flow breakdown */}
        <div className="grid grid-cols-2 gap-3">
          {flows.map((flow, index) => (
            <div key={index} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded ${flow.color}`} />
                <span className="text-gray-600">{flow.label}</span>
              </div>
              <span className="font-medium">{formatCurrency(flow.amount)}</span>
            </div>
          ))}

          {/* Surplus */}
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-emerald-400" />
              <span className="text-gray-600">Surplus</span>
            </div>
            <span className={`font-medium ${surplus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(surplus, { showSign: true })}
            </span>
          </div>
        </div>

        {/* Summary stats */}
        <div className="pt-3 border-t grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-500">Total Outflow</p>
            <p className="font-semibold text-red-600">{formatCurrency(totalOutflow)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Savings Rate</p>
            <p className="font-semibold text-green-600">
              {((totalSavings / income) * 100).toFixed(1)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Remaining</p>
            <p className={`font-semibold ${surplus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(surplus, { showSign: true })}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CashflowSankey;
