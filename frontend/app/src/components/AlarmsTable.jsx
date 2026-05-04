import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { SeverityPill } from './Pills.jsx';
import { COMPONENT_LABELS } from '../mockData.js';
import { timeAgo } from '../lib/format.js';

export default function AlarmsTable({ alarms }) {
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState(null);

  const visible = filter === 'active' ? alarms.filter((a) => !a.resolved) : alarms;
  const counts = { all: alarms.length, active: alarms.filter((a) => !a.resolved).length };

  function toggle(id) {
    setExpandedId((curr) => (curr === id ? null : id));
  }

  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden flex flex-col">
      <header className="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-navy">Recent alarms</div>
          <div className="text-[11px] text-slate-500">Last {alarms.length} events from DCS</div>
        </div>
        <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
          {['active', 'all'].map((k) => (
            <button
              key={k}
              onClick={() => setFilter(k)}
              className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                filter === k ? 'bg-white text-navy shadow-sm' : 'text-slate-500 hover:text-navy'
              }`}
            >
              {k === 'active' ? 'Active' : 'All'}{' '}
              <span className="font-mono text-slate-400">{counts[k]}</span>
            </button>
          ))}
        </div>
      </header>
      <div className="overflow-y-auto max-h-[380px]">
        <ul className="divide-y divide-slate-100">
          {visible.map((a) => {
            const isOpen = expandedId === a.alarm_id;
            return (
              <li key={a.alarm_id} className="border-l-2 border-transparent transition-colors">
                <button
                  onClick={() => toggle(a.alarm_id)}
                  className={`w-full text-left px-4 py-2.5 grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 items-center transition-colors ${
                    isOpen ? 'bg-slate-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <SeverityPill severity={a.severity} />
                  <div className="min-w-0">
                    <div className="text-[13px] text-navy truncate">{a.message}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                      <span className="font-mono uppercase tracking-wide">
                        {COMPONENT_LABELS[a.component_id] || a.component_id || '—'}
                      </span>
                      <span>·</span>
                      <span>{timeAgo(a.raised_at)}</span>
                      {a.resolved && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[9px] font-semibold uppercase tracking-wider ml-1">
                          resolved
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronDown
                    className={`w-3.5 h-3.5 text-slate-400 transition-transform shrink-0 ${
                      isOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {isOpen && <AlarmDetail alarm={a} />}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function AlarmDetail({ alarm }) {
  const downtimeMin = alarm.downtime_minutes ?? 0;
  const downtimeLabel =
    downtimeMin === 0
      ? 'No downtime recorded'
      : downtimeMin >= 60
      ? `${(downtimeMin / 60).toFixed(1)} h`
      : `${downtimeMin} min`;

  return (
    <div className="px-5 py-4 bg-slate-50/70 border-t border-slate-100">
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold mb-2">
        Description
      </div>
      <p className="text-[13px] text-navy leading-relaxed mb-4">{alarm.message}</p>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        <DetailKV label="Severity" value={alarm.severity} mono uppercase />
        <DetailKV
          label="Status"
          value={alarm.resolved ? 'Resolved' : 'Active'}
          tone={alarm.resolved ? 'emerald' : 'red'}
        />
        <DetailKV label="Raised at" value={formatTimestamp(alarm.raised_at)} mono />
        <DetailKV
          label="Resolved at"
          value={alarm.resolved_at ? formatTimestamp(alarm.resolved_at) : '—'}
          mono
        />
        <DetailKV label="Component" value={COMPONENT_LABELS[alarm.component_id] || alarm.component_id || '—'} />
        <DetailKV label="Downtime" value={downtimeLabel} mono />
        <DetailKV label="Alarm ID" value={alarm.alarm_id} mono small className="col-span-2" />
      </div>
    </div>
  );
}

function DetailKV({ label, value, mono, uppercase, tone, small, className = '' }) {
  const valueClasses = [
    'text-navy',
    mono ? 'font-mono tabular-nums' : '',
    uppercase ? 'uppercase tracking-wider' : '',
    small ? 'text-[11px]' : 'text-[12.5px]',
    tone === 'emerald' ? 'text-emerald-700' : '',
    tone === 'red' ? 'text-red-700' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className}>
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold mb-1">
        {label}
      </div>
      <div className={valueClasses}>{value}</div>
    </div>
  );
}

function formatTimestamp(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }) + ' UTC';
}