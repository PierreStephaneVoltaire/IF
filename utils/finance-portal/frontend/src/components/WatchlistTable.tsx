import { WatchlistItem } from '@finance-portal/types';
import { formatCurrency, formatDate } from '../utils/formatters';

interface WatchlistTableProps {
  watchlist: WatchlistItem[];
}

export function WatchlistTable({ watchlist }: WatchlistTableProps) {
  if (watchlist.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-4">Watchlist</h3>
        <p className="text-gray-500 text-center py-4">No items on watchlist</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b">
        <h3 className="font-semibold text-gray-700">Watchlist</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left py-2 px-3 font-medium text-gray-600">Ticker</th>
              <th className="text-left py-2 px-3 font-medium text-gray-600">Name</th>
              <th className="text-right py-2 px-3 font-medium text-gray-600">Target Price</th>
              <th className="text-left py-2 px-3 font-medium text-gray-600">Notes</th>
              <th className="text-right py-2 px-3 font-medium text-gray-600">Added</th>
            </tr>
          </thead>
          <tbody>
            {watchlist.map((item) => (
              <tr key={item.ticker} className="border-b hover:bg-gray-50">
                <td className="py-2 px-3 font-medium">{item.ticker}</td>
                <td className="py-2 px-3 text-gray-600">{item.name}</td>
                <td className="py-2 px-3 text-right text-blue-600 font-medium">
                  {item.target_price ? formatCurrency(item.target_price) : '-'}
                </td>
                <td className="py-2 px-3 text-gray-500 text-xs max-w-48 truncate">
                  {item.notes || '-'}
                </td>
                <td className="py-2 px-3 text-right text-gray-500 text-xs">
                  {formatDate(item.added_at, 'short')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default WatchlistTable;
