import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { NetWorthCard, SurplusCard, CashflowSankey } from '../components';
import { formatCurrency, formatDate } from '../utils/formatters';

export function Dashboard() {
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const isLoading = useFinanceStore((state) => state.isLoading);
  const version = useFinanceStore((state) => state.version);
  const snapshot = useSnapshot();

  useEffect(() => {
    fetchCurrentSnapshot();
  }, [fetchCurrentSnapshot]);

  if (isLoading && !snapshot) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="h-48 bg-gray-200 rounded"></div>
            <div className="h-48 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No data available. Click "New Version" to create your first snapshot.</p>
      </div>
    );
  }

  const totalCreditCardDebt = snapshot.accounts.credit_cards.reduce(
    (sum, card) => sum + card.balance_owing, 0
  );
  const totalLOCDebt = snapshot.accounts.lines_of_credit.reduce(
    (sum, loc) => sum + loc.balance_owing, 0
  );
  const totalLoanDebt = snapshot.accounts.loans.reduce(
    (sum, loan) => sum + loan.current_balance, 0
  );
  const totalDebt = totalCreditCardDebt + totalLOCDebt + totalLoanDebt;

  const totalInvestments = snapshot.investment_accounts.reduce(
    (sum, account) => sum + account.holdings.reduce(
      (hSum, h) => hSum + (h.shares * h.current_price), 0
    ) + (account.cash_balance || 0), 0
  );

  const totalChequing = snapshot.accounts.chequing.reduce(
    (sum, acc) => sum + acc.balance, 0
  );
  const totalSavings = snapshot.accounts.savings.reduce(
    (sum, acc) => sum + acc.balance, 0
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>
          {version && (
            <p className="text-sm text-gray-500">
              Version {version.label} • Updated {formatDate(version.updated_at, 'relative')}
            </p>
          )}
        </div>
        <button
          onClick={() => fetchCurrentSnapshot()}
          className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
        >
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <NetWorthCard />
        <SurplusCard />

        {/* Quick Stats - Debt */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-700 mb-4">Total Debt</h3>
          <p className="text-3xl font-bold text-red-600 mb-4">
            {formatCurrency(totalDebt)}
          </p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Credit Cards</span>
              <span>{formatCurrency(totalCreditCardDebt)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Lines of Credit</span>
              <span>{formatCurrency(totalLOCDebt)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Loans</span>
              <span>{formatCurrency(totalLoanDebt)}</span>
            </div>
          </div>
        </div>

        {/* Quick Stats - Assets */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-700 mb-4">Liquid Assets</h3>
          <p className="text-3xl font-bold text-green-600 mb-4">
            {formatCurrency(totalChequing + totalSavings + totalInvestments)}
          </p>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Chequing</span>
              <span>{formatCurrency(totalChequing)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Savings</span>
              <span>{formatCurrency(totalSavings)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Investments</span>
              <span>{formatCurrency(totalInvestments)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Cashflow Breakdown */}
      <CashflowSankey cashflow={snapshot.monthly_cashflow} />

      {/* Account Summaries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Credit Cards Summary */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Credit Cards</h3>
          {snapshot.accounts.credit_cards.length === 0 ? (
            <p className="text-gray-500 text-sm">No credit cards</p>
          ) : (
            <div className="space-y-2">
              {snapshot.accounts.credit_cards.slice(0, 3).map((card) => (
                <div key={card.id} className="flex justify-between items-center text-sm">
                  <span className="text-gray-600">{card.name}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          card.utilization_pct < 30 ? 'bg-green-500' :
                          card.utilization_pct < 50 ? 'bg-yellow-500' :
                          card.utilization_pct < 75 ? 'bg-orange-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.min(card.utilization_pct, 100)}%` }}
                      />
                    </div>
                    <span className="font-medium text-red-600 w-20 text-right">
                      {formatCurrency(card.balance_owing)}
                    </span>
                  </div>
                </div>
              ))}
              {snapshot.accounts.credit_cards.length > 3 && (
                <p className="text-xs text-gray-500">
                  +{snapshot.accounts.credit_cards.length - 3} more cards
                </p>
              )}
            </div>
          )}
        </div>

        {/* Goals Summary */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Goals Progress</h3>
          {snapshot.goals.short_term.length === 0 &&
           snapshot.goals.medium_term.length === 0 &&
           snapshot.goals.long_term.length === 0 ? (
            <p className="text-gray-500 text-sm">No goals set</p>
          ) : (
            <div className="space-y-2">
              {[...snapshot.goals.short_term, ...snapshot.goals.medium_term]
                .slice(0, 3)
                .map((goal) => {
                  const progress = (goal.current_amount / goal.target_amount) * 100;
                  return (
                    <div key={goal.id} className="text-sm">
                      <div className="flex justify-between mb-1">
                        <span className="text-gray-600">{goal.title}</span>
                        <span className="text-gray-500">{progress.toFixed(0)}%</span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500"
                          style={{ width: `${Math.min(progress, 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
