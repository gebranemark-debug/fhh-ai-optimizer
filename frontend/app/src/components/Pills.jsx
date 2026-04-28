import { TIER_PILL_CLASSES, RISK_TIER_LABELS, SEVERITY_PILL_CLASSES } from '../brand/tokens.js';

const STATUS_CLASSES = {
  running: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  idle: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
  maintenance: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  offline: 'bg-red-50 text-red-700 ring-1 ring-red-200',
};

const STATUS_DOT = {
  running: 'bg-emerald-500',
  idle: 'bg-slate-400',
  maintenance: 'bg-amber-500',
  offline: 'bg-red-500',
};

export function TierPill({ tier, size = 'md' }) {
  const sizing = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-[11px] px-2 py-0.5';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold uppercase tracking-wide ${sizing} ${TIER_PILL_CLASSES[tier]}`}
    >
      {RISK_TIER_LABELS[tier]}
    </span>
  );
}

export function SeverityPill({ severity }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full text-[10px] px-2 py-0.5 font-semibold uppercase tracking-wide ${SEVERITY_PILL_CLASSES[severity]}`}
    >
      {severity}
    </span>
  );
}

export function StatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full text-[10px] px-2 py-0.5 font-semibold uppercase tracking-wide ${STATUS_CLASSES[status]}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {status}
    </span>
  );
}
