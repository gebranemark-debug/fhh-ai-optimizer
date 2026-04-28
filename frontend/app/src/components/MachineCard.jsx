import { Link } from 'react-router-dom';
import { ArrowRight, Gauge } from 'lucide-react';
import { RISK_TIER_COLORS, RISK_TIER_LABELS } from '../brand/tokens.js';
import { tierPillClasses, STATUS_LABELS, STATUS_DOT_COLOR } from '../lib/format.js';

// Single machine card — used in the 2x2 grid on the Overview page.
// Consumes a Machine object from GET /machines.
export default function MachineCard({ machine }) {
  const tierColor = RISK_TIER_COLORS[machine.risk_tier];

  return (
    <Link
      to={`/machines/${machine.machine_id}`}
      className="group block bg-white rounded-xl shadow-card relative overflow-hidden hover:shadow-md transition-shadow"
    >
      {/* Tier accent border-left (4px) */}
      <span
        aria-hidden
        className="absolute left-0 top-0 bottom-0 w-[4px]"
        style={{ backgroundColor: tierColor }}
      />

      <div className="p-6 pl-7">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-[17px] font-semibold text-navy tracking-tight truncate">
                {machine.name}
              </h3>
              <span className="text-[10px] font-mono text-slate-400 truncate">
                {machine.machine_id}
              </span>
            </div>
            <div className="text-[12px] text-slate-500 mt-0.5 truncate">
              {machine.location}
            </div>
          </div>

          {/* Status badge */}
          <div className="shrink-0 flex items-center gap-1.5 text-[11px] text-slate-600 bg-slate-50 px-2 py-1 rounded-md ring-1 ring-slate-200">
            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT_COLOR[machine.status]}`} />
            <span className="font-medium">{STATUS_LABELS[machine.status]}</span>
          </div>
        </div>

        {/* Risk score */}
        <div className="mt-5 flex items-end justify-between gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold">
              Risk score
            </div>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span
                className="font-mono text-[48px] leading-none font-semibold"
                style={{ color: tierColor }}
              >
                {machine.risk_score}
              </span>
              <span className="text-slate-400 text-sm font-mono">/100</span>
            </div>
          </div>

          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ${tierPillClasses(
              machine.risk_tier
            )}`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: tierColor }}
            />
            {RISK_TIER_LABELS[machine.risk_tier]}
          </span>
        </div>

        {/* Metrics row */}
        <div className="mt-5 grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-canvas px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
              Speed
            </div>
            <div className="font-mono text-[15px] text-navy mt-0.5">
              {machine.current_speed_mpm.toLocaleString()}
              <span className="text-[11px] text-slate-400 ml-1">m/min</span>
            </div>
          </div>
          <div className="rounded-lg bg-canvas px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
              OEE
            </div>
            <div className="font-mono text-[15px] text-navy mt-0.5">
              {machine.current_oee_percent.toFixed(1)}
              <span className="text-[11px] text-slate-400 ml-1">%</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
            <Gauge className="w-3.5 h-3.5 text-slate-400" />
            <span>
              {machine.active_alerts_count} active alert
              {machine.active_alerts_count === 1 ? '' : 's'}
            </span>
          </div>
          <div className="flex items-center gap-1 text-[12px] font-medium text-navy group-hover:text-gold-deep transition-colors">
            View details
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </div>
        </div>
      </div>
    </Link>
  );
}
