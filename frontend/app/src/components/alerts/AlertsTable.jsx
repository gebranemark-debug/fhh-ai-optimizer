import { ChevronRight } from 'lucide-react';
import { SeverityPill } from '../Pills.jsx';
import { COMPONENT_LABELS, machines } from '../../mockData.js';
import { formatCurrencyCompact, formatHours, timeAgo } from '../../lib/format.js';
import { RISK_TIER_COLORS } from '../../brand/tokens.js';

// Full alerts table — fleet-wide. Eight columns per the spec, dense but not
// cramped (44px row height target). Row click opens the drawer; the entire
// row is the click target.
//
// Sort key is applied here (already passed in from the page); we don't sort
// internally. We *do* render the empty state when the filtered list is empty.

export default function AlertsTable({ alerts, selectedId, onSelect, ackOverrides }) {
  if (alerts.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-card p-10 text-center">
        <div className="text-sm font-semibold text-navy mb-1">No alerts match these filters</div>
        <p className="text-[12px] text-slate-500">Try clearing a filter or widening the severity selection.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold border-b border-slate-100">
              <Th className="w-[1%] pl-4">Sev</Th>
              <Th>Title</Th>
              <Th className="w-[140px]">Machine</Th>
              <Th className="w-[120px]">Component</Th>
              <Th className="w-[80px] text-right">Risk</Th>
              <Th className="w-[120px]">Window</Th>
              <Th className="w-[110px] text-right">Cost at risk</Th>
              <Th className="w-[110px]">Created</Th>
              <Th className="w-[1%] pr-4">Status</Th>
              <Th className="w-[1%] pr-4" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {alerts.map((alert) => (
              <Row
                key={alert.alert_id}
                alert={alert}
                selected={alert.alert_id === selectedId}
                acknowledged={isAcknowledged(alert, ackOverrides)}
                onClick={() => onSelect(alert.alert_id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Row({ alert, selected, acknowledged, onClick }) {
  const machine = machines.find((m) => m.machine_id === alert.machine_id);
  const machineName = machine?.name || alert.machine_id;
  const tierColor = severityToColor(alert.severity);

  return (
    <tr
      onClick={onClick}
      className={`cursor-pointer transition-colors ${
        selected ? 'bg-navy/[0.04]' : acknowledged ? 'opacity-60 hover:bg-slate-50' : 'hover:bg-slate-50'
      }`}
    >
      <Td className="pl-4 py-2.5">
        <span
          aria-hidden
          className="inline-block w-1 h-7 rounded-full align-middle"
          style={{ backgroundColor: tierColor }}
        />
      </Td>
      <Td>
        <div className="flex items-center gap-2 min-w-0">
          <SeverityPill severity={alert.severity} />
          <span className="text-[13px] text-navy font-medium truncate" title={alert.title}>
            {alert.title}
          </span>
        </div>
      </Td>
      <Td>
        <div className="text-[12px] text-navy truncate">{machineName}</div>
        <div className="text-[10px] text-slate-400 font-mono truncate">{alert.machine_id}</div>
      </Td>
      <Td>
        <span className="text-[12px] text-slate-600">{COMPONENT_LABELS[alert.component_id] || alert.component_id}</span>
      </Td>
      <Td className="text-right">
        <span className="font-mono text-[13px] font-semibold tabular-nums" style={{ color: tierColor }}>
          {alert.risk_score}
        </span>
      </Td>
      <Td>
        <span className="font-mono text-[11px] text-slate-600">
          {alert.predicted_failure_window_hours == null ? '—' : formatHours(alert.predicted_failure_window_hours)}
        </span>
      </Td>
      <Td className="text-right">
        <span className="font-mono text-[12px] text-navy tabular-nums">
          {alert.estimated_cost_if_unaddressed_usd > 0
            ? formatCurrencyCompact(alert.estimated_cost_if_unaddressed_usd)
            : '—'}
        </span>
      </Td>
      <Td>
        <span className="text-[11px] text-slate-500">{timeAgo(alert.created_at)}</span>
      </Td>
      <Td className="pr-4">
        {acknowledged ? (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-[9px] font-semibold uppercase tracking-wider">
            ack
          </span>
        ) : (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 text-[9px] font-semibold uppercase tracking-wider ring-1 ring-amber-200">
            new
          </span>
        )}
      </Td>
      <Td className="pr-4 text-slate-300">
        <ChevronRight className="w-4 h-4" strokeWidth={2} />
      </Td>
    </tr>
  );
}

function Th({ children, className = '' }) {
  return <th className={`py-2 px-2 font-semibold ${className}`}>{children}</th>;
}

function Td({ children, className = '' }) {
  return <td className={`py-2.5 px-2 align-middle ${className}`}>{children}</td>;
}

function severityToColor(s) {
  if (s === 'critical') return RISK_TIER_COLORS.critical;
  if (s === 'warning')  return RISK_TIER_COLORS.warning;
  return '#3B82F6';
}

function isAcknowledged(alert, overrides) {
  if (overrides && Object.prototype.hasOwnProperty.call(overrides, alert.alert_id)) {
    return overrides[alert.alert_id];
  }
  return !!alert.acknowledged;
}