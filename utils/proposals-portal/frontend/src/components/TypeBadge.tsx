import { ProposalType, TYPE_BADGE_COLORS, TYPE_LABELS } from '../types';

interface TypeBadgeProps {
  type: ProposalType;
  className?: string;
}

export function TypeBadge({ type, className = '' }: TypeBadgeProps) {
  const colorClass = TYPE_BADGE_COLORS[type] || 'bg-gray-500';
  const label = TYPE_LABELS[type] || type;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium text-white ${colorClass} ${className}`}
    >
      {label}
    </span>
  );
}
