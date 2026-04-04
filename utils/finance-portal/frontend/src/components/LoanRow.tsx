import { Loan } from '@finance-portal/types';
import { EditableField } from './EditableField';
import { useFinanceStore } from '../store/financeStore';
import { formatCurrency, formatPercent } from '../utils/formatters';

interface LoanRowProps {
  loan: Loan;
}

export function LoanRow({ loan }: LoanRowProps) {
  const updateLoan = useFinanceStore((state) => state.updateLoan);

  const handleUpdate = async (field: keyof Loan, value: number | string) => {
    await updateLoan(loan.id, { [field]: value });
  };

  const progress = loan.original_amount > 0
    ? ((loan.original_amount - loan.current_balance) / loan.original_amount) * 100
    : 0;

  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="py-3 px-4">
        <div>
          <p className="font-medium">{loan.name}</p>
          <p className="text-xs text-gray-500">
            {loan.institution} ••••{loan.account_number_last4}
            <span className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded text-xs capitalize">
              {loan.type}
            </span>
          </p>
        </div>
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={loan.current_balance}
          type="currency"
          onSave={(v) => handleUpdate('current_balance', v as number)}
          displayClassName="font-medium text-red-600"
        />
      </td>

      <td className="py-3 px-4 text-right text-sm text-gray-600">
        {formatCurrency(loan.original_amount)}
      </td>

      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-green-600 w-14 text-right">
            {progress.toFixed(0)}% paid
          </span>
        </div>
      </td>

      <td className="py-3 px-4 text-right text-sm">
        {formatPercent(loan.interest_rate)}
      </td>

      <td className="py-3 px-4 text-right font-medium">
        {formatCurrency(loan.monthly_payment)}
      </td>

      <td className="py-3 px-4 text-center text-sm text-gray-500">
        {loan.remaining_months} mo
      </td>
    </tr>
  );
}

export default LoanRow;
