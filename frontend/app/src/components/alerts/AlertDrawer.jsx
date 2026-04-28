import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X, ExternalLink, AlertOctagon, Clock, DollarSign, Activity, Wrench } from 'lucide-react';
import { SeverityPill } from '../Pills.jsx';
import { COMPONENT_LABELS, machines, sensorsByMachine } from '../../mockData.js';
import { formatCurrencyCompact, formatCurrencyFull, formatHours, timeAgo } from '../../lib/format.js';
import { RISK_TIER_COLORS } from '../../brand/tokens.js';

// Right-slide drawer with full alert detail. Renders nothing when alert is
// null. Click backdrop / Esc / X all dismiss.
//
// "Top contributing sensors" is a placeholder section — the API contract
// doesn't expose a sensor-attribution endpoint yet. We fake it by showing
// the alert's component sensors marked as anomalies, with the literal
// placeholder copy the brief specified.

export default function AlertDrawer({ alert, acknowledged, onClose, onToggleAck }) {
  useEffect(() => {
    if (!alert) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [alert, onClose]);

  if (!alert) return null;

  const machine = machines.find((m) => m.machine_id === alert.machine_id);
  const tierColor = severityToColor(alert.severity);
  const componentLabel = COMPONENT_LABELS[alert.component_id] || alert.component_id;

  const sensors = (sensorsByMachine[alert.machine_id] || [])
    .filter((s) => s.component_id === alert.component_id)
    .sort((a, b) => (b.anomaly_score || 0) - (a.anomaly_score || 0))
    .slice(0, 3);

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 bg-navy/20 backdrop-blur-[1px] z-30 animate-[fadeIn_120ms_ease-out]"
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label={`Alert ${alert.alert_id}`}
        className="fixed right-0 top-0 bottom-0 w-[460px] max-w-[92vw] bg-white shadow-2xl z-40 flex flex-col animate-[slideIn_180ms_ease-out]"
      >
        <div className="h-1 shrink-0" style={{ backgroundColor: tierColor }} />

        <header className="px-5 py-4 border-b border-slate-100 flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <SeverityPill severity={alert.severity} />
              <span className="font-mono text-[10px] text-slate-400">{alert.alert_id}</span>
              {acknowledged && (
                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[9px] font-semibold uppercase tracking-wider">
                  acknowledged
                </span>
              )}
            </div>
            <h2 className="text-[15px] font-semibold text-navy leading-snug">{alert.title}</h2>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-navy hover:bg-slate-100 shrink-0"
            aria-label="Close drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="px-5 py-4 grid grid-cols-2 gap-4 border-b border-slate-100">
            <Field label="Risk score" mono>
              <span className="text-[20px] font-semibold tabular-nums" style={{ color: tierColor }}>
                {alert.risk_score}
              </span>
              <span className="text-[10px] text-slate-400 ml-1">/ 100</span>
            </Field>
            <Field label="Failure window" mono>
              <span className="text-[15px] font-semibold text-navy">
                {alert.predicted_failure_window_hours == null
                  ? '—'
                  : formatHours(alert.predicted_failure_window_hours)}
              </span>
            </Field>
            <Field label="Machine">
              <Link
                to={`/machines/${alert.machine_id}`}
                className="text-[13px] text-navy font-medium hover:underline inline-flex items-center gap-1"
              >
                {machine?.name || alert.machine_id}
                <ExternalLink className="w-3 h-3 text-slate-400" />
              </Link>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">{alert.machine_id}</div>
            </Field>
            <Field label="Component">
              <span className="text-[13px] text-slate-700">{componentLabel}</span>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">{alert.component_id}</div>
            </Field>
          </div>

          <Section title="Description" icon={AlertOctagon}>
            <p className="text-[13px] text-slate-700 leading-relaxed">{alert.description}</p>
          </Section>

          <Section title="Recommended action" icon={Wrench}>
            <div
              className={`text-[13px] leading-relaxed rounded-md px-3 py-2.5 ${
                alert.severity === 'critical'
                  ? 'bg-red-50 text-red-900 border border-red-100'
                  : alert.severity === 'warning'
                  ? 'bg-orange-50 text-orange-900 border border-orange-100'
                  : 'bg-blue-50/60 text-slate-700 border border-blue-100'
              }`}
            >
              {alert.recommended_action}
            </div>
          </Section>

          <Section title="Cost at risk" icon={DollarSign}>
            {alert.estimated_cost_if_unaddressed_usd > 0 ? (
              <div className="flex items-baseline gap-2">
                <span className="font-mono text-[22px] font-semibold text-navy tabular-nums">
                  {formatCurrencyCompact(alert.estimated_cost_if_unaddressed_usd)}
                </span>
                <span className="text-[11px] text-slate-500">
                  ({formatCurrencyFull(alert.estimated_cost_if_unaddressed_usd)} if unaddressed)
                </span>
              </div>
            ) : (
              <p className="text-[12px] text-slate-500">Informational alert — no quantified cost exposure.</p>
            )}
          </Section>

          <Section title="Top contributing sensors" icon={Activity}>
            {sensors.length === 0 ? (
              <p className="text-[12px] text-slate-500">
                Sensor attribution unavailable for this alert. (Pending sensor-attribution endpoint.)
              </p>
            ) : (
              <ul className="space-y-1.5">
                {sensors.map((s) => (
                  <li
                    key={s.sensor_type}
                    className="flex items-center justify-between gap-3 bg-slate-50 rounded-md px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="text-[12px] text-navy font-medium truncate">{prettySensor(s.sensor_type)}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        normal {s.normal_range[0]}–{s.normal_range[1]} {s.unit}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div
                        className={`font-mono text-[13px] font-semibold tabular-nums ${
                          s.is_anomaly ? 'text-risk-critical' : 'text-navy'
                        }`}
                      >
                        {s.value} <span className="text-slate-400 text-[10px]">{s.unit}</span>
                      </div>
                      {s.is_anomaly && (
                        <div className="text-[9px] uppercase tracking-wider text-risk-critical font-semibold">
                          anomaly · {Math.round(s.anomaly_score * 100)}%
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <Section title="Timeline" icon={Clock}>
            <ul className="text-[12px] text-slate-600 space-y-1.5">
              <li className="flex items-center justify-between">
                <span>Created</span>
                <span className="font-mono text-slate-500">
                  {timeAgo(alert.created_at)}
                  <span className="text-slate-300 ml-2">{alert.created_at.replace('T', ' ').slice(0, 16)} UTC</span>
                </span>
              </li>
            </ul>
          </Section>
        </div>

        <footer className="border-t border-slate-100 px-5 py-3 flex items-center justify-between gap-3 shrink-0 bg-slate-50/50">
          <Link
            to={`/machines/${alert.machine_id}`}
            className="text-[12px] text-slate-600 hover:text-navy inline-flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" /> Open machine detail
          </Link>
          <button
            onClick={onToggleAck}
            className={`px-3.5 py-1.5 rounded-md text-[12px] font-semibold transition-colors ${
              acknowledged
                ? 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                : 'bg-navy text-white hover:bg-navy/90'
            }`}
          >
            {acknowledged ? 'Un-acknowledge' : 'Acknowledge'}
          </button>
        </footer>
      </aside>
    </>
  );
}

function Field({ label, children, mono }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">{label}</div>
      <div className={mono ? 'font-mono' : ''}>{children}</div>
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <section className="px-5 py-4 border-b border-slate-100 last:border-b-0">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5 text-slate-400" strokeWidth={2} />
        <h3 className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function severityToColor(s) {
  if (s === 'critical') return RISK_TIER_COLORS.critical;
  if (s === 'warning')  return RISK_TIER_COLORS.warning;
  return '#3B82F6';
}

function prettySensor(t) {
  return t.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}