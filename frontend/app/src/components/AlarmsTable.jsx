import { useState } from 'react';
import { SeverityPill } from './Pills.jsx';
import { COMPONENT_LABELS } from '../mockData.js';
import { timeAgo } from '../lib/format.js';

export default function AlarmsTable({ alarms }) {
  const [filter, setFilter] = useState('all');
  const visible = filter === 'active' ? alarms.filter((a) => !a.resolved) : alarms;
  const counts = { all: alarms.length, active: alarms.filter((a) => !a.resolved).length };
  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden flex flex-col">
      <header className="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-navy">Recent alarms</div>
          <div className="text-[11px] text-slate-500">Last {alarms.length} events from DCS</div>
        </div>
        <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
          {['active', 'all'].map((k) => (
            <button key={k} onClick={() => setFilter(k)} className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${filter === k ? 'bg-white text-navy shadow-sm' : 'text-slate-500 hover:text-navy'}`}>
              {k === 'active' ? 'Active' : 'All'} <span className="font-mono text-slate-400">{counts[k]}</span>
            </button>
          ))}
        </div>
      </header>
      <div className="overflow-y-auto max-h-[380px]">
        <ul className="divide-y divide-slate-100">
          {visible.map((a) => (
            <li key={a.alarm_id} className="px-4 py-2.5 hover:bg-slate-50 grid grid-cols-[auto_minmax(0,1fr)_auto] gap-3 items-center">
              <SeverityPill severity={a.severity} />
              <div className="min-w-0">
                <div className="text-[13px] text-navy truncate">{a.message}</div>
                <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                  <span className="font-mono uppercase tracking-wide">{COMPONENT_LABELS[a.component_id] || a.component_id}</span>
                  <span>·</span>
                  <span>{timeAgo(a.raised_at)}</span>
                  {a.resolved && <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[9px] font-semibold uppercase tracking-wider ml-1">resolved</span>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}