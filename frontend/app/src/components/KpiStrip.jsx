import { ArrowUpRight, AlertTriangle, ShieldCheck, DollarSign } from 'lucide-react';
import { formatCurrencyCompact } from '../lib/format.js';

// 4-card KPI strip for the homepage hero.
// Reads from GET /kpis/overview shape (mocked in src/mockData.js for now).
export default function KpiStrip({ kpis }) {
  if (!kpis) return null;

  const cards = [
    {
      kicker: 'Fleet OEE',
      value: kpis.fleet_avg_oee_percent.toFixed(1),
      suffix: '%',
      footnote: `${kpis.machines_running} of ${kpis.machines_total} machines running`,
      icon: ShieldCheck,
      tone: 'neutral',
    },
    {
      kicker: 'Critical alerts',
      value: kpis.active_critical_alerts,
      footnote:
        kpis.active_critical_alerts > 0
          ? 'Action required'
          : `${kpis.active_warning_alerts} warning · monitored`,
      icon: AlertTriangle,
      tone: kpis.active_critical_alerts > 0 ? 'critical' : 'neutral',
    },
    {
      kicker: 'Downtime prevented',
      value: kpis.predicted_downtime_prevented_hours_mtd,
      suffix: 'h',
      footnote: 'Month to date · vs. baseline',
      icon: ArrowUpRight,
      tone: 'positive',
    },
    {
      kicker: 'Cost saved (MTD)',
      value: formatCurrencyCompact(kpis.estimated_cost_saved_usd_mtd),
      footnote: 'Predicted-and-prevented failures',
      icon: DollarSign,
      tone: 'gold',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map((c, i) => (
        <KpiCard key={i} {...c} />
      ))}
    </div>
  );
}

function KpiCard({ kicker, value, suffix, footnote, icon: Icon, tone }) {
  const valueColor =
    tone === 'critical'
      ? 'text-risk-critical'
      : tone === 'gold'
      ? 'text-gold-deep'
      : 'text-navy';

  const iconWrap =
    tone === 'critical'
      ? 'bg-red-50 text-risk-critical'
      : tone === 'positive'
      ? 'bg-emerald-50 text-emerald-600'
      : tone === 'gold'
      ? 'bg-gold/10 text-gold-deep'
      : 'bg-slate-100 text-slate-500';

  return (
    <div className="bg-white rounded-xl shadow-card p-5 flex flex-col gap-3 relative overflow-hidden">
      {tone === 'gold' && (
        <span className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-gold to-transparent" />
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500 font-semibold">
          {kicker}
        </div>
        <div className={`w-7 h-7 rounded-md flex items-center justify-center ${iconWrap}`}>
          <Icon className="w-3.5 h-3.5" strokeWidth={2.25} />
        </div>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`font-mono text-[32px] font-semibold leading-none tracking-tight ${valueColor}`}>
          {value}
        </span>
        {suffix && (
          <span className="font-mono text-[16px] text-slate-400 font-medium">{suffix}</span>
        )}
      </div>
      <div className="text-xs text-slate-500">{footnote}</div>
    </div>
  );
}
