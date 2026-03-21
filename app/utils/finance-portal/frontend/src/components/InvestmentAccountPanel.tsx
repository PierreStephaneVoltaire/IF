import { InvestmentAccount, Holding } from '@finance-portal/types';
import { HoldingsTable } from './HoldingsTable';
import { useFinanceStore } from '../store/financeStore';
import { formatCurrency } from '../utils/formatters';
import { useState } from 'react';

interface InvestmentAccountPanelProps {
  account: InvestmentAccount;
}

export function InvestmentAccountPanel({ account }: InvestmentAccountPanelProps) {
  const updateHolding = useFinanceStore((state) => state.updateHolding);
  const addHolding = useFinanceStore((state) => state.addHolding);
  const [isExpanded, setIsExpanded] = useState(true);
  const [showAddHolding, setShowAddHolding] = useState(false);
  const [newHolding, setNewHolding] = useState<Partial<Holding>>({
    ticker: '',
    shares: 0,
    avg_cost: 0,
    current_price: 0,
    notes: '',
  });

  const totalValue = account.holdings.reduce((sum, h) => sum + (h.shares * h.current_price), 0);
  const totalCash = account.cash_balance || 0;
  const totalAccountValue = totalValue + totalCash;

  const accountTypeLabels: Record<string, string> = {
    rrsp: 'RRSP',
    tfsa: 'TFSA',
    non_registered: 'Non-Registered',
    resp: 'RESP',
    lira: 'LIRA',
  };

  const handleAddHolding = async () => {
    if (!newHolding.ticker?.trim()) return;

    await addHolding(account.id, newHolding);

    // Reset form and close modal on success
    setNewHolding({
      ticker: '',
      shares: 0,
      avg_cost: 0,
      current_price: 0,
      notes: '',
    });
    setShowAddHolding(false);
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Header */}
      <div
        className="px-4 py-3 bg-gray-50 border-b cursor-pointer flex items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
            ▶
          </span>
          <div>
            <h3 className="font-semibold">{account.name}</h3>
            <p className="text-xs text-gray-500">
              {account.institution} ••••{account.account_number_last4}
              <span className="ml-2 px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
                {accountTypeLabels[account.type] || account.type}
              </span>
            </p>
          </div>
        </div>

        <div className="text-right">
          <p className="font-semibold">{formatCurrency(totalAccountValue)}</p>
          <p className="text-xs text-gray-500">
            {formatCurrency(totalValue)} holdings + {formatCurrency(totalCash)} cash
          </p>
        </div>
      </div>

      {/* Holdings */}
      {isExpanded && (
        <div className="p-4">
          <div className="flex justify-between items-center mb-3">
            <h4 className="font-medium text-gray-700">Holdings</h4>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowAddHolding(true);
              }}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              + Add Holding
            </button>
          </div>

          <HoldingsTable
            holdings={account.holdings}
            accountId={account.id}
            onUpdateHolding={updateHolding}
          />

          {account.notes && (
            <p className="mt-3 text-sm text-gray-500 italic">{account.notes}</p>
          )}

          {/* Add Holding Modal */}
          {showAddHolding && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
              <div
                className="bg-white rounded-lg p-6 w-full max-w-md"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="text-lg font-semibold mb-4">Add New Holding</h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Ticker *</label>
                    <input
                      type="text"
                      value={newHolding.ticker}
                      onChange={(e) => setNewHolding({ ...newHolding, ticker: e.target.value.toUpperCase() })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="e.g., AAPL"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Shares</label>
                    <input
                      type="number"
                      step="0.0001"
                      value={newHolding.shares}
                      onChange={(e) => setNewHolding({ ...newHolding, shares: parseFloat(e.target.value) || 0 })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="0"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Avg Cost</label>
                      <input
                        type="number"
                        step="0.01"
                        value={newHolding.avg_cost}
                        onChange={(e) => setNewHolding({ ...newHolding, avg_cost: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="0.00"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Current Price</label>
                      <input
                        type="number"
                        step="0.01"
                        value={newHolding.current_price}
                        onChange={(e) => setNewHolding({ ...newHolding, current_price: parseFloat(e.target.value) || 0 })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        placeholder="0.00"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                    <input
                      type="text"
                      value={newHolding.notes}
                      onChange={(e) => setNewHolding({ ...newHolding, notes: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Optional notes"
                    />
                  </div>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => setShowAddHolding(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleAddHolding}
                    disabled={!newHolding.ticker?.trim()}
                    className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 text-white font-medium rounded-lg transition-colors"
                  >
                    Add Holding
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default InvestmentAccountPanel;
