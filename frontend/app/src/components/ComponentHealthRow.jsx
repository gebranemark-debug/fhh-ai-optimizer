import { ChevronRight } from 'lucide-react';
import { COMPONENT_LABELS, COMPONENT_ORDER } from '../mockData.js';
import { RISK_TIER_COLORS, TIER_SOFT_BG } from '../brand/tokens.js';
import { TierPill } from './Pills.jsx';

export default function ComponentHealthRow({ components, predictions, isMaintenance }) {
  const byId = Object.fromEntries(components.map((c) => [c.component_id, c]));
  const predById = Object.fromEntries(predictions.map((p) => [p.component_id, p]));

  return (
    <section>
      <SectionHeader title="Component health" subtitle="Production order · failure probability is the hero metric" />
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 relative">
        {COMPONENT_ORDER.map((id, idx) => {
          const c = byId[id];
          const p = predById[id];
          if (!c) return null;
          return (
            <div key={id} className="relative">
              <ComponentCard component={c} prediction={p} isMaintenance={isMaintenance} />
              {idx < COMPONENT_ORDER.length - 1 && (
                <ChevronRight className="hidden xl:block absolute -right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" strokeWidth={1.5} />
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ComponentCard({ component, prediction, isMaintenance }) {
  const tierColor = RISK_TIER_COLORS[component.tier];
  const probPct = prediction?.failure_probability != null ? (prediction.failure_probability * 100) : null;
  const display = probPct == null ? '—' : probPct >= 99 ? probPct.toFixed(2) : probPct >= 10 ? probPct.toFixed(1) : probPct.toFixed(2);
  const action = prediction?.recommended_action || '';
  const truncated = action.length > 80 ? action.slice(0, 78) + '…' : action;

  return (
    <div className="bg-white rounded-xl shadow-card overflow-hidden flex flex-col" style={{ borderTop: `2px solid ${tierColor}` }}>
      <div className="px-3.5 pt-3 pb-2.5 flex flex-col gap-2 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs font-semibold text-navy truncate">{COMPONENT_LABELS[component.component_id]}</div>
          <TierPill tier={component.tier} size="sm" />
        </div>
        <div className="flex items-baseline gap-1" style={{ backgroundColor: TIER_SOFT_BG[component.tier], padding: '6px 8px', borderRadius: 6, marginInline: -2 }}>
          <span className="font-mono text-[26px] font-semibold leading-none tracking-tight tabular-nums" style={{ color: tierColor }}>
            {display}
          </span>
          {probPct != null && <span className="font-mono text-xs text-slate-400 ml-0.5">%</span>}
          <span className="ml-auto text-[9px] uppercase tracking-wider text-slate-400 font-semibold whitespace-nowrap">failure prob.</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[10px]">
          <Cell label="Health" value={isMaintenance ? '—' : `${component.health_score}`} />
          <Cell label="Confidence" value={prediction?.confidence != null ? `${Math.round(prediction.confidence * 100)}%` : '—'} />
        </div>
        <div className="text-[10.5px] text-slate-500 leading-snug pt-1.5 mt-auto border-t border-slate-100" title={action}>
          {truncated || (isMaintenance ? 'Awaiting next prediction run.' : '—')}
        </div>
      </div>
    </div>
  );
}

function Cell({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="uppercase tracking-wider text-slate-400 font-semibold">{label}</span>
      <span className="font-mono text-xs text-navy font-medium tabular-nums">{value}</span>
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="flex items-baseline justify-between mb-3">
      <h2 className="text-sm font-semibold text-navy">{title}</h2>
      {subtitle && <div className="text-[11px] text-slate-400">{subtitle}</div>}
    </div>
  );
}