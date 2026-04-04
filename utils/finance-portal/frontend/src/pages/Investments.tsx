import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { InvestmentAccountPanel, AllocationChart, WatchlistTable } from '../components';
import { formatCurrency } from '../utils/formatters';

export function Investments() {
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

  const { investment_accounts, watchlist } = snapshot;

  // Calculate totals
  const totalHoldingsValue = investment_accounts.reduce(
    (sum, account) => sum + account.holdings.reduce(
      (hSum, h) => hSum + (h.shares * h.current_price), 0
    ), 0
  );

  const totalCash = investment_accounts.reduce(
    (sum, account) => sum + (account.cash_balance || 0), 0
  );

  const totalCostBasis = investment_accounts.reduce(
    (sum, account) => sum + account.holdings.reduce(
      (hSum, h) => hSum + (h.shares * h.avg_cost), 0
    ), 0
  );

  const totalGainLoss = totalHoldingsValue - totalCostBasis;
  const totalGainLossPct = totalCostBasis > 0 ? (totalGainLoss / totalCostBasis) * 100 : 0;

  // Aggregate allocation across all accounts
  const aggregatedAllocation = investment_accounts.reduce((acc, account) => {
    account.target_allocation.forEach((alloc) => {
      const existing = acc.find((a) => a.category === alloc.category);
      if (existing) {
        existing.current_pct += alloc.current_pct;
        existing.target_pct += alloc.target_pct;
      } else {
        acc.push({ ...alloc });
      }
    });
    return acc;
  }, [] as { category: string; current_pct: number; target_pct: number }[]);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Investments</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Holdings</p>
          <p className="text-xl font-bold text-blue-600">{formatCurrency(totalHoldingsValue)}</p>
          <p className="text-xs text-gray-500">{investment_accounts.length} accounts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Cash Balance</p>
          <p className="text-xl font-bold text-green-600">{formatCurrency(totalCash)}</p>
          <p className="text-xs text-gray-500">Uninvested</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Gain/Loss</p>
          <p className={`text-xl font-bold ${totalGainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatCurrency(Math.abs(totalGainLoss), { showSign: totalGainLoss > 0 })}
          </p>
          <p className={`text-xs ${totalGainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalGainLossPct >= 0 ? '+' : ''}{totalGainLossPct.toFixed(1)}%
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Total Portfolio</p>
          <p className="text-xl font-bold text-gray-800">
            {formatCurrency(totalHoldingsValue + totalCash)}
          </p>
          <p className="text-xs text-gray-500">Holdings + Cash</p>
        </div>
      </div>

      {/* Allocation Chart */}
      {aggregatedAllocation.length > 0 && (
        <AllocationChart allocation={aggregatedAllocation} title="Portfolio Allocation" />
      )}

      {/* Investment Accounts */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-700">Accounts</h2>
        {investment_accounts.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
            No investment accounts
          </div>
        ) : (
          investment_accounts.map((account) => (
            <InvestmentAccountPanel key={account.id} account={account} />
          ))
        )}
      </div>

      {/* Watchlist */}
      <WatchlistTable watchlist={watchlist} />
    </div>
  );
}

export default Investments;
