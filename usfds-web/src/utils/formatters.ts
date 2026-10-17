/**
 * Format bytes into human-readable strings (KB, MB, GB)
 */
export function formatBytes(bytes?: number, decimals: number = 2): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

/**
 * Format raw numbers with thousands separator
 */
export function formatNumber(num?: number): string {
  if (num === undefined || num === null) return '0';
  return new Intl.NumberFormat('en-US').format(num);
}

/**
 * Format decimal to percentage string
 */
export function formatPercent(value?: number, decimals: number = 1): string {
  if (value === undefined || value === null) return '0%';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format ISO date string into readable local representation
 */
export function formatDate(dateString?: string): string {
  if (!dateString) return 'N/A';
  try {
    const d = new Date(dateString);
    return new Intl.DateTimeFormat('vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return dateString;
  }
}

/**
 * Truncate long strings with ellipsis
 */
export function truncate(text?: string, length: number = 30): string {
  if (!text) return '';
  if (text.length <= length) return text;
  return `${text.slice(0, length)}...`;
}
