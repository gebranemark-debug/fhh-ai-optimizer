import { machines, alerts, kpisOverview, getCriticalAlerts } from '../mockData.js';
import KpiStrip from '../components/KpiStrip.jsx';
import MachineGrid from '../components/MachineGrid.jsx';
import CriticalAlertsTicker from '../components/CriticalAlertsTicker.jsx';

export default function Overview() {
  // In a real app these would be 3 separate fetches:
  //   GET /kpis/overview
  //   GET /machines
  //   GET /alerts?severity=critical&limit=3
  const kpis = kpisOverview;
  const fleet = machines;
  const criticalAlerts = getCriticalAlerts(3);

  return (
    <div className="px-8 py-7 max-w-[1200px]">
      <header className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
            Fleet
          </div>
          <h1 className="text-[28px] font-semibold text-navy tracking-tight mt-1">
            Overview
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Live health across all four production lines.
          </p>
        </div>
        <div className="text-right hidden md:block">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
            Last updated
          </div>
          <div className="font-mono text-xs text-slate-600">
            {new Date(kpis.last_updated).toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              hour12: false,
              timeZone: 'UTC',
            })}{' '}
            UTC
          </div>
        </div>
      </header>

      <KpiStrip kpis={kpis} />

      <div className="mt-6">
        <SectionTitle
          title="Production lines"
          subtitle={`${fleet.length} machines · sorted by risk`}
        />
        <MachineGrid
          machines={[...fleet].sort((a, b) => b.risk_score - a.risk_score)}
        />
      </div>

      <div className="mt-6">
        <CriticalAlertsTicker alerts={criticalAlerts} />
      </div>
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="flex items-baseline justify-between mb-3">
      <h2 className="text-sm font-semibold text-navy">{title}</h2>
      {subtitle && <div className="text-[11px] text-slate-400">{subtitle}</div>}
    </div>
  );
}
