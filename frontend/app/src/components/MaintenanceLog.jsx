import { COMPONENT_LABELS } from '../mockData.js';
import { MAINT_KIND_CLASSES } from '../brand/tokens.js';
import { formatCurrencyCompact } from '../lib/format.js';

export default function MaintenanceLog({ entries }) {
  const items = entries.slice(0, 8);
  return (
    <section className="bg-white rounded-xl shadow-card overflow-hidden">
      <header className="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-navy">Maintenance log</div>
          <div className="text-[11px] text-slate-500">Last {items.length} entries · 6-month window</div>
        </div>
        <div className="text-[11px] text-slate-400 font-mono">
          {formatCurrencyCompact(items.reduce((s, e) => s + (e.cost_usd || 0), 0))} total
        </div>
      </header>
      <ul className="divide-y divide-slate-100 max-h-[420px] overflow-y-auto">
        {items.map((e) => {
          const inProgress = (e.cost_usd || 0) === 0 && (e.summary || '').startsWith('IN PROGRESS');
          return (
            <li key={e.entry_id} className="px-4 py-3 hover:bg-slate-50">
              <div className="flex items-center justify-between gap-2 mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide ${MAINT_KIND_CLASSES[e.kind]}`}>{e.kind}</span>
                  <span className="text-[11px] text-slate-500 font-mono truncate">{COMPONENT_LABELS[e.component_id] || e.component_id}</span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono shrink-0">{e.date}</span>
              </div>
              <div className="text-[12.5px] text-navy leading-snug">{e.summary}</div>
              <div className="flex items-center justify-between mt-1">
                <div className="text-[10px] text-slate-400 truncate">{e.technician}</div>
                <div className="font-mono text-[11px] font-medium text-navy">
                  {inProgress ? <span className="text-amber-600">in progress</span> : formatCurrencyCompact(e.cost_usd)}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
