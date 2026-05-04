import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LabelList,
} from 'recharts';
import {
  DollarSign,
  Clock,
  CheckCircle2,
  TrendingUp,
  Activity,
  AlertOctagon,
  AlertTriangle,
  Cpu,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { COLORS, RISK_TIER_COLORS } from '../brand/tokens.js';
import { getCostSavings, getKpisOverview } from '../lib/api.js';

// ─────────────────────────────────────────────────────────────────────────────
// ROI / Cost Savings page
//
// Hero-typography page. Three takeaways in 10 seconds:
//   1. How much money the system has saved
//   2. Whether anyone is acting on the predictions
//   3. Where the value is concentrated (per-machine)
//
// All fetches are mocked. Each is wrapped in a TODO(wiring) marker so Task 5
// can swap in the real lib/api.js calls without touching layout.


// ─── Static reference data ───────────────────────────────────────────────────
const MACHINE_INFO = {
  'al-nakheel': { name: 'Al Nakheel', location: 'Abu Dhabi, UAE',           tier: 'critical' },
  'al-bardi':   { name: 'Al Bardi',   location: 'Tenth of Ramadan, Egypt',  tier: 'warning'  },
  'al-sindian': { name: 'Al Sindian', location: 'Sadat City, Egypt',        tier: 'watch'    },
  'al-snobar':  { name: 'Al Snobar',  location: 'Amman, Jordan',            tier: 'healthy'  },
};

const WINDOW_OPTIONS = [
  { id: 'mtd', label: 'MTD', longLabel: 'Month-to-date' },
  { id: 'qtd', label: 'QTD', longLabel: 'Quarter-to-date' },
  { id: 'ytd', label: 'YTD', longLabel: 'Year-to-date' },
  { id: 'all', label: 'ALL', longLabel: 'All time' },
];

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// ─── Format helpers ──────────────────────────────────────────────────────────
const fmtCompactUsd = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000)     return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n)}`;
};

const fmtFullUsd = (n) => {
  if (n == null) return '—';
  return `$${Math.round(n).toLocaleString('en-US')}`;
};

const fmtPct = (num, denom, digits = 0) => {
  if (!denom) return '0%';
  return `${((num / denom) * 100).toFixed(digits)}%`;
};

const fmtUpdated = (iso) => {
  const d = new Date(iso);
  return `Updated ${String(d.getUTCDate()).padStart(2, '0')} ${MONTH_NAMES[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')} UTC`;
};

// ─── Page ────────────────────────────────────────────────────────────────────
export default function ROI() {
  const [window, setWindow] = useState('ytd');

  const [costSavings, setCostSavings] = useState({ status: 'loading', data: null, error: null });
  const [allTime, setAllTime]         = useState({ status: 'loading', data: null, error: null });
  const [overview, setOverview]       = useState({ status: 'loading', data: null, error: null });

  // Re-fetch the active window on change.
// Re-fetch the active window on change.
  useEffect(() => {
    let cancelled = false;
    setCostSavings({ status: 'loading', data: null, error: null });

    getCostSavings(window)
      .then((data) => { if (!cancelled) setCostSavings({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setCostSavings({ status: 'error', data: null, error }); });

    return () => { cancelled = true; };
  }, [window]);

  // All-time fetch is independent of the selected window — it powers the
  // "Total predictions to-date" tile in the Fleet strip.
  useEffect(() => {
    let cancelled = false;

    getCostSavings('all')
      .then((data) => { if (!cancelled) setAllTime({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setAllTime({ status: 'error', data: null, error }); });

    return () => { cancelled = true; };
  }, []);

  // Overview is "now" — fetched once.
  useEffect(() => {
    let cancelled = false;

    getKpisOverview()
      .then((data) => { if (!cancelled) setOverview({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setOverview({ status: 'error', data: null, error }); });

    return () => { cancelled = true; };
  }, []);

  return (
    <div className="px-8 py-7 max-w-[1400px] flex flex-col gap-6">
      <Header window={window} setWindow={setWindow} overview={overview} />

      <HeroStrip costSavings={costSavings} />

      <BreakdownSection costSavings={costSavings} window={window} />

      <FleetStrip overview={overview} allTime={allTime} />
    </div>
  );
}

// ─── Header ──────────────────────────────────────────────────────────────────
function Header({ window, setWindow, overview }) {
  return (
    <div>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
            Module 1 · Predictive maintenance
          </div>
          <h1 className="text-[24px] font-semibold text-navy tracking-tight mt-0.5">Cost Savings</h1>
          <p className="text-[13px] text-slate-500 mt-1 max-w-2xl">
            Predictive maintenance ROI · what we&rsquo;ve prevented.
          </p>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          <WindowSelector value={window} onChange={setWindow} />
          {overview.status === 'ok' && (
            <div className="text-[11px] text-slate-400 font-mono whitespace-nowrap">
              {fmtUpdated(overview.data.last_updated)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function WindowSelector({ value, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Window</span>
      <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
        {WINDOW_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            onClick={() => onChange(opt.id)}
            title={opt.longLabel}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold tracking-wider transition-colors ${
              value === opt.id
                ? 'bg-white text-navy shadow-sm'
                : 'text-slate-500 hover:text-navy'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Hero strip (4 tiles, "Total cost saved" is the visual lead) ─────────────
function HeroStrip({ costSavings }) {
  if (costSavings.status === 'loading') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-9 gap-4">
        <div className="md:col-span-3 h-[176px] rounded-xl bg-amber-50/40 ring-1 ring-amber-200 animate-pulse" />
        {[0,1,2].map((i) => (
          <div key={i} className="md:col-span-2 h-[176px] rounded-xl bg-white shadow-card animate-pulse" />
        ))}
      </div>
    );
  }
  if (costSavings.status === 'error' || !costSavings.data) {
    return <ErrorPanel title="Couldn't load cost savings" onRetry={() => window.location.reload()} />;
  }

  const d = costSavings.data;
  const adoption = d.total_predictions ? d.predictions_acted_on / d.total_predictions : 0;
  const avgPerSave = d.predictions_acted_on ? d.estimated_cost_saved_usd / d.predictions_acted_on : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-9 gap-4">
      <HeroTile
        kind="primary"
        className="md:col-span-3"
        icon={DollarSign}
        label="Total cost saved"
        value={fmtCompactUsd(d.estimated_cost_saved_usd)}
        unit=""
        subtitle="Avoided in selected window."
        footnote={fmtFullUsd(d.estimated_cost_saved_usd)}
      />
      <HeroTile
        className="md:col-span-2"
        icon={Clock}
        label="Downtime prevented"
        value={String(d.estimated_downtime_hours_prevented)}
        unit="hours"
        subtitle="Across the fleet."
      />
      <HeroTile
        className="md:col-span-2"
        icon={CheckCircle2}
        label="Predictions acted on"
        value={
          <span>
            <span className="text-navy">{d.predictions_acted_on}</span>
            <span className="text-slate-400 font-normal text-[24px] mx-1.5">of</span>
            <span className="text-navy">{d.total_predictions}</span>
          </span>
        }
        unit=""
        subtitle={`${fmtPct(d.predictions_acted_on, d.total_predictions)} adoption rate.`}
      />
      <HeroTile
        className="md:col-span-2"
        icon={TrendingUp}
        label="Avg savings per save"
        value={fmtCompactUsd(avgPerSave)}
        unit=""
        subtitle="Per acted-upon prediction."
      />
    </div>
  );
}

function HeroTile({ kind = 'default', icon: Icon, label, value, unit, subtitle, footnote, className = '' }) {
  const isPrimary = kind === 'primary';

  return (
    <div
      className={`relative rounded-xl p-5 flex flex-col justify-between min-h-[176px] ${className} ${
        isPrimary
          ? 'shadow-card overflow-hidden'
          : 'bg-white shadow-card'
      }`}
      style={
        isPrimary
          ? { background: `linear-gradient(155deg, #FFFDF5 0%, #FFFFFF 60%)` }
          : undefined
      }
    >
      {isPrimary && (
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-1.5 rounded-l-xl"
          style={{ backgroundColor: COLORS.gold }}
        />
      )}

      <div className={`flex items-center gap-2 ${isPrimary ? 'pl-1' : ''}`}>
        {Icon && (
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
            style={{
              backgroundColor: isPrimary ? `${COLORS.gold}1f` : '#F1F5F9',
              color: isPrimary ? COLORS.gold : COLORS.navy,
            }}
          >
            <Icon className="w-3.5 h-3.5" strokeWidth={2.25} />
          </div>
        )}
        <div className="text-[10.5px] uppercase tracking-[0.14em] text-slate-500 font-semibold">
          {label}
        </div>
      </div>

      <div className={`flex items-baseline gap-2 leading-none ${isPrimary ? 'pl-1' : ''}`}>
        <span
          className="font-mono font-semibold tabular-nums tracking-tight whitespace-nowrap"
          style={{
            fontSize: isPrimary ? 44 : 30,
            color: isPrimary ? COLORS.gold : COLORS.navy,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit && (
          <span className="text-[14px] text-slate-400 font-normal">{unit}</span>
        )}
      </div>

      <div className={`flex items-end justify-between gap-3 ${isPrimary ? 'pl-1' : ''}`}>
        <p className="text-[11.5px] text-slate-500 leading-snug">{subtitle}</p>
        {footnote && (
          <span className="font-mono text-[10.5px] text-slate-400 tabular-nums whitespace-nowrap">
            {footnote}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Per-machine breakdown ───────────────────────────────────────────────────
function BreakdownSection({ costSavings, window }) {
  return (
    <section className="grid grid-cols-1 lg:grid-cols-5 gap-5">
      <div className="lg:col-span-3 bg-white rounded-xl shadow-card p-5">
        <SectionHead
          title="Savings by machine"
          subtitle="Where the prevented losses come from"
          icon={Cpu}
        />
        {costSavings.status !== 'ok' || !costSavings.data ? (
          <div className="h-[320px] rounded-lg bg-slate-100 animate-pulse" />
        ) : (
          <MachineBreakdownChart costSavings={costSavings.data} />
        )}
      </div>
      <div className="lg:col-span-2">
        <InsightCallout costSavings={costSavings} window={window} />
      </div>
    </section>
  );
}

function MachineBreakdownChart({ costSavings }) {
  const total = costSavings.estimated_cost_saved_usd;

  const rows = useMemo(() => {
    return [...costSavings.breakdown_by_machine]
      .sort((a, b) => b.cost_saved_usd - a.cost_saved_usd)
      .map((row) => {
        const info = MACHINE_INFO[row.machine_id] || { name: row.machine_id, location: '', tier: 'healthy' };
        return {
          machine_id: row.machine_id,
          name: info.name,
          location: info.location,
          tier: info.tier,
          tierColor: RISK_TIER_COLORS[info.tier],
          cost_saved_usd: row.cost_saved_usd,
          pct: total ? row.cost_saved_usd / total : 0,
        };
      });
  }, [costSavings, total]);

  return (
    <div>
      <div className="flex flex-col gap-3">
        {rows.map((row) => (
          <MachineBar key={row.machine_id} row={row} max={rows[0].cost_saved_usd} />
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between flex-wrap gap-2 text-[11px] text-slate-500 border-t border-slate-100 pt-3">
        <div className="flex items-center gap-3 flex-wrap">
          <LegendDot color={COLORS.gold} label="Cost saved" shape="bar" />
          <span className="text-slate-300">·</span>
          <span>Left rail = current risk tier</span>
          <span className="inline-flex items-center gap-1.5">
            <TierDot tier="critical" /> Critical
            <TierDot tier="warning" /> Warning
            <TierDot tier="watch" /> Watch
            <TierDot tier="healthy" /> Healthy
          </span>
        </div>
        <span className="font-mono tabular-nums">
          Total <span className="text-navy font-semibold">{fmtFullUsd(total)}</span>
        </span>
      </div>
    </div>
  );
}

function MachineBar({ row, max }) {
  const widthPct = max ? (row.cost_saved_usd / max) * 100 : 0;
  // Keep the percentage label inside the bar only when there's room for it,
  // otherwise it renders to the right. Threshold tuned for the 4-machine layout.
  // Inline label only fits when the bar is wide enough to hold the value.
  // Tuned for the 4-machine layout — Al Nakheel typically clears, the others render the value to the right.
  const labelInside = widthPct >= 60;

  return (
    <div className="flex items-stretch gap-3 group">
      <div className="w-[180px] shrink-0 flex flex-col justify-center">
        <div className="text-[12.5px] text-navy font-medium leading-tight">{row.name}</div>
        <div className="text-[10.5px] text-slate-400 leading-tight truncate">{row.location}</div>
      </div>

      <div className="flex-1 flex items-center min-w-0">
        <div className="w-full h-9 relative rounded-md bg-slate-50 ring-1 ring-slate-100">
          {/* Tier accent rail */}
          <span
            aria-hidden
            className="absolute left-0 top-0 bottom-0 w-1"
            style={{ backgroundColor: row.tierColor }}
          />
          {/* Bar fill */}
          <div
            className="absolute left-1 top-0 bottom-0 rounded-r-md transition-all duration-500 ease-out"
            style={{
              width: `calc(${widthPct}% - 4px)`,
              backgroundColor: COLORS.gold,
              minWidth: 4,
            }}
          />
          {/* Inline value (inside) */}
          {labelInside && (
            <div
              className="absolute top-0 bottom-0 flex items-center pr-2.5 text-white font-mono text-[12px] font-semibold tabular-nums pointer-events-none"
              style={{ left: 0, width: `calc(${widthPct}% - 4px)`, justifyContent: 'flex-end' }}
            >
              {fmtCompactUsd(row.cost_saved_usd)}
            </div>
          )}
        </div>

        {/* Trailing stats */}
        <div className="ml-3 w-[140px] shrink-0 flex items-baseline justify-end gap-2 font-mono tabular-nums">
          {!labelInside && (
            <span className="text-[12.5px] text-navy font-semibold">
              {fmtCompactUsd(row.cost_saved_usd)}
            </span>
          )}
          <span className="text-[11px] text-slate-500">
            {(row.pct * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function TierDot({ tier }) {
  return (
    <span
      className="inline-block w-1.5 h-1.5 rounded-full ml-2"
      style={{ backgroundColor: RISK_TIER_COLORS[tier] }}
    />
  );
}

function LegendDot({ color, label, shape = 'dot' }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {shape === 'bar' ? (
        <span className="w-3 h-2 rounded-sm" style={{ backgroundColor: color }} />
      ) : (
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      )}
      <span className="text-slate-500">{label}</span>
    </span>
  );
}

// ─── Insight callout ─────────────────────────────────────────────────────────
function InsightCallout({ costSavings, window }) {
  // Yankee saves are derived from al-nakheel's window total. Single biggest
  // intervention is illustrative — kept constant across windows since it's a
  // historical event, not a window-scoped figure.
  // Illustrative — will derive from real /alerts history once available
  const yankeeSavesYtd = costSavings.status === 'ok'
    ? costSavings.data.breakdown_by_machine.find((m) => m.machine_id === 'al-nakheel')?.cost_saved_usd ?? 0
    : null;

  const nakheelPct = costSavings.status === 'ok' && costSavings.data.estimated_cost_saved_usd
    ? Math.round((costSavings.data.breakdown_by_machine.find((m) => m.machine_id === 'al-nakheel')?.cost_saved_usd ?? 0) / costSavings.data.estimated_cost_saved_usd * 100)
    : null;

  const yankeeLabel = window === 'all' ? 'Yankee-related saves (all-time)'
                    : window === 'qtd' ? 'Yankee-related saves (QTD)'
                    : window === 'mtd' ? 'Yankee-related saves (MTD)'
                    : 'Yankee-related saves (YTD)';

  return (
    <div
      className="rounded-xl shadow-card p-5 h-full flex flex-col gap-4 relative overflow-hidden"
      style={{
        background: `linear-gradient(160deg, #FAF8F0 0%, #FFFFFF 70%)`,
        border: `1px solid ${COLORS.gold}33`,
      }}
    >
      <div className="flex items-center gap-2">
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${COLORS.gold}1f`, color: COLORS.gold }}
        >
          <Sparkles className="w-3.5 h-3.5" strokeWidth={2.25} />
        </div>
        <h3 className="text-sm font-semibold text-navy">Where the value comes from</h3>
      </div>

      <p className="text-[13px] text-slate-700 leading-relaxed">
        <span className="font-semibold text-navy">Al Nakheel</span> alone accounts for{' '}
        <span className="font-mono font-semibold tabular-nums" style={{ color: COLORS.gold }}>
          {nakheelPct == null ? '—' : `${nakheelPct}%`}
        </span>{' '}
        of total savings. Its Yankee cylinder is the most expensive failure mode on the fleet —
        bearings cost up to{' '}
        <span className="font-semibold text-navy">$20,000 per hour</span> of unplanned downtime. The
        model has correctly flagged{' '}
        <span className="font-mono font-semibold tabular-nums text-navy">9 out of 12</span> of its
        precursor signals year-to-date.
      </p>

      <div className="mt-auto grid grid-cols-1 gap-2.5 pt-3 border-t" style={{ borderTopColor: `${COLORS.gold}33` }}>
        <KpiRow
          label={yankeeLabel}
          value={yankeeSavesYtd == null ? '—' : fmtCompactUsd(yankeeSavesYtd)}
          accent
        />
        <KpiRow
          label="Highest single intervention"
          value="$120K"
          hint="Bearing 3 replacement, March 2026"
        />
      </div>
    </div>
  );
}

function KpiRow({ label, value, hint, accent }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[11.5px] text-slate-600">{label}</div>
        {hint && <div className="text-[10.5px] text-slate-400 mt-0.5">{hint}</div>}
      </div>
      <span
        className="font-mono text-[18px] font-semibold tabular-nums whitespace-nowrap"
        style={{ color: accent ? COLORS.gold : COLORS.navy }}
      >
        {value}
      </span>
    </div>
  );
}

// ─── Fleet context strip ─────────────────────────────────────────────────────
function FleetStrip({ overview, allTime }) {
  const isLoading = overview.status === 'loading' || allTime.status === 'loading';
  if (isLoading) {
    return (
      <div className="bg-white rounded-xl shadow-card p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
        {[0,1,2,3,4].map((i) => (
          <div key={i} className="h-[68px] rounded-lg bg-slate-100 animate-pulse" />
        ))}
      </div>
    );
  }
  if (overview.status === 'error' || allTime.status === 'error') {
    return <ErrorPanel title="Couldn't load fleet status" inline />;
  }

  const o = overview.data;
  const totalToDate = allTime.data.total_predictions;

  const tiles = [
    { icon: Activity,      label: 'Fleet avg OEE',           value: `${o.fleet_avg_oee_percent.toFixed(1)}%`, color: COLORS.navy },
    { icon: Cpu,           label: 'Machines running',        value: `${o.machines_running} / ${o.machines_total}`, color: COLORS.navy },
    { icon: AlertOctagon,  label: 'Critical alerts',         value: String(o.active_critical_alerts), color: RISK_TIER_COLORS.critical },
    { icon: AlertTriangle, label: 'Warning alerts',          value: String(o.active_warning_alerts),  color: RISK_TIER_COLORS.warning  },
    { icon: TrendingUp,    label: 'Total predictions to-date', value: String(totalToDate),            color: COLORS.navy },
  ];

  return (
    <div className="bg-white rounded-xl shadow-card p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
      {tiles.map((t) => (
        <FleetTile key={t.label} {...t} />
      ))}
    </div>
  );
}

function FleetTile({ icon: Icon, label, value, color }) {
  return (
    <div className="flex items-center gap-3 px-1">
      <div
        className="w-9 h-9 rounded-md flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}14`, color }}
      >
        <Icon className="w-4 h-4" strokeWidth={2.25} />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
        <div className="font-mono text-[20px] font-semibold tabular-nums leading-tight" style={{ color }}>
          {value}
        </div>
      </div>
    </div>
  );
}

// ─── Shared bits ─────────────────────────────────────────────────────────────
function SectionHead({ title, subtitle, icon: Icon }) {
  return (
    <div className="flex items-baseline justify-between gap-3 mb-4">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-slate-400" strokeWidth={2} />}
        <h2 className="text-sm font-semibold text-navy">{title}</h2>
      </div>
      {subtitle && <div className="text-[11px] text-slate-400">{subtitle}</div>}
    </div>
  );
}

function ErrorPanel({ title, onRetry, inline }) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center gap-2 ${
        inline ? 'py-6' : 'bg-white rounded-xl shadow-card p-10'
      }`}
    >
      <AlertOctagon className="w-5 h-5 text-slate-400" strokeWidth={2} />
      <div className="text-[13px] font-semibold text-navy">{title}</div>
      <p className="text-[11.5px] text-slate-500 max-w-xs">
        Something went wrong fetching this section. Try again in a moment.
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-navy text-white text-[11.5px] font-semibold hover:bg-navy/90"
        >
          <RefreshCw className="w-3 h-3" /> Retry
        </button>
      )}
    </div>
  );
}