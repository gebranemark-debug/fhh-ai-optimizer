import { Link } from 'react-router-dom';
import { ChevronRight, AlertOctagon } from 'lucide-react';
import { SeverityPill } from './Pills.jsx';
import { formatCurrencyCompact, timeAgo, formatHours } from '../lib/format.js';
import { getMachineById } from '../mockData.js';

// Full-width "ticker" card showing top critical alerts.
// Source: GET /alerts?severity=critical&limit=3
export default function CriticalAlertsTicker({ alerts }) {
  const empty = !alerts || alerts.length === 0;
  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-red-50 text-risk-critical flex items-center justify-center">
            <AlertOctagon className="w-3.5 h-3.5" strokeWidth={2.25} />
          </div>
          <div>
            <div className="text-sm font-semibold text-navy">Critical alerts</div>
            <div className="text-[11px] text-slate-500">
              Top {alerts?.length || 0} requiring immediate attention
            </div>
          </div>
        </div>
        <Link
          to="/alerts"
          className="text-xs text-slate-500 hover:text-navy font-medium flex items-center gap-1"
        >
          View all alerts
          <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </header>

      {empty ? (
        <div className="px-5 py-10 text-center">
          <div className="text-sm text-slate-500">No critical alerts. Fleet running clean.</div>
        </div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {alerts.map((a) => (
            <AlertRow key={a.alert_id} alert={a} />
          ))}
        </ul>
      )}
    </section>
  );
}

function AlertRow({ alert }) {
  const machine = getMachineById(alert.machine_id);
  return (
    <li>
      <Link
        to={`/machines/${alert.machine_id}`}
        className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors group"
      >
        <SeverityPill severity={alert.severity} />

        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <span className="font-medium text-navy">{machine?.name || alert.machine_id}</span>
            <span>·</span>
            <span className="font-mono uppercase tracking-wide">{alert.component_id}</span>
            <span>·</span>
            <span>{timeAgo(alert.created_at)}</span>
          </div>
          <div className="text-sm text-navy font-medium truncate mt-0.5">{alert.title}</div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          {alert.predicted_failure_window_hours != null && (
            <div className="text-right hidden md:block">
              <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
                Window
              </div>
              <div className="font-mono text-sm text-risk-critical font-semibold">
                {formatHours(alert.predicted_failure_window_hours)}
              </div>
            </div>
          )}
          <div className="text-right hidden md:block">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
              At risk
            </div>
            <div className="font-mono text-sm text-navy font-semibold">
              {formatCurrencyCompact(alert.estimated_cost_if_unaddressed_usd)}
            </div>
          </div>
          <span className="text-xs font-medium text-slate-400 group-hover:text-navy flex items-center gap-1">
            View
            <ChevronRight className="w-3.5 h-3.5" />
          </span>
        </div>
      </Link>
    </li>
  );
}
