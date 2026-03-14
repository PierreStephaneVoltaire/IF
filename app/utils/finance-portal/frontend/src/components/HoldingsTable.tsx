import { Holding } from '@finance-portal/types';
import { EditableField } from './EditableField';
import { formatCurrency, getGainLossClass, formatDate } from '../utils/formatters';

interface HoldingsTableProps {
  holdings: Holding[];
  accountId: string;
  onUpdateHolding: (accountId: string, ticker: string, updates: Partial<Holding>) => Promise<void>;
}

export function HoldingsTable({ holdings, accountId, onUpdateHolding }: HoldingsTableProps) {
  if (holdings.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No holdings in this account
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-left py-2 px-3 font-medium text-gray-600">Ticker</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Shares</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Avg Cost</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Current</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Market Value</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Gain/Loss</th>
            <th className="text-right py-2 px-3 font-medium text-gray-600">Updated</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => {
            const marketValue = holding.shares * holding.current_price;
            const costBasis = holding.shares * holding.avg_cost;
            const gainLoss = marketValue - costBasis;
            const gainLossPct = costBasis > 0 ? (gainLoss / costBasis) * 100 : 0;

            return (
              <tr key={holding.ticker} className="border-b hover:bg-gray-50">
                <td className="py-2 px-3">
                  <span className="font-medium">{holding.ticker}</span>
                  {holding.notes && (
                    <p className="text-xs text-gray-500 truncate max-w-32">{holding.notes}</p>
                  )}
                </td>

                <td className="py-2 px-3 text-right">
                  <EditableField
                    value={holding.shares}
                    type="number"
                    decimals={4}
                    onSave={(v) => onUpdateHolding(accountId, holding.ticker, { shares: v as number })}
                  />
                </td>

                <td className="py-2 px-3 text-right">
                  <EditableField
                    value={holding.avg_cost}
                    type="currency"
                    onSave={(v) => onUpdateHolding(accountId, holding.ticker, { avg_cost: v as number })}
                  />
                </td>

                <td className="py-2 px-3 text-right">
                  <EditableField
                    value={holding.current_price}
                    type="currency"
                    onSave={(v) => onUpdateHolding(accountId, holding.ticker, { current_price: v as number })}
                  />
                </td>

                <td className="py-2 px-3 text-right font-medium">
                  {formatCurrency(marketValue)}
                </td>

                <td className="py-2 px-3 text-right">
                  <div className={getGainLossClass(gainLoss)}>
                    <span className="font-medium">
                      {formatCurrency(Math.abs(gainLoss), { showSign: gainLoss > 0 })}
                    </span>
                    <span className="text-xs ml-1">
                      ({gainLossPct > 0 ? '+' : ''}{gainLossPct.toFixed(1)}%)
                    </span>
                  </div>
                </td>

                <td className="py-2 px-3 text-right text-xs text-gray-500">
                  {holding.last_price_update ? formatDate(holding.last_price_update, 'relative') : '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="bg-gray-50 font-medium">
            <td className="py-2 px-3">Total</td>
            <td colSpan={3}></td>
            <td className="py-2 px-3 text-right">
              {formatCurrency(holdings.reduce((sum, h) => sum + (h.shares * h.current_price), 0))}
            </td>
            <td className="py-2 px-3 text-right">
              <span className={getGainLossClass(holdings.reduce((sum, h) => sum + (h.shares * (h.current_price - h.avg_cost)), 0))}>
                {formatCurrency(Math.abs(holdings.reduce((sum, h) => sum + (h.shares * (h.current_price - h.avg_cost)), 0)), { showSign: true })}
              </span>
            </td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export default HoldingsTable;
