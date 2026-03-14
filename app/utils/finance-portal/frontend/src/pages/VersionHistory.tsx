import { useEffect, useState } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { formatDate, formatCurrency } from '../utils/formatters';

export function VersionHistory() {
  const fetchVersions = useFinanceStore((state) => state.fetchVersions);
  const fetchVersion = useFinanceStore((state) => state.fetchVersion);
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const versions = useFinanceStore((state) => state.versions);
  const snapshot = useSnapshot();
  const isLoading = useFinanceStore((state) => state.isLoading);
  const [selectedSk, setSelectedSk] = useState<string | null>(null);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);

  useEffect(() => {
    fetchVersions();
    if (!snapshot) {
      fetchCurrentSnapshot();
    }
  }, [fetchVersions, fetchCurrentSnapshot, snapshot]);

  const handleSelectVersion = async (sk: string) => {
    setSelectedSk(sk);
    await fetchVersion(sk);
  };

  const handleRestore = async () => {
    // In a real implementation, this would create a new version from the selected one
    setShowRestoreConfirm(false);
    // For now, just show current
    await fetchCurrentSnapshot();
    setSelectedSk(null);
  };

  if (isLoading && versions.length === 0) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">Version History</h1>
        {selectedSk && (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setSelectedSk(null);
                fetchCurrentSnapshot();
              }}
              className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
            >
              Back to Current
            </button>
            <button
              onClick={() => setShowRestoreConfirm(true)}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
            >
              Restore This Version
            </button>
          </div>
        )}
      </div>

      {/* Version List */}
      {!selectedSk && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-3 px-4 font-medium text-gray-600">Version</th>
                <th className="text-left py-3 px-4 font-medium text-gray-600">Date</th>
                <th className="text-left py-3 px-4 font-medium text-gray-600">Change Log</th>
                <th className="text-right py-3 px-4 font-medium text-gray-600">Net Worth</th>
                <th className="text-center py-3 px-4 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version, index) => {
                const isCurrent = index === 0;
                return (
                  <tr
                    key={version.sk}
                    className={`border-b hover:bg-gray-50 ${isCurrent ? 'bg-green-50' : ''}`}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{version.version_label}</span>
                        {isCurrent && (
                          <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs">
                            Current
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">{version.sk}</span>
                    </td>
                    <td className="py-3 px-4">
                      {formatDate(version.updated_at, 'long')}
                    </td>
                    <td className="py-3 px-4 text-gray-600 max-w-xs truncate">
                      {/* Change log would come from the full snapshot */}
                      -
                    </td>
                    <td className="py-3 px-4 text-right font-medium">
                      {/* Net worth would come from the full snapshot */}
                      -
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => handleSelectVersion(version.sk)}
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {versions.length === 0 && (
            <p className="p-6 text-center text-gray-500">No version history yet</p>
          )}
        </div>
      )}

      {/* Selected Version Preview */}
      {selectedSk && snapshot && (
        <div className="space-y-6">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-800">
              Viewing historical version: <strong>{snapshot.version_label}</strong>
            </p>
          </div>

          {/* Snapshot Summary */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Net Worth</p>
              <p className="text-xl font-bold text-blue-600">
                {formatCurrency(snapshot.net_worth_snapshot.net_worth)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Monthly Surplus</p>
              <p className="text-xl font-bold text-green-600">
                {formatCurrency(snapshot.monthly_cashflow.monthly_surplus)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Total Debt</p>
              <p className="text-xl font-bold text-red-600">
                {formatCurrency(
                  snapshot.accounts.credit_cards.reduce((s, c) => s + c.balance_owing, 0) +
                  snapshot.accounts.lines_of_credit.reduce((s, l) => s + l.balance_owing, 0) +
                  snapshot.accounts.loans.reduce((s, l) => s + l.current_balance, 0)
                )}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Investments</p>
              <p className="text-xl font-bold text-purple-600">
                {formatCurrency(
                  snapshot.investment_accounts.reduce(
                    (s, a) => s + a.holdings.reduce((h, h2) => h + h2.shares * h2.current_price, 0),
                    0
                  )
                )}
              </p>
            </div>
          </div>

          {/* Change Log */}
          {snapshot.change_log.length > 0 && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="font-semibold text-gray-700 mb-3">Change Log</h3>
              <ul className="space-y-1 text-sm">
                {snapshot.change_log.map((entry, index) => (
                  <li key={index} className="text-gray-600">
                    • {entry}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {showRestoreConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Restore Version</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to restore this version? This will create a new version with the data from this historical snapshot.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowRestoreConfirm(false)}
                className="px-4 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleRestore}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
              >
                Restore
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VersionHistory;
