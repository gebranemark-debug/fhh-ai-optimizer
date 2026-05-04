import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { COMPONENT_LABELS } from '../mockData.js';
import { MAINT_KIND_CLASSES } from '../brand/tokens.js';
import { formatCurrencyCompact } from '../lib/format.js';

export default function MaintenanceLog({ entries }) {
  const items = entries.slice(0, 8);
  const [expandedId, setExpandedId] = useState(null);

  function toggle(id) {
    setExpandedId((curr) => (curr === id ? null : id));
  }

  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden">
      <header className="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-navy">Maintenance log</div>
          <div className="text-[11px] text-slate-500">
            Last {items.length} entries · 6-month window
          </div>
        </div>
        <div className="text-[11px] text-slate-400 font-mono">
          {formatCurrencyCompact(items.reduce((s, e) => s + (e.cost_usd || 0), 0))} total
        </div>
      </header>
      <ul className="divide-y divide-slate-100 max-h-[420px] overflow-y-auto">
        {items.map((e) => {
          const inProgress = (e.cost_usd || 0) === 0 && (e.summary || '').startsWith('IN PROGRESS');
          const isOpen = expandedId === e.entry_id;
          return (
            <li key={e.entry_id}>
              <button
                onClick={() => toggle(e.entry_id)}
                className={`w-full text-left px-4 py-3 transition-colors ${
                  isOpen ? 'bg-slate-50' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide ${MAINT_KIND_CLASSES[e.kind]}`}
                    >
                      {e.kind}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono truncate">
                      {COMPONENT_LABELS[e.component_id] || e.component_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] text-slate-400 font-mono">{e.date}</span>
                    <ChevronDown
                      className={`w-3.5 h-3.5 text-slate-400 transition-transform ${
                        isOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </div>
                </div>
                <div className="text-[12.5px] text-navy leading-snug truncate">{e.summary}</div>
                <div className="flex items-center justify-between mt-1">
                  <div className="text-[10px] text-slate-400 truncate">{e.technician}</div>
                  <div className="font-mono text-[11px] font-medium text-navy">
                    {inProgress ? (
                      <span className="text-amber-600">in progress</span>
                    ) : (
                      formatCurrencyCompact(e.cost_usd)
                    )}
                  </div>
                </div>
              </button>

              {isOpen && <MaintenanceDetail entry={e} inProgress={inProgress} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function MaintenanceDetail({ entry, inProgress }) {
  return (
    <div className="px-5 py-4 bg-slate-50/70 border-t border-slate-100">
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold mb-2">
        Notes
      </div>
      <p className="text-[13px] text-navy leading-relaxed mb-4">
        {entry.summary || '(No notes recorded.)'}
      </p>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3">
        <DetailKV label="Type" value={entry.kind} uppercase mono />
        <DetailKV
          label="Component"
          value={COMPONENT_LABELS[entry.component_id] || entry.component_id || '—'}
        />
        <DetailKV label="Date performed" value={entry.date || '—'} mono />
        <DetailKV
          label="Downtime"
          value={
            entry.downtime_hours != null
              ? `${entry.downtime_hours} h`
              : '—'
          }
          mono
        />
        <DetailKV label="Technician" value={entry.technician || '—'} />
        <DetailKV
          label="Cost"
          value={
            inProgress
              ? 'In progress'
              : entry.cost_usd != null
              ? formatCurrencyCompact(entry.cost_usd)
              : '—'
          }
          mono
          tone={inProgress ? 'amber' : null}
        />
        <DetailKV label="Entry ID" value={entry.entry_id} mono small className="col-span-2" />
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
    tone === 'amber' ? 'text-amber-700' : '',
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