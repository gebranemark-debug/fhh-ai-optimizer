import { Search, X } from 'lucide-react';
import { machines } from '../../mockData.js';

// Filter bar for the Alerts page. Owns no state — every value is a controlled
// prop driven by the page. Mirrors the GET /alerts query params 1:1:
//   severity, machine_id, acknowledged (tri-state), sort, plus a free-text
//   search that filters client-side on title / description.

const SEVERITY_OPTIONS = [
  { value: 'all',      label: 'All severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning',  label: 'Warning' },
  { value: 'info',     label: 'Info' },
];

const ACK_OPTIONS = [
  { value: 'all',            label: 'All' },
  { value: 'unacknowledged', label: 'Unacknowledged' },
  { value: 'acknowledged',   label: 'Acknowledged' },
];

const SORT_OPTIONS = [
  { value: 'severity',   label: 'Severity (high → low)' },
  { value: 'risk_score', label: 'Risk score (high → low)' },
  { value: 'created_at', label: 'Most recent' },
];

export default function AlertsFilterBar({ filters, onChange, totalShown, totalAll }) {
  const hasActiveFilters =
    filters.severity !== 'all' ||
    filters.machine_id !== 'all' ||
    filters.acknowledged !== 'all' ||
    filters.search.trim() !== '';

  const set = (patch) => onChange({ ...filters, ...patch });

  return (
    <div className="bg-white rounded-xl shadow-card overflow-hidden">
      <div className="px-4 py-3 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-[320px]">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" strokeWidth={2} />
          <input
            type="text"
            placeholder="Search alerts…"
            value={filters.search}
            onChange={(e) => set({ search: e.target.value })}
            className="w-full pl-8 pr-3 py-1.5 text-[13px] bg-slate-50 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 placeholder:text-slate-400"
          />
        </div>

        <Select
          label="Severity"
          value={filters.severity}
          options={SEVERITY_OPTIONS}
          onChange={(v) => set({ severity: v })}
        />

        <Select
          label="Machine"
          value={filters.machine_id}
          options={[
            { value: 'all', label: 'All machines' },
            ...machines.map((m) => ({ value: m.machine_id, label: m.name })),
          ]}
          onChange={(v) => set({ machine_id: v })}
        />

        <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
          {ACK_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => set({ acknowledged: opt.value })}
              className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                filters.acknowledged === opt.value
                  ? 'bg-white text-navy shadow-sm'
                  : 'text-slate-500 hover:text-navy'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <Select
          label="Sort"
          value={filters.sort}
          options={SORT_OPTIONS}
          onChange={(v) => set({ sort: v })}
        />

        <div className="ml-auto flex items-center gap-3">
          <div className="text-[11px] text-slate-500 font-mono whitespace-nowrap">
            {totalShown === totalAll ? (
              <>{totalAll} alert{totalAll === 1 ? '' : 's'}</>
            ) : (
              <>
                <span className="text-navy font-semibold">{totalShown}</span>
                <span className="text-slate-400"> of {totalAll}</span>
              </>
            )}
          </div>
          {hasActiveFilters && (
            <button
              onClick={() =>
                onChange({ severity: 'all', machine_id: 'all', acknowledged: 'all', sort: filters.sort, search: '' })
              }
              className="text-[11px] text-slate-500 hover:text-navy flex items-center gap-1"
            >
              <X className="w-3 h-3" /> Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Select({ label, value, options, onChange }) {
  return (
    <label className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="text-[12px] bg-slate-50 border border-slate-200 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 text-navy"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
