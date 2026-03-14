import { InvestmentAccount } from '@finance-portal/types';
import { HoldingsTable } from './HoldingsTable';
import { useFinanceStore } from '../store/financeStore';
import { formatCurrency } from '../utils/formatters';
import { useState } from 'react';

interface InvestmentAccountPanelProps {
  account: InvestmentAccount;
}

export function InvestmentAccountPanel({ account }: InvestmentAccountPanelProps) {
  const updateHolding = useFinanceStore((state) => state.updateHolding);
  const [isExpanded, setIsExpanded] = useState(true);

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
          <HoldingsTable
            holdings={account.holdings}
            accountId={account.id}
            onUpdateHolding={updateHolding}
          />

          {account.notes && (
            <p className="mt-3 text-sm text-gray-500 italic">{account.notes}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default InvestmentAccountPanel;
