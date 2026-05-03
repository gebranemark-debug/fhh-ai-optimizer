import { useEffect, useState } from 'react';
import { getKpisOverview, getMachines, getAlerts, getCostSavings } from '../lib/api.js';
import KpiStrip from '../components/KpiStrip.jsx';
import MachineGrid from '../components/MachineGrid.jsx';
import CriticalAlertsTicker from '../components/CriticalAlertsTicker.jsx';

export default function Overview() {
  // Three independent fetches. Each piece lands when it lands — partial
  // failure on one section doesn't block the others from rendering.
const [kpis, setKpis] = useState({ status: 'loading', data: null, error: null });
const [fleet, setFleet] = useState({ status: 'loading', data: null, error: null });
const [alerts, setAlerts] = useState({ status: 'loading', data: null, error: null });
const [costSavings, setCostSavings] = useState({ status: 'loading', data: null, error: null });

  useEffect(() => {
    let cancelled = false;

    getKpisOverview()
      .then((data) => { if (!cancelled) setKpis({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setKpis({ status: 'error', data: null, error }); });

    getMachines()
      .then((data) => { if (!cancelled) setFleet({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setFleet({ status: 'error', data: null, error }); });

    getAlerts()
      .then((data) => { if (!cancelled) setAlerts({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setAlerts({ status: 'error', data: null, error }); });

    getCostSavings('mtd')
      .then((data) => { if (!cancelled) setCostSavings({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setCostSavings({ status: 'error', data: null, error }); });

    return () => { cancelled = true; };
  }, []);

  // Derive the critical-alerts ticker payload from the full alerts list,
  // mirroring mockData.getCriticalAlerts(3): severity==='critical', top 3.
  const criticalAlerts = alerts.status === 'ok'
    ? alerts.data.filter((a) => a.severity === 'critical').slice(0, 3)
    : [];

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
            {kpis.status === 'ok' ? formatTimestamp(kpis.data.last_updated) : '—'}
          </div>
        </div>
      </header>
{kpis.status === 'ok' ? (
        <KpiStrip
          kpis={{
            ...kpis.data,
            // Override with the canonical cost-savings value when it's loaded.
            // /kpis/overview returns a different (stale) MTD figure than
            // /kpis/cost-savings?window=mtd; the cost-savings endpoint is
            // canonical because it ties to the auditable predictions trail.
            estimated_cost_saved_usd_mtd:
              costSavings.status === 'ok'
                ? costSavings.data.estimated_cost_saved_usd
                : kpis.data.estimated_cost_saved_usd_mtd,
          }}
        />
      ) : kpis.status === 'error' ? (
        <SectionError label="KPI strip" />
      ) : (
        <div className="h-[100px] rounded-xl bg-slate-100 animate-pulse" />
      )}

      <div className="mt-6">
        <SectionTitle
          title="Production lines"
          subtitle={fleet.status === 'ok' ? `${fleet.data.length} machines · sorted by risk` : ''}
        />
        {fleet.status === 'ok' ? (
          <MachineGrid
            machines={[...fleet.data].sort((a, b) => b.risk_score - a.risk_score)}
          />
        ) : fleet.status === 'error' ? (
          <SectionError label="Production lines" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-[180px] rounded-xl bg-slate-100 animate-pulse" />
            ))}
          </div>
        )}
      </div>

      <div className="mt-6">
        {alerts.status === 'ok' ? (
          <CriticalAlertsTicker alerts={criticalAlerts} />
        ) : alerts.status === 'error' ? (
          <SectionError label="Critical alerts" />
        ) : (
          <div className="h-[80px] rounded-xl bg-slate-100 animate-pulse" />
        )}
      </div>
    </div>
  );
}

function formatTimestamp(iso) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }) + ' UTC';
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="flex items-baseline justify-between mb-3">
      <h2 className="text-sm font-semibold text-navy">{title}</h2>
      {subtitle && <div className="text-[11px] text-slate-400">{subtitle}</div>}
    </div>
  );
}

function SectionError({ label }) {
  return (
    <div className="rounded-xl bg-red-50 ring-1 ring-red-200 p-4 text-[12px] text-red-800">
      Couldn't load {label}. Check the network and refresh.
    </div>
  );
}