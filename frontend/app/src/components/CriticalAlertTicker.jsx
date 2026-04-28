import { Link } from 'react-router-dom';
import { AlertOctagon, ArrowRight, Clock } from 'lucide-react';
import { SEVERITY_COLORS } from '../brand/tokens.js';
import { formatCurrencyUsd, formatRelativeTime, severityPillClasses } from '../lib/format.js';
import { getMachineById } from '../mockData.js';

// Critical alerts ticker — full-width card on the Overview page.
// Consumes shape from GET /alerts?severity=critical&limit=3.
export default function CriticalAlertTicker({ alerts }) {
  if (!alerts.length) {
    return (
      <section className="bg-white rounded-xl shadow-card p-6">
        <div className="flex items-center gap-2 text-emerald-700">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <div className="text-sm font-medium">No critical alerts.</div>
          <div className="text-sm text-slate-500">All systems within tolerance.</div>
        </div>
      </section>
    );
  }

  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <span
            className="w-7 h-7 rounded-md flex items-center justify-center"
            style={{ backgroundColor: SEVERITY_COLORS.critical + '14' }}
          >
            <AlertOctagon
              className="w-[15px] h-[15px]"
              style={{ color: SEVERITY_COLORS.critical }}
              strokeWidth={2}
            />
          </span>
          <div>
            <div className="text-[13px] font-semibold text-navy">
              Critical alerts
            </div>
            <div className="text-[11px] text-slate-500">
              Top {alerts.length} requiring immediate intervention
            </div>
          </div>
        </div>
        <Link
          to="/alerts"
          className="text-[12px] font-medium text-navy hover:text-gold-deep flex items-center gap-1 transition-colors"
        >
          View all alerts <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      <ul className="divide-y divide-slate-100">
        {alerts.map((a) => {
          const m = getMachineById(a.machine_id);
          return (
            <li key={a.alert_id}>
              <Link
                to="/alerts"
                className="grid grid-cols-12 items-center gap-4 px-6 py-4 hover:bg-canvas transition-colors"
              >
                <div className="col-span-12 md:col-span-1">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${severityPillClasses(
                      a.severity
                    )}`}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: SEVERITY_COLORS[a.severity] }}
                    />
                    {a.severity}
                  </span>
                </div>

                <div className="col-span-12 md:col-span-3">
                  <div className="text-[13px] font-semibold text-navy">
                    {m?.name || a.machine_id}
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    {a.machine_id} · {a.component_id}
                  </div>
                </div>

                <div className="col-span-12 md:col-span-5">
                  <div className="text-[13px] text-navy line-clamp-1">
                    {a.title}
                  </div>
                  {a.predicted_failure_window_hours != null && (
                    <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Failure window: {a.predicted_failure_window_hours}h
                    </div>
                  )}
                </div>

                <div className="col-span-6 md:col-span-2 text-right">
                  <div className="font-mono text-[13px] text-red-500 font-semibold">
                    {formatCurrencyUsd(a.estimated_cost_if_unaddressed_usd)}
                  </div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                    if ignored
                  </div>
                </div>

                <div className="col-span-6 md:col-span-1 text-right text-[11px] text-slate-500">
                  {formatRelativeTime(a.created_at)}
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
