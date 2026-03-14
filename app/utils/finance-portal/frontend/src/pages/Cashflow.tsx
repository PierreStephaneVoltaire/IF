import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { EditableField, CashflowSankey } from '../components';
import { formatCurrency } from '../utils/formatters';

export function Cashflow() {
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const updateCashflow = useFinanceStore((state) => state.updateCashflow);
  const isLoading = useFinanceStore((state) => state.isLoading);
  const snapshot = useSnapshot();

  useEffect(() => {
    if (!snapshot) {
      fetchCurrentSnapshot();
    }
  }, [snapshot, fetchCurrentSnapshot]);

  const handleIncomeUpdate = async (value: number) => {
    updateCashflow({ net_monthly_income: value });
    // Server-side recalculation would happen via API call
  };

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

  const { monthly_cashflow } = snapshot;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Cashflow</h1>

      {/* Income Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Monthly Income</h2>
        <div className="flex items-center gap-4">
          <span className="text-gray-600">Net Monthly Income:</span>
          <EditableField
            value={monthly_cashflow.net_monthly_income}
            type="currency"
            onSave={(v) => handleIncomeUpdate(v as number)}
            displayClassName="text-2xl font-bold text-green-600"
          />
        </div>
      </div>

      {/* Cashflow Visualization */}
      <CashflowSankey cashflow={monthly_cashflow} />

      {/* Fixed Expenses */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-semibold text-gray-700">
            Fixed Expenses ({formatCurrency(monthly_cashflow.total_fixed)})
          </h2>
        </div>
        {monthly_cashflow.fixed_expenses.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No fixed expenses recorded</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Name</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Amount</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Frequency</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Category</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Due Day</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Auto-Pay</th>
              </tr>
            </thead>
            <tbody>
              {monthly_cashflow.fixed_expenses.map((expense) => (
                <tr key={expense.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium">{expense.name}</td>
                  <td className="py-3 px-4 text-right">{formatCurrency(expense.amount)}</td>
                  <td className="py-3 px-4 text-center capitalize">{expense.frequency}</td>
                  <td className="py-3 px-4 text-gray-600">{expense.category}</td>
                  <td className="py-3 px-4 text-center text-gray-500">
                    {expense.due_day ? `${expense.due_day}${getOrdinalSuffix(expense.due_day)}` : '-'}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {expense.auto_pay ? (
                      <span className="text-green-600">✓</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Debt Payments */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-semibold text-gray-700">
            Debt Payments ({formatCurrency(monthly_cashflow.total_debt_payments)})
          </h2>
        </div>
        {monthly_cashflow.debt_payments.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No debt payments recorded</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Account</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Payment</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Type</th>
              </tr>
            </thead>
            <tbody>
              {monthly_cashflow.debt_payments.map((payment) => (
                <tr key={payment.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium">{payment.account_name}</td>
                  <td className="py-3 px-4 text-right">{formatCurrency(payment.amount)}</td>
                  <td className="py-3 px-4 text-center capitalize">
                    <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">
                      {payment.type.replace('_', ' ')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Savings & Investments */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-semibold text-gray-700">
            Savings & Investments ({formatCurrency(monthly_cashflow.total_savings_investments)})
          </h2>
        </div>
        {monthly_cashflow.savings_and_investments.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No savings or investments recorded</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Name</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Amount</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Frequency</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Type</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Auto-Transfer</th>
              </tr>
            </thead>
            <tbody>
              {monthly_cashflow.savings_and_investments.map((item) => (
                <tr key={item.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium">{item.name}</td>
                  <td className="py-3 px-4 text-right text-green-600 font-medium">
                    {formatCurrency(item.amount)}
                  </td>
                  <td className="py-3 px-4 text-center capitalize">{item.frequency}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs uppercase">
                      {item.type}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    {item.auto_transfer ? (
                      <span className="text-green-600">✓</span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Variable Budget */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-semibold text-gray-700">
            Variable Budget ({formatCurrency(monthly_cashflow.total_variable_budget)})
          </h2>
        </div>
        {monthly_cashflow.variable_expense_budget.length === 0 ? (
          <p className="p-4 text-gray-500 text-center">No variable budget categories</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Category</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Budget</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Notes</th>
              </tr>
            </thead>
            <tbody>
              {monthly_cashflow.variable_expense_budget.map((item) => (
                <tr key={item.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4 font-medium">{item.category}</td>
                  <td className="py-3 px-4 text-right">{formatCurrency(item.budget_amount)}</td>
                  <td className="py-3 px-4 text-gray-500 text-xs">{item.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Summary */}
      <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Monthly Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
          <div>
            <p className="text-sm text-gray-500">Income</p>
            <p className="text-xl font-bold text-green-600">
              {formatCurrency(monthly_cashflow.net_monthly_income)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Total Outflow</p>
            <p className="text-xl font-bold text-red-600">
              {formatCurrency(monthly_cashflow.total_outflow)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Surplus</p>
            <p className={`text-xl font-bold ${monthly_cashflow.monthly_surplus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(monthly_cashflow.monthly_surplus, { showSign: true })}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Savings Rate</p>
            <p className="text-xl font-bold text-blue-600">
              {monthly_cashflow.net_monthly_income > 0
                ? ((monthly_cashflow.total_savings_investments / monthly_cashflow.net_monthly_income) * 100).toFixed(1)
                : 0}%
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function getOrdinalSuffix(day: number): string {
  if (day >= 11 && day <= 13) return 'th';
  switch (day % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
}

export default Cashflow;
