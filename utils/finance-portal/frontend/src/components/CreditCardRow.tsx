import { CreditCard } from '@finance-portal/types';
import { EditableField } from './EditableField';
import { useFinanceStore } from '../store/financeStore';
import { formatCurrency, formatPercent, getUtilizationClass, formatAPR } from '../utils/formatters';

interface CreditCardRowProps {
  card: CreditCard;
}

export function CreditCardRow({ card }: CreditCardRowProps) {
  const updateCreditCard = useFinanceStore((state) => state.updateCreditCard);

  const handleUpdate = async (field: keyof CreditCard, value: number | string) => {
    await updateCreditCard(card.name, { [field]: value });
  };

  const utilizationClass = getUtilizationClass(card.utilization_pct);

  return (
    <tr className="border-b hover:bg-gray-50">
      <td className="py-3 px-4">
        <div>
          <p className="font-medium">{card.name}</p>
          <p className="text-xs text-gray-500">{card.institution} ••••{card.account_number_last4}</p>
        </div>
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={card.balance_owing}
          type="currency"
          onSave={(v) => handleUpdate('balance_owing', v as number)}
          displayClassName="font-medium text-red-600"
        />
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={card.credit_limit}
          type="currency"
          onSave={(v) => handleUpdate('credit_limit', v as number)}
        />
      </td>

      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full ${
                card.utilization_pct < 30 ? 'bg-green-500' :
                card.utilization_pct < 50 ? 'bg-yellow-500' :
                card.utilization_pct < 75 ? 'bg-orange-500' : 'bg-red-500'
              }`}
              style={{ width: `${Math.min(card.utilization_pct, 100)}%` }}
            />
          </div>
          <span className={`text-sm font-medium ${utilizationClass} w-14 text-right`}>
            {formatPercent(card.utilization_pct)}
          </span>
        </div>
      </td>

      <td className="py-3 px-4 text-right text-sm">
        <EditableField
          value={card.apr}
          type="number"
          step={0.01}
          decimals={2}
          onSave={(v) => handleUpdate('apr', v as number)}
          formatter={(v) => formatAPR(v as number)}
          displayClassName="text-gray-700"
        />
      </td>

      <td className="py-3 px-4 text-right">
        <EditableField
          value={card.target_payment}
          type="currency"
          onSave={(v) => handleUpdate('target_payment', v as number)}
          displayClassName="font-medium text-blue-600"
        />
      </td>

      <td className="py-3 px-4 text-center text-sm text-gray-500">
        {card.due_date ? `${card.due_date}${getOrdinalSuffix(card.due_date)}` : '-'}
      </td>
    </tr>
  );
}

function getOrdinalSuffix(day: number): string {
  if (day >= 11 && day <= 13) return 'th';
  switch (day % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
}

export default CreditCardRow;
