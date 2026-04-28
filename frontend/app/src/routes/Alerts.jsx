import { useMemo, useState } from 'react';
import { alerts as allAlerts, getAlertCounts } from '../mockData.js';
import AlertsFilterBar from '../components/alerts/AlertsFilterBar.jsx';
import AlertCountsStrip from '../components/alerts/AlertCountsStrip.jsx';
import AlertsTable from '../components/alerts/AlertsTable.jsx';
import AlertDrawer from '../components/alerts/AlertDrawer.jsx';

// Severity ranking for the default sort. Higher = shown first.
const SEVERITY_RANK = { critical: 3, warning: 2, info: 1 };

const DEFAULT_FILTERS = {
  severity: 'all',
  machine_id: 'all',
  acknowledged: 'all',
  sort: 'severity',
  search: '',
};

export default function Alerts() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState(null);
  // Local override map: alert_id → boolean. Wins over the mock acknowledged flag.
  const [ackOverrides, setAckOverrides] = useState({});

  const isAck = (alert) =>
    Object.prototype.hasOwnProperty.call(ackOverrides, alert.alert_id)
      ? ackOverrides[alert.alert_id]
      : !!alert.acknowledged;

  const filtered = useMemo(() => {
    const search = filters.search.trim().toLowerCase();
    const list = allAlerts.filter((a) => {
      if (filters.severity !== 'all' && a.severity !== filters.severity) return false;
      if (filters.machine_id !== 'all' && a.machine_id !== filters.machine_id) return false;
      if (filters.acknowledged === 'acknowledged' && !isAck(a)) return false;
      if (filters.acknowledged === 'unacknowledged' && isAck(a)) return false;
      if (search) {
        const hay = `${a.title} ${a.description}`.toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });

    return list.sort((a, b) => {
      if (filters.sort === 'risk_score') return b.risk_score - a.risk_score;
      if (filters.sort === 'created_at') return b.created_at.localeCompare(a.created_at);
      // 'severity' (default) — severity DESC, then risk_score DESC tiebreaker
      const sev = (SEVERITY_RANK[b.severity] || 0) - (SEVERITY_RANK[a.severity] || 0);
      if (sev !== 0) return sev;
      return b.risk_score - a.risk_score;
    });
    // ackOverrides is intentionally a dep — it changes which rows pass the
    // acknowledged tri-state filter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, ackOverrides]);

  const counts = useMemo(() => getAlertCounts(filtered), [filtered]);

  const selectedAlert = useMemo(
    () => allAlerts.find((a) => a.alert_id === selectedId) || null,
    [selectedId]
  );

  const toggleAck = () => {
    if (!selectedAlert) return;
    const current = isAck(selectedAlert);
    setAckOverrides((prev) => ({ ...prev, [selectedAlert.alert_id]: !current }));
  };

  return (
    <div className="px-8 py-7 max-w-[1400px] flex flex-col gap-5">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
          Module 1 · Predictive maintenance
        </div>
        <h1 className="text-[24px] font-semibold text-navy tracking-tight mt-0.5">Alerts</h1>
        <p className="text-[13px] text-slate-500 mt-1 max-w-2xl">
          Fleet-wide alerts ranked by severity and predicted impact. Open any row to see the full
          recommendation, contributing sensors, and cost exposure.
        </p>
      </div>

      <AlertCountsStrip counts={counts} />

      <AlertsFilterBar
        filters={filters}
        onChange={setFilters}
        totalShown={filtered.length}
        totalAll={allAlerts.length}
      />

      <AlertsTable
        alerts={filtered}
        selectedId={selectedId}
        onSelect={setSelectedId}
        ackOverrides={ackOverrides}
      />

      <AlertDrawer
        alert={selectedAlert}
        acknowledged={selectedAlert ? isAck(selectedAlert) : false}
        onClose={() => setSelectedId(null)}
        onToggleAck={toggleAck}
      />
    </div>
  );
}