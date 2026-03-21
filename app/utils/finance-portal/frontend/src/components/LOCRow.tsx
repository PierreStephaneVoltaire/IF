import { LineOfCredit } from '@finance-portal/types';
import { EditableField } from './EditableField';
import { useFinanceStore } from '../store/financeStore';
import { formatCurrency, formatAPR } from '../utils/formatters';

interface LOCRowProps {
  loc: LineOfCredit;
}

export function LOCRow({ loc }: LOCRowProps) {
  const updateLineOfCredit = useFinanceStore((state) => state.updateLineOfCredit);

  const handleUpdate = async (field: keyof LineOfCredit, value: number | string) => {
    await updateLineOfCredit(loc.name, { [field]: value });
  };

  const utilization = loc.credit_limit > 0 ? (loc.balance_owing / loc.credit_limit) * 100 : 0;

  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="py-3 px-4">
        <div>
          <p className="font-medium">{loc.name}</p>
          <p className="text-xs text-gray-500">
            {loc.institution} ••••{loc.account_number_last4}
            <span className="ml-2 px-1.5 py-0.5 bg-gray-100 rounded text-xs capitalize">
              {loc.type.replace('_', ' ')}
            </span>
          </p>
        </div>
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={loc.balance_owing}
          type="currency"
          onSave={(v) => handleUpdate('balance_owing', v as number)}
          displayClassName="font-medium text-red-600"
        />
      </td>

      <td className="py-3 px-4 text-right">
        {formatCurrency(loc.credit_limit)}
      </td>

      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${
                utilization < 30 ? 'bg-green-500' :
                utilization < 50 ? 'bg-yellow-500' :
                utilization < 75 ? 'bg-orange-500' : 'bg-red-500'
              }`}
              style={{ width: `${Math.min(utilization, 100)}%` }}
            />
          </div>
          <span className={`text-sm font-medium w-14 text-right ${
            utilization < 30 ? 'text-green-600' :
            utilization < 50 ? 'text-yellow-600' :
            utilization < 75 ? 'text-orange-600' : 'text-red-600'
          }`}>
            {utilization.toFixed(1)}%
          </span>
        </div>
      </td>

      <td className="py-3 px-4 text-right text-sm">
        {formatAPR(loc.apr)}
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={loc.target_payment}
          type="currency"
          onSave={(v) => handleUpdate('target_payment', v as number)}
          displayClassName="font-medium text-blue-600"
        />
      </td>
    </tr>
  );
}

export default LOCRow;
