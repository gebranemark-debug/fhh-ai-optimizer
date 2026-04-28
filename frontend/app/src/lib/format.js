// Small shared formatting helpers — kept in one place so all KPI cards,
// alert rows, and detail drawers format dollars / hours / time-ago identically.

export function formatCurrencyCompact(usd) {
  if (usd == null || isNaN(usd)) return '—';
  const abs = Math.abs(usd);
  if (abs >= 1_000_000) return `$${(usd / 1_000_000).toFixed(abs >= 10_000_000 ? 1 : 2)}M`;
  if (abs >= 1_000) return `$${Math.round(usd / 1000)}K`;
  return `$${usd}`;
}

export function formatCurrencyFull(usd) {
  if (usd == null || isNaN(usd)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(usd);
}

export function formatHours(hours) {
  if (hours == null || isNaN(hours)) return '—';
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  return rem === 0 ? `${days}d` : `${days}d ${rem}h`;
}

export function timeAgo(iso) {
  if (!iso) return '';
  // Anchor "now" to the contract's example timestamp so mock data reads
  // consistently regardless of the user's actual clock.
  const NOW = new Date('2026-04-28T10:00:00Z').getTime();
  const t = new Date(iso).getTime();
  const diff = Math.max(0, NOW - t);
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
