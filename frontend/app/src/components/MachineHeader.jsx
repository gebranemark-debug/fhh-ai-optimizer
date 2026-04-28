import { Link } from 'react-router-dom';
import { ChevronLeft, Gauge, Activity, MapPin } from 'lucide-react';
import { TierPill, StatusBadge } from './Pills.jsx';
import { RISK_TIER_COLORS } from '../brand/tokens.js';

export default function MachineHeader({ machine }) {
  const tierColor = RISK_TIER_COLORS[machine.risk_tier];
  const isMaint = machine.status === 'maintenance';
  return (
    <div className="bg-white rounded-xl shadow-card overflow-hidden">
      <div className="h-1" style={{ backgroundColor: tierColor }} />
      <div className="p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <Link to="/" className="text-xs text-slate-500 hover:text-navy flex items-center gap-1">
            <ChevronLeft className="w-3.5 h-3.5" /> Back to fleet
          </Link>
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="font-mono">{machine.model}</span>
            <span>·</span>
            <span>installed {new Date(machine.installation_date).getFullYear()}</span>
          </div>
        </div>

        <div className="flex items-end justify-between gap-6">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">Machine</div>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              <h1 className="text-[28px] font-semibold text-navy tracking-tight">{machine.name}</h1>
              <StatusBadge status={machine.status} />
            </div>
            <div className="text-sm text-slate-500 mt-1 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5" /> {machine.location}
            </div>
          </div>

          <div className="flex items-center gap-6 shrink-0">
            <Stat label="Speed" value={isMaint ? '—' : machine.current_speed_mpm.toLocaleString()} suffix={isMaint ? '' : 'm/min'} icon={Gauge} />
            <Stat label="OEE" value={isMaint ? '—' : machine.current_oee_percent.toFixed(1)} suffix={isMaint ? '' : '%'} icon={Activity} />
            <div className="text-right pl-6 border-l border-slate-100">
              <div className="font-mono text-[44px] leading-none font-semibold tracking-tight tabular-nums" style={{ color: tierColor }}>
                {machine.risk_score}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium mt-1">risk score</div>
              <div className="mt-1.5"><TierPill tier={machine.risk_tier} /></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, suffix, icon: Icon }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-8 h-8 rounded-md bg-slate-50 flex items-center justify-center text-slate-400">
        <Icon className="w-4 h-4" strokeWidth={1.75} />
      </div>
      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">{label}</div>
        <div className="font-mono text-base font-medium text-navy tabular-nums">
          {value}
          {suffix && <span className="text-slate-400 ml-1 text-xs">{suffix}</span>}
        </div>
      </div>
    </div>
  );
}