import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { CreditCardRow, LOCRow, LoanRow } from '../components';
import { formatCurrency, formatPercent } from '../utils/formatters';

export function Accounts() {
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

  const { accounts } = snapshot;
  const totalCreditCardDebt = accounts.credit_cards.reduce((sum, c) => sum + c.balance_owing, 0);
  const totalCreditLimit = accounts.credit_cards.reduce((sum, c) => sum + c.credit_limit, 0);
  const avgUtilization = totalCreditLimit > 0 ? (totalCreditCardDebt / totalCreditLimit) * 100 : 0;

  const totalLOCDebt = accounts.lines_of_credit.reduce((sum, l) => sum + l.balance_owing, 0);
  const totalLOCLimit = accounts.lines_of_credit.reduce((sum, l) => sum + l.credit_limit, 0);

  const totalLoanDebt = accounts.loans.reduce((sum, l) => sum + l.current_balance, 0);
  const totalLoanOriginal = accounts.loans.reduce((sum, l) => sum + l.original_amount, 0);

  const totalChequing = accounts.chequing.reduce((sum, a) => sum + a.balance, 0);
  const totalSavings = accounts.savings.reduce((sum, a) => sum + a.balance, 0);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Accounts</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Chequing</p>
          <p className="text-xl font-bold text-green-600">{formatCurrency(totalChequing)}</p>
          <p className="text-xs text-gray-500">{accounts.chequing.length} accounts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Savings</p>
          <p className="text-xl font-bold text-green-600">{formatCurrency(totalSavings)}</p>
          <p className="text-xs text-gray-500">{accounts.savings.length} accounts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Revolving Debt</p>
          <p className="text-xl font-bold text-red-600">{formatCurrency(totalCreditCardDebt + totalLOCDebt)}</p>
          <p className="text-xs text-gray-500">
            {formatPercent(avgUtilization)} utilization
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">Installment Debt</p>
          <p className="text-xl font-bold text-red-600">{formatCurrency(totalLoanDebt)}</p>
          <p className="text-xs text-gray-500">
            {totalLoanOriginal > 0 ? ((totalLoanOriginal - totalLoanDebt) / totalLoanOriginal * 100).toFixed(0) : 0}% paid off
          </p>
        </div>
      </div>

      {/* Chequing Accounts */}
      {accounts.chequing.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b">
            <h2 className="font-semibold text-gray-700">Chequing Accounts</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Account</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Balance</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Primary</th>
              </tr>
            </thead>
            <tbody>
              {accounts.chequing.map((account) => (
                <tr key={account.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4">
                    <p className="font-medium">{account.name}</p>
                    <p className="text-xs text-gray-500">{account.institution} ••••{account.account_number_last4}</p>
                  </td>
                  <td className="py-3 px-4 text-right font-medium text-green-600">
                    {formatCurrency(account.balance)}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {account.is_primary && (
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">Primary</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Savings Accounts */}
      {accounts.savings.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b">
            <h2 className="font-semibold text-gray-700">Savings Accounts</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Account</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Balance</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Rate</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Purpose</th>
              </tr>
            </thead>
            <tbody>
              {accounts.savings.map((account) => (
                <tr key={account.id} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4">
                    <p className="font-medium">{account.name}</p>
                    <p className="text-xs text-gray-500">{account.institution} ••••{account.account_number_last4}</p>
                  </td>
                  <td className="py-3 px-4 text-right font-medium text-green-600">
                    {formatCurrency(account.balance)}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-600">
                    {formatPercent(account.interest_rate)}
                  </td>
                  <td className="py-3 px-4 text-gray-600">
                    {account.purpose || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Credit Cards */}
      {accounts.credit_cards.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="font-semibold text-gray-700">Credit Cards</h2>
            <span className="text-sm text-gray-500">
              Total: <span className="font-medium text-red-600">{formatCurrency(totalCreditCardDebt)}</span>
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Card</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Balance</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Limit</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Utilization</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">APR</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Target Payment</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Due</th>
              </tr>
            </thead>
            <tbody>
              {accounts.credit_cards.map((card) => (
                <CreditCardRow key={card.id} card={card} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Lines of Credit */}
      {accounts.lines_of_credit.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="font-semibold text-gray-700">Lines of Credit</h2>
            <span className="text-sm text-gray-500">
              Total: <span className="font-medium text-red-600">{formatCurrency(totalLOCDebt)}</span>
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Account</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Balance</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Limit</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Utilization</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">APR</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Target Payment</th>
              </tr>
            </thead>
            <tbody>
              {accounts.lines_of_credit.map((loc) => (
                <LOCRow key={loc.id} loc={loc} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Loans */}
      {accounts.loans.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center">
            <h2 className="font-semibold text-gray-700">Loans</h2>
            <span className="text-sm text-gray-500">
              Total: <span className="font-medium text-red-600">{formatCurrency(totalLoanDebt)}</span>
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left py-2 px-4 font-medium text-gray-600">Loan</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Balance</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Original</th>
                <th className="text-left py-2 px-4 font-medium text-gray-600">Progress</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Rate</th>
                <th className="text-right py-2 px-4 font-medium text-gray-600">Payment</th>
                <th className="text-center py-2 px-4 font-medium text-gray-600">Remaining</th>
              </tr>
            </thead>
            <tbody>
              {accounts.loans.map((loan) => (
                <LoanRow key={loan.id} loan={loan} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default Accounts;
