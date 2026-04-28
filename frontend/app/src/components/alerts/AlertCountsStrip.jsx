import { AlertOctagon, AlertTriangle, Eye } from 'lucide-react';
import { RISK_TIER_COLORS } from '../../brand/tokens.js';

// Three-chip strip showing severity counts for the *currently filtered* list.
// Keeps the user oriented when filters narrow the table — e.g. "of these 4
// shown, 1 critical / 2 warning / 1 info".

export default function AlertCountsStrip({ counts }) {
  const cells = [
    { key: 'critical', label: 'Critical', count: counts.critical, color: RISK_TIER_COLORS.critical, icon: AlertOctagon },
    { key: 'warning',  label: 'Warning',  count: counts.warning,  color: RISK_TIER_COLORS.warning,  icon: AlertTriangle },
    { key: 'watch',    label: 'Info',     count: counts.watch,    color: '#3B82F6',                 icon: Eye },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {cells.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.key}
            className="bg-white rounded-xl shadow-card p-4 flex items-center gap-3 border-l-2"
            style={{ borderLeftColor: c.color }}
          >
            <div
              className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
              style={{ backgroundColor: `${c.color}14`, color: c.color }}
            >
              <Icon className="w-4 h-4" strokeWidth={2} />
            </div>
            <div className="flex items-baseline gap-2 min-w-0">
              <span className="font-mono text-[26px] font-semibold tabular-nums leading-none" style={{ color: c.color }}>
                {c.count}
              </span>
              <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">{c.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}