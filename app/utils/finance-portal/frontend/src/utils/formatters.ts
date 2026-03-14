/**
 * Currency formatter for CAD
 */
export function formatCurrency(amount: number, options?: {
  compact?: boolean;
  showSign?: boolean;
}): string {
  const { compact = false, showSign = false } = options || {};

  const formatter = new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    notation: compact ? 'compact' : 'standard',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  let formatted = formatter.format(Math.abs(amount));

  if (showSign && amount !== 0) {
    formatted = amount > 0 ? `+${formatted}` : `-${formatted}`;
  } else if (amount < 0) {
    formatted = `-${formatted}`;
  }

  return formatted;
}

/**
 * Percentage formatter
 */
export function formatPercent(value: number, decimals: number = 1): string {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Date formatter
 */
export function formatDate(date: string | Date, format: 'short' | 'long' | 'relative' = 'short'): string {
  const d = typeof date === 'string' ? new Date(date) : date;

  if (format === 'relative') {
    return formatRelativeDate(d);
  }

  const options: Intl.DateTimeFormatOptions = format === 'long'
    ? { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { year: 'numeric', month: 'short', day: 'numeric' };

  return new Intl.DateTimeFormat('en-CA', options).format(d);
}

/**
 * Relative date formatter (e.g., "2 hours ago", "3 days ago")
 */
export function formatRelativeDate(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

  return formatDate(date, 'short');
}

/**
 * Format utilization with color class
 */
export function getUtilizationClass(utilization: number): string {
  if (utilization < 30) return 'text-green-600';
  if (utilization < 50) return 'text-yellow-600';
  if (utilization < 75) return 'text-orange-600';
  return 'text-red-600';
}

/**
 * Format gain/loss with color class
 */
export function getGainLossClass(value: number): string {
  if (value > 0) return 'text-green-600';
  if (value < 0) return 'text-red-600';
  return 'text-gray-600';
}

/**
 * Format gain/loss with sign
 */
export function formatGainLoss(value: number, prefix: string = ''): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${prefix}${formatCurrency(value)}`;
}

/**
 * Format large numbers with K/M suffix
 */
export function formatCompact(amount: number): string {
  if (Math.abs(amount) >= 1_000_000) {
    return `${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(amount) >= 1_000) {
    return `${(amount / 1_000).toFixed(1)}K`;
  }
  return amount.toFixed(0);
}

/**
 * Format APR as percentage
 */
export function formatAPR(apr: number): string {
  return `${apr.toFixed(2)}% APR`;
}

/**
 * Format phone number
 */
export function formatPhone(phone: string): string {
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 10) {
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
  }
  return phone;
}

/**
 * Parse currency string to number
 */
export function parseCurrency(value: string): number {
  const cleaned = value.replace(/[^0-9.-]/g, '');
  return parseFloat(cleaned) || 0;
}

/**
 * Format number with commas
 */
export function formatNumber(value: number, decimals: number = 0): string {
  return new Intl.NumberFormat('en-CA', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}
