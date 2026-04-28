import { Link } from 'react-router-dom';
import { ArrowRight, Gauge, Activity } from 'lucide-react';
import { TierPill, StatusBadge } from './Pills.jsx';
import { RISK_TIER_COLORS } from '../brand/tokens.js';

// 2x2 grid of machine cards for the Overview page.
export default function MachineGrid({ machines }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {machines.map((m) => (
        <MachineCard key={m.machine_id} machine={m} />
      ))}
    </div>
  );
}

function MachineCard({ machine }) {
  const tierColor = RISK_TIER_COLORS[machine.risk_tier];
  const isMaintenance = machine.status === 'maintenance';
  return (
    <Link
      to={`/machines/${machine.machine_id}`}
      className="group bg-white rounded-xl shadow-card relative overflow-hidden hover:shadow-md transition-shadow flex"
    >
      {/* Tier accent bar */}
      <div
        className="w-[4px] shrink-0"
        style={{ backgroundColor: tierColor }}
        aria-hidden
      />

      <div className="flex-1 p-5 flex flex-col gap-4 min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-[17px] font-semibold text-navy tracking-tight truncate">
                {machine.name}
              </h3>
              <StatusBadge status={machine.status} />
            </div>
            <div className="text-xs text-slate-500 mt-0.5 truncate">{machine.location}</div>
          </div>

          <div className="text-right shrink-0">
            <div
              className="font-mono text-[44px] leading-none font-semibold tracking-tight tabular-nums"
              style={{ color: tierColor }}
            >
              {machine.risk_score}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium mt-0.5">
              risk score
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <TierPill tier={machine.risk_tier} />
          {machine.active_alerts_count > 0 && (
            <span className="text-[11px] text-slate-500">
              · {machine.active_alerts_count} active alert
              {machine.active_alerts_count === 1 ? '' : 's'}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-100">
          <Stat
            icon={Gauge}
            label="Speed"
            value={isMaintenance ? '—' : machine.current_speed_mpm.toLocaleString()}
            suffix={isMaintenance ? '' : 'm/min'}
          />
          <Stat
            icon={Activity}
            label="OEE"
            value={isMaintenance ? '—' : machine.current_oee_percent.toFixed(1)}
            suffix={isMaintenance ? '' : '%'}
          />
        </div>

        <div className="flex items-center justify-end pt-1 -mb-1">
          <span className="text-xs font-medium text-slate-500 group-hover:text-navy transition-colors flex items-center gap-1">
            View details
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}

function Stat({ icon: Icon, label, value, suffix }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-7 h-7 rounded-md bg-slate-50 flex items-center justify-center text-slate-400">
        <Icon className="w-3.5 h-3.5" strokeWidth={1.75} />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
          {label}
        </div>
        <div className="font-mono text-sm font-medium text-navy tabular-nums">
          {value}
          {suffix && <span className="text-slate-400 ml-0.5">{suffix}</span>}
        </div>
      </div>
    </div>
  );
}
