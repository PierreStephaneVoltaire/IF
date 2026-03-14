import { useSnapshot } from '../store/financeStore';
import { formatCurrency, formatDate, getGainLossClass } from '../utils/formatters';

export function NetWorthCard() {
  const snapshot = useSnapshot();

  if (!snapshot) {
    return (
      <div className="bg-white rounded-lg shadow p-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
        <div className="h-8 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  const { net_worth_snapshot } = snapshot;
  const netWorth = net_worth_snapshot.net_worth;
  const totalAssets = net_worth_snapshot.total_assets;
  const totalLiabilities = net_worth_snapshot.total_liabilities;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-gray-700">Net Worth</h3>
        <span className="text-xs text-gray-500">
          as of {formatDate(net_worth_snapshot.as_of)}
        </span>
      </div>

      <div className="mb-4">
        <span className={`text-3xl font-bold ${getGainLossClass(netWorth)}`}>
          {formatCurrency(netWorth)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Total Assets</p>
          <p className="font-semibold text-green-600">{formatCurrency(totalAssets)}</p>
        </div>
        <div>
          <p className="text-gray-500">Total Liabilities</p>
          <p className="font-semibold text-red-600">{formatCurrency(totalLiabilities)}</p>
        </div>
      </div>

      {/* Visual breakdown */}
      <div className="mt-4">
        <div className="flex h-3 rounded-full overflow-hidden bg-gray-200">
          {totalAssets > 0 && (
            <div
              className="bg-green-500"
              style={{ width: `${(totalAssets / (totalAssets + totalLiabilities)) * 100}%` }}
            />
          )}
          {totalLiabilities > 0 && (
            <div
              className="bg-red-500"
              style={{ width: `${(totalLiabilities / (totalAssets + totalLiabilities)) * 100}%` }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default NetWorthCard;
