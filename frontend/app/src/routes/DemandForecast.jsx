import { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceDot,
  ReferenceLine,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, AlertCircle, Sparkles, RefreshCw } from 'lucide-react';
import { COLORS, RISK_TIER_COLORS } from '../brand/tokens.js';

// ─────────────────────────────────────────────────────────────────────────────
// DemandForecast page — Module 2
//
// All fetches are stubbed with hardcoded payloads (taken verbatim from the
// design brief — Railway production captures). Each is wrapped in a TODO
// marker so Claude Code can swap in lib/api.js calls in the next pass.
// ─────────────────────────────────────────────────────────────────────────────

// ─── Hardcoded mock payloads ─────────────────────────────────────────────────
const MOCK_PRODUCTS = {
  total: 37,
  products: [
    // tissue (15)
    { sku: 'fine-facial-100',     name: 'Fine Facial Tissue 100ct',          category: 'tissue',     unit: 'box' },
    { sku: 'fine-facial-200',     name: 'Fine Facial Tissue 200ct',          category: 'tissue',     unit: 'box' },
    { sku: 'fine-facial-cube',    name: 'Fine Facial Cube Box',              category: 'tissue',     unit: 'box' },
    { sku: 'fine-facial-pocket',  name: 'Fine Pocket Tissue 10pk',           category: 'tissue',     unit: 'pack' },
    { sku: 'fine-toilet-2ply',    name: 'Fine Toilet Tissue 2-ply 12pk',     category: 'tissue',     unit: 'pack' },
    { sku: 'fine-toilet-3ply',    name: 'Fine Toilet Tissue 3-ply 12pk',     category: 'tissue',     unit: 'pack' },
    { sku: 'fine-toilet-4ply',    name: 'Fine Toilet Tissue 4-ply 8pk',      category: 'tissue',     unit: 'pack' },
    { sku: 'fine-toilet-mega',    name: 'Fine Toilet Tissue Mega 24pk',      category: 'tissue',     unit: 'pack' },
    { sku: 'fine-kitchen-2ply',   name: 'Fine Kitchen Towel 2-ply 4pk',      category: 'tissue',     unit: 'pack' },
    { sku: 'fine-kitchen-mega',   name: 'Fine Kitchen Towel Mega 6pk',       category: 'tissue',     unit: 'pack' },
    { sku: 'fine-napkin-100',     name: 'Fine Dinner Napkins 100ct',         category: 'tissue',     unit: 'pack' },
    { sku: 'fine-napkin-50',      name: 'Fine Dinner Napkins 50ct',          category: 'tissue',     unit: 'pack' },
    { sku: 'fine-handkerchief',   name: 'Fine Handkerchief 6pk',             category: 'tissue',     unit: 'pack' },
    { sku: 'fine-wet-wipes-80',   name: 'Fine Wet Wipes 80ct',               category: 'tissue',     unit: 'pack' },
    { sku: 'fine-wet-wipes-40',   name: 'Fine Wet Wipes 40ct Travel',        category: 'tissue',     unit: 'pack' },
    // baby_care (8)
    { sku: 'fine-baby-s1',        name: 'Fine Baby Diapers Size 1 Newborn',  category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-s2',        name: 'Fine Baby Diapers Size 2 Mini',     category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-s3',        name: 'Fine Baby Diapers Size 3 Midi',     category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-s4',        name: 'Fine Baby Diapers Size 4 Maxi',     category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-s5',        name: 'Fine Baby Diapers Size 5 Junior',   category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-s6',        name: 'Fine Baby Diapers Size 6 XL',       category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-pants',     name: 'Fine Baby Training Pants',          category: 'baby_care',  unit: 'pack' },
    { sku: 'fine-baby-wipes',     name: 'Fine Baby Wet Wipes 72ct',          category: 'baby_care',  unit: 'pack' },
    // adult_care (4)
    { sku: 'fine-adult-m',        name: 'Fine Adult Briefs Medium',          category: 'adult_care', unit: 'pack' },
    { sku: 'fine-adult-l',        name: 'Fine Adult Briefs Large',           category: 'adult_care', unit: 'pack' },
    { sku: 'fine-adult-xl',       name: 'Fine Adult Briefs XL',              category: 'adult_care', unit: 'pack' },
    { sku: 'fine-adult-pads',     name: 'Fine Adult Pads 30ct',              category: 'adult_care', unit: 'pack' },
    // wellness (4)
    { sku: 'fine-wellness-pads-r', name: 'Fine Wellness Pads Regular',       category: 'wellness',   unit: 'pack' },
    { sku: 'fine-wellness-pads-n', name: 'Fine Wellness Pads Night',         category: 'wellness',   unit: 'pack' },
    { sku: 'fine-wellness-liners', name: 'Fine Wellness Pantyliners',        category: 'wellness',   unit: 'pack' },
    { sku: 'fine-wellness-tampons',name: 'Fine Wellness Tampons',            category: 'wellness',   unit: 'pack' },
    // fine_guard (3)
    { sku: 'fine-guard-spray',    name: 'Fine Guard Disinfectant Spray',     category: 'fine_guard', unit: 'bottle' },
    { sku: 'fine-guard-wipes',    name: 'Fine Guard Antibacterial Wipes',    category: 'fine_guard', unit: 'pack' },
    { sku: 'fine-guard-soap',     name: 'Fine Guard Hand Soap 500ml',        category: 'fine_guard', unit: 'bottle' },
    // cosmetics (3)
    { sku: 'fine-cosmetic-pads',  name: 'Fine Cosmetic Pads 80ct',           category: 'cosmetics',  unit: 'pack' },
    { sku: 'fine-cosmetic-rounds',name: 'Fine Cosmetic Rounds 100ct',        category: 'cosmetics',  unit: 'pack' },
    { sku: 'fine-cosmetic-buds',  name: 'Fine Cosmetic Cotton Buds 200ct',   category: 'cosmetics',  unit: 'pack' },
  ],
};

const MOCK_MARKETS = {
  markets: [
    { market_id: 'uae',     name: 'United Arab Emirates', currency: 'AED' },
    { market_id: 'ksa',     name: 'Saudi Arabia',         currency: 'SAR' },
    { market_id: 'jordan',  name: 'Jordan',               currency: 'JOD' },
    { market_id: 'egypt',   name: 'Egypt',                currency: 'EGP' },
    { market_id: 'morocco', name: 'Morocco',              currency: 'MAD' },
  ],
};

const MOCK_FORECAST = {
  sku: 'fine-facial-100',
  market: 'uae',
  horizon_months: 6,
  model: 'prophet',
  forecast: [
    { date: '2026-05-01', forecast_value: 154435, lower_bound: 154376, upper_bound: 154499 },
    { date: '2026-06-01', forecast_value: 140208, lower_bound: 140021, upper_bound: 140414 },
    { date: '2026-07-01', forecast_value: 154935, lower_bound: 154556, upper_bound: 155341 },
    { date: '2026-08-01', forecast_value: 183598, lower_bound: 182996, upper_bound: 184207 },
    { date: '2026-09-01', forecast_value: 147410, lower_bound: 146540, upper_bound: 148255 },
    { date: '2026-10-01', forecast_value: 163913, lower_bound: 162773, upper_bound: 165054 },
  ],
  seasonality_events: [
    { date: '2026-03-10', label: 'Ramadan begins', expected_lift_percent: 35 },
    { date: '2026-04-09', label: 'Eid al-Fitr',    expected_lift_percent: 22 },
  ],
  regressors_used: ['historical_sales', 'ramadan_calendar', 'b2b_pipeline'],
  generated_at: '2026-04-25T14:30:00Z',
};

// Per-tab scenario response. Keyed by tab id.
const MOCK_SCENARIOS = {
  ramadan: {
    delta_summary: { total_baseline_units: 944499, total_scenario_units: 1008758, delta_units: 64259, delta_percent: 6.8 },
    summary: 'Ramadan demand surge concentrates in August, driving the largest single-month spike of the horizon.',
    scale: { '2026-08-01': 1.35 },
  },
  supply: {
    delta_summary: { total_baseline_units: 944499, total_scenario_units: 802824, delta_units: -141675, delta_percent: -15.0 },
    summary: 'Supply disruption flows through every month uniformly, depressing the horizon evenly.',
    scaleAll: 0.85,
  },
  promotion: {
    delta_summary: { total_baseline_units: 944499, total_scenario_units: 1171178, delta_units: 226679, delta_percent: 24.0 },
    summary: 'Price elasticity drives the strongest positive horizon lift — magnitude depends on category sensitivity.',
    scaleAll: 1.24,
  },
  competitor: {
    delta_summary: { total_baseline_units: 944499, total_scenario_units: 880914, delta_units: -63585, delta_percent: -6.7 },
    summary: 'Competitor entry erodes baseline demand gradually, trimming each month roughly in line with share loss.',
    scaleAll: 0.933,
  },
};

const MOCK_ANOMALIES = {
  anomalies: [
    { anomaly_id: 'anm-2026-04-22-001', sku: 'fine-baby-s3',     market: 'ksa',   detected_at: '2026-04-22', type: 'spike',       magnitude_percent: 47, explanation: 'Sales 47% above expected — possible distributor restocking or demand surge.' },
    { anomaly_id: 'anm-2026-04-15-002', sku: 'fine-toilet-3ply', market: 'uae',   detected_at: '2026-04-15', type: 'dip',         magnitude_percent: 32, explanation: 'Sales 32% below expected — short-term supply disruption flagged in operations log.' },
    { anomaly_id: 'anm-2026-04-08-003', sku: 'fine-facial-200',  market: 'egypt', detected_at: '2026-04-08', type: 'trend_break', magnitude_percent: 18, explanation: 'Sustained 18% downward shift since April 2025. Possible competitor entry or category re-pricing.' },
  ],
};

const MOCK_SEASONALITY = {
  sku: 'fine-facial-100',
  market: null,
  yearly_pattern: [
    { month: 1,  index: 0.98 }, { month: 2,  index: 0.96 }, { month: 3,  index: 1.28 },
    { month: 4,  index: 1.04 }, { month: 5,  index: 0.94 }, { month: 6,  index: 0.96 },
    { month: 7,  index: 0.98 }, { month: 8,  index: 1.07 }, { month: 9,  index: 0.94 },
    { month: 10, index: 0.95 }, { month: 11, index: 0.94 }, { month: 12, index: 0.96 },
  ],
  events: [
    { name: 'ramadan',        average_lift_percent: 35 },
    { name: 'eid_al_fitr',    average_lift_percent: 22 },
    { name: 'back_to_school', average_lift_percent: 12 },
  ],
};

// ─── Constants ───────────────────────────────────────────────────────────────
const HORIZONS = [3, 6, 9, 12];

const CATEGORY_LABELS = {
  tissue: 'Tissue',
  baby_care: 'Baby Care',
  adult_care: 'Adult Care',
  wellness: 'Wellness',
  fine_guard: 'Fine Guard',
  cosmetics: 'Cosmetics',
};

const SCENARIO_TABS = [
  { id: 'ramadan',    emoji: '🌙', label: 'Ramadan Boost' },
  { id: 'supply',     emoji: '📉', label: 'Supply Disruption' },
  { id: 'promotion',  emoji: '🏷️', label: 'Promotion (10% price drop)' },
  { id: 'competitor', emoji: '⚔️', label: 'Competitor Entry' },
];

const ANOMALY_COLOR = {
  spike:       '#F97316', // warning orange
  dip:         '#EF4444', // critical red
  trend_break: '#F59E0B', // watch yellow
};

const ANOMALY_LABEL = {
  spike: 'Spike',
  dip: 'Dip',
  trend_break: 'Trend break',
};

const MONTH_INITIALS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
const MONTH_NAMES_LONG = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// ─── Format helpers ──────────────────────────────────────────────────────────
const fmtNum = (n) => (n == null ? '—' : Math.round(n).toLocaleString('en-US'));
const fmtSigned = (n) => (n >= 0 ? '+' : '−') + fmtNum(Math.abs(n));
const fmtSignedPct = (n) => (n >= 0 ? '+' : '−') + Math.abs(n).toFixed(1) + '%';
const fmtCompact = (n) => {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${Math.round(n / 1_000)}K`;
  return `${Math.round(n)}`;
};
const fmtMonthShort = (iso) => {
  const d = new Date(iso);
  return `${MONTH_NAMES_LONG[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
};
const fmtMonthAxis = (iso) => {
  const d = new Date(iso);
  return MONTH_NAMES_LONG[d.getUTCMonth()];
};
const fmtDayDate = (iso) => {
  const d = new Date(iso);
  return `${String(d.getUTCDate()).padStart(2, '0')} ${MONTH_NAMES_LONG[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
};
const fmtGenerated = (iso) => {
  const d = new Date(iso);
  return `Updated ${String(d.getUTCDate()).padStart(2, '0')} ${MONTH_NAMES_LONG[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')} UTC`;
};
// ─── Mock variation helpers (throwaway — Task 5 wiring deletes this) ────────
function hashString(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h) + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

function generateForecast(sku, market, horizon) {
  const seed = hashString(sku + ':' + market);
  const baselineLevel = 80000 + (seed % 200000);          // 80K–280K
  const seasonalityStrength = 0.85 + ((seed >> 8) % 40) / 100; // 0.85–1.25

  const startMonthIdx = 4; // May
  const startYear = 2026;
  const monthMultipliers = [0.98, 0.96, 1.28, 1.04, 0.94, 0.96, 0.98, 1.07, 0.94, 0.95, 0.94, 0.96];

  const points = [];
  for (let i = 0; i < horizon; i++) {
    const monthIdx = (startMonthIdx + i) % 12;
    const yearOffset = Math.floor((startMonthIdx + i) / 12);
    const date = `${startYear + yearOffset}-${String(monthIdx + 1).padStart(2, '0')}-01`;
    const seasonalFactor = 1 + (monthMultipliers[monthIdx] - 1) * seasonalityStrength;
    const noise = (((seed >> (i * 3)) % 100) - 50) / 1000; // ±5% deterministic
    const value = Math.max(1000, Math.round(baselineLevel * seasonalFactor * (1 + noise)));
    const ciHalf = Math.max(20, Math.round(value * 0.0004));
    points.push({ date, forecast_value: value, lower_bound: value - ciHalf, upper_bound: value + ciHalf });
  }
  return points;
}

function generateSeasonality(sku) {
  const seed = hashString(sku);
  const intensity = 0.7 + ((seed >> 4) % 60) / 100; // 0.7–1.3
  const phaseShift = seed % 12;
  const basePattern = [0.98, 0.96, 1.28, 1.04, 0.94, 0.96, 0.98, 1.07, 0.94, 0.95, 0.94, 0.96];
  const yearly_pattern = basePattern.map((_, i) => {
    const shifted = basePattern[(i + phaseShift) % 12];
    const adjusted = 1 + (shifted - 1) * intensity;
    return { month: i + 1, index: Number(adjusted.toFixed(2)) };
  });
  return { sku, market: null, yearly_pattern, events: MOCK_SEASONALITY.events };
}
// ─── Scenario per-segment modulation (throwaway — Task 5 deletes this) ─────
// MOCK_SCENARIOS holds the *average* impact. Real elasticity varies by SKU
// category and market. We modulate the base scale around 1.0 = "tissue/UAE
// baseline matches what we curled from Railway." Numbers chosen to feel
// plausible: baby_care has low Ramadan boost (babies don't fast), cosmetics
// has high price elasticity (discretionary), Morocco bears more supply
// disruption (most distant from production hubs).
const RAMADAN_CATEGORY_LIFT = {
  tissue: 1.00, baby_care: 0.40, adult_care: 0.60,
  wellness: 0.70, fine_guard: 0.85, cosmetics: 1.20,
};
const RAMADAN_MARKET_LIFT = {
  uae: 1.00, ksa: 1.10, egypt: 1.05, jordan: 1.00, morocco: 0.90,
};
const PROMOTION_ELASTICITY = {
  tissue: 1.00, baby_care: 0.50, adult_care: 0.45,
  wellness: 0.80, fine_guard: 0.65, cosmetics: 1.30,
};
const SUPPLY_MARKET_EXPOSURE = {
  uae: 1.00, ksa: 1.15, egypt: 0.85, jordan: 0.90, morocco: 1.30,
};
const COMPETITOR_MARKET_VULNERABILITY = {
  uae: 1.00, ksa: 0.85, egypt: 1.20, jordan: 0.95, morocco: 1.40,
};

function scenarioModifier(scenarioId, category, market) {
  if (scenarioId === 'ramadan')    return (RAMADAN_CATEGORY_LIFT[category] ?? 1) * (RAMADAN_MARKET_LIFT[market] ?? 1);
  if (scenarioId === 'promotion')  return PROMOTION_ELASTICITY[category] ?? 1;
  if (scenarioId === 'supply')     return SUPPLY_MARKET_EXPOSURE[market] ?? 1;
  if (scenarioId === 'competitor') return COMPETITOR_MARKET_VULNERABILITY[market] ?? 1;
  return 1;
}
// ─── Page ────────────────────────────────────────────────────────────────────
export default function DemandForecast() {
  // Selectors
  const [sku, setSku] = useState('fine-facial-100');
  const [market, setMarket] = useState('uae');
  const [horizon, setHorizon] = useState(6);

  // Async state per resource
  const [products, setProducts] = useState({ status: 'loading', data: null, error: null });
  const [markets, setMarkets] = useState({ status: 'loading', data: null, error: null });
  const [forecast, setForecast] = useState({ status: 'loading', data: null, error: null });
  const [scenarios, setScenarios] = useState({ status: 'loading', data: null, error: null });
  const [anomalies, setAnomalies] = useState({ status: 'loading', data: null, error: null });
  const [seasonality, setSeasonality] = useState({ status: 'loading', data: null, error: null });

  // Active scenario tab
  const [activeTab, setActiveTab] = useState('ramadan');

  // Load products + markets once
  useEffect(() => {
    // TODO(wiring): replace with getProducts()
    const t1 = setTimeout(() => setProducts({ status: 'ok', data: MOCK_PRODUCTS, error: null }), 60);
    // TODO(wiring): replace with getMarkets()
    const t2 = setTimeout(() => setMarkets({ status: 'ok', data: MOCK_MARKETS, error: null }), 60);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  // Re-fetch forecast / scenarios on selector change
  useEffect(() => {
    setForecast({ status: 'loading', data: null, error: null });
    setScenarios({ status: 'loading', data: null, error: null });
    // TODO(wiring): replace with getForecast(sku, market, horizon)
    const t1 = setTimeout(() => {
      setForecast({
        status: 'ok',
        data: {
          ...MOCK_FORECAST,
          sku,
          market,
          horizon_months: horizon,
          forecast: generateForecast(sku, market, horizon),
        },
        error: null,
      });
    }, 200);
    // TODO(wiring): replace with getAllScenarios(sku, market, horizon) — one call per tab id
    const t2 = setTimeout(() => {
      setScenarios({ status: 'ok', data: MOCK_SCENARIOS, error: null });
    }, 240);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [sku, market, horizon]);

  // Anomalies + seasonality
  useEffect(() => {
    // TODO(wiring): replace with getDemandAnomalies()
    const t1 = setTimeout(() => setAnomalies({ status: 'ok', data: MOCK_ANOMALIES, error: null }), 80);
    return () => clearTimeout(t1);
  }, []);

  useEffect(() => {
    setSeasonality({ status: 'loading', data: null, error: null });
    // TODO(wiring): replace with getSeasonality(sku)
    const t1 = setTimeout(() => setSeasonality({ status: 'ok', data: generateSeasonality(sku), error: null }), 120);
    return () => clearTimeout(t1);
  }, [sku]);

  // Lookup helpers
  const productMap = useMemo(() => {
    const m = new Map();
    products.data?.products?.forEach((p) => m.set(p.sku, p));
    return m;
  }, [products.data]);

  const marketMap = useMemo(() => {
    const m = new Map();
    markets.data?.markets?.forEach((mk) => m.set(mk.market_id, mk));
    return m;
  }, [markets.data]);

  return (
    <div className="px-8 py-7 max-w-[1400px] flex flex-col gap-6">
      <Header
        sku={sku} setSku={setSku}
        market={market} setMarket={setMarket}
        horizon={horizon} setHorizon={setHorizon}
        products={products}
        markets={markets}
        generatedAt={forecast.data?.generated_at}
      />

      <ForecastSection forecast={forecast} />
<ScenarioSection
  forecast={forecast}
  scenarios={scenarios}
  activeTab={activeTab}
  setActiveTab={setActiveTab}
  sku={sku}
  market={market}
  productMap={productMap}
/>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3">
          <AnomaliesSection anomalies={anomalies} productMap={productMap} marketMap={marketMap} />
        </div>
        <div className="lg:col-span-2">
          <SeasonalitySection seasonality={seasonality} />
        </div>
      </div>
    </div>
  );
}

// ─── Header ──────────────────────────────────────────────────────────────────
function Header({ sku, setSku, market, setMarket, horizon, setHorizon, products, markets, generatedAt }) {
  // Group products by category, alphabetical within each.
  const groupedProducts = useMemo(() => {
    if (products.status !== 'ok') return [];
    const byCat = {};
    for (const p of products.data.products) {
      (byCat[p.category] = byCat[p.category] || []).push(p);
    }
    Object.values(byCat).forEach((arr) => arr.sort((a, b) => a.name.localeCompare(b.name)));
    return Object.keys(byCat).map((cat) => ({
      category: cat,
      label: CATEGORY_LABELS[cat] || cat,
      items: byCat[cat],
    }));
  }, [products]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
            Module 2 · Demand forecasting
          </div>
          <h1 className="text-[24px] font-semibold text-navy tracking-tight mt-0.5">Demand Forecast</h1>
          <p className="text-[13px] text-slate-500 mt-1 max-w-2xl">
            Prophet-based forecasts across 37 SKUs and 5 markets.
          </p>
        </div>
        {generatedAt && (
          <div className="text-[11px] text-slate-400 font-mono mt-1 whitespace-nowrap">
            {fmtGenerated(generatedAt)}
          </div>
        )}
      </div>

      <div className="mt-4 bg-white rounded-xl shadow-card px-4 py-3 flex items-center gap-3 flex-wrap">
        <Field label="SKU">
          {products.status !== 'ok' ? (
            <SkeletonInput w={260} />
          ) : (
            <select
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              className="text-[13px] bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 text-navy min-w-[260px]"
            >
              {groupedProducts.map((g) => (
                <optgroup key={g.category} label={g.label}>
                  {g.items.map((p) => (
                    <option key={p.sku} value={p.sku}>{p.name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          )}
        </Field>

        <Field label="Market">
          {markets.status !== 'ok' ? (
            <SkeletonInput w={220} />
          ) : (
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value)}
              className="text-[13px] bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 text-navy min-w-[220px]"
            >
              {markets.data.markets.map((m) => (
                <option key={m.market_id} value={m.market_id}>
                  {m.name} ({m.currency})
                </option>
              ))}
            </select>
          )}
        </Field>

        <Field label="Horizon">
          <div className="flex items-center gap-1 bg-slate-100 rounded-md p-0.5">
            {HORIZONS.map((h) => (
              <button
                key={h}
                onClick={() => setHorizon(h)}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                  horizon === h
                    ? 'bg-white text-navy shadow-sm'
                    : 'text-slate-500 hover:text-navy'
                }`}
              >
                {h} mo
              </button>
            ))}
          </div>
        </Field>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{label}</span>
      {children}
    </label>
  );
}

function SkeletonInput({ w = 200 }) {
  return <div className="h-[30px] rounded-md bg-slate-100 animate-pulse" style={{ width: w }} />;
}

// ─── Forecast (KPIs + main chart) ────────────────────────────────────────────
function ForecastSection({ forecast }) {
  if (forecast.status === 'loading') {
    return (
      <div className="bg-white rounded-xl shadow-card p-5">
        <div className="grid grid-cols-3 gap-3 mb-4">
          {[0,1,2].map((i) => <div key={i} className="h-[78px] rounded-lg bg-slate-100 animate-pulse" />)}
        </div>
        <div className="h-[320px] rounded-lg bg-slate-100 animate-pulse" />
      </div>
    );
  }
  if (forecast.status === 'error' || !forecast.data) {
    return <ErrorPanel title="Couldn't load forecast" onRetry={() => window.location.reload()} />;
  }

  const fc = forecast.data.forecast;
  if (!fc || fc.length === 0) {
    return (
      <EmptyPanel message="No forecast available for this SKU + market combination." />
    );
  }

  const total = fc.reduce((s, p) => s + p.forecast_value, 0);
  const avgMonthly = total / fc.length;
  // Average CI half-width as % of the forecast value.
  const avgCiPct = (fc.reduce((s, p) => {
    const half = (p.upper_bound - p.lower_bound) / 2;
    return s + half / p.forecast_value;
  }, 0) / fc.length) * 100;

  // Map seasonality events that fall inside the visible horizon onto their
  // closest forecast point so the dot lands on the line.
  const eventDots = (forecast.data.seasonality_events || [])
    .map((e) => {
      const eDate = new Date(e.date).getTime();
      const closest = fc.reduce((best, p) => {
        const diff = Math.abs(new Date(p.date).getTime() - eDate);
        return !best || diff < best.diff ? { p, diff } : best;
      }, null);
      // Only show events within ~45 days of a forecast point so we don't
      // anchor a March event onto a May dot. Saves the user from a weird mark.
      if (!closest || closest.diff > 1000 * 60 * 60 * 24 * 45) return null;
      return { ...e, anchor: closest.p };
    })
    .filter(Boolean);

  return (
    <section className="bg-white rounded-xl shadow-card p-5">
      <div className="grid grid-cols-3 gap-3 mb-5">
        <KpiTile label="Total horizon demand" value={fmtNum(total)} unit="units" accent="gold" />
        <KpiTile label="Avg monthly demand" value={fmtNum(avgMonthly)} unit="units / mo" accent="gold" />
        <KpiTile
          label="Model confidence"
          value={`±${avgCiPct.toFixed(2)}%`}
          unit="avg CI half-width"
          accent="navy"
          hint="Narrow CI = high model certainty"
        />
      </div>

      <div className="h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={fc} margin={{ top: 12, right: 24, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="ciFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.navy} stopOpacity={0.18} />
                <stop offset="100%" stopColor={COLORS.navy} stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={fmtMonthAxis}
              tick={{ fontSize: 11, fill: '#64748B' }}
              tickLine={false}
              axisLine={{ stroke: '#E2E8F0' }}
            />
            <YAxis
              tickFormatter={fmtCompact}
              tick={{ fontSize: 11, fill: '#64748B' }}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <Tooltip content={<ForecastTooltip />} />
            <Area
              dataKey="upper_bound"
              stroke="none"
              fill="url(#ciFill)"
              activeDot={false}
              isAnimationActive={false}
            />
            <Area
              dataKey="lower_bound"
              stroke="none"
              fill="#fff"
              activeDot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="forecast_value"
              stroke={COLORS.navy}
              strokeWidth={2}
              dot={{ r: 4, fill: COLORS.navy, stroke: '#fff', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: COLORS.navy, stroke: '#fff', strokeWidth: 2 }}
              isAnimationActive={false}
            />
            {eventDots.map((ev) => (
              <ReferenceDot
                key={ev.date}
                x={ev.anchor.date}
                y={ev.anchor.forecast_value}
                r={7}
                fill={COLORS.gold}
                stroke="#fff"
                strokeWidth={2}
                shape={<DiamondShape />}
                ifOverflow="extendDomain"
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex items-center justify-between flex-wrap gap-2 text-[11px] text-slate-500">
        <div>
          Model: <span className="font-semibold text-navy">Prophet</span>
          <span className="mx-2 text-slate-300">·</span>
          Regressors: <span className="font-mono text-slate-600">{(forecast.data.regressors_used || []).join(', ')}</span>
        </div>
        <div className="flex items-center gap-3">
          <LegendDot color={COLORS.navy} label="Forecast" />
          <LegendDot color={COLORS.gold} label="Seasonality event" shape="diamond" />
          <LegendDot color={COLORS.navy} opacity={0.18} label="Confidence interval" shape="band" />
        </div>
      </div>

      {eventDots.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {eventDots.map((ev) => (
            <span
              key={ev.date}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-50 ring-1 ring-amber-200 text-[10.5px] text-amber-800"
            >
              <span className="w-1.5 h-1.5 rotate-45" style={{ backgroundColor: COLORS.gold }} />
              {ev.label} · {fmtDayDate(ev.date)} · +{ev.expected_lift_percent}%
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function DiamondShape({ cx, cy, fill, stroke, strokeWidth }) {
  if (cx == null || cy == null) return null;
  const s = 6;
  const points = `${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`;
  return <polygon points={points} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
}

function ForecastTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const half = (row.upper_bound - row.lower_bound) / 2;
  return (
    <div className="bg-white rounded-lg shadow-lg ring-1 ring-slate-200 px-3 py-2 text-[12px]">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
        {fmtMonthShort(row.date)}
      </div>
      <div className="font-mono text-navy font-semibold tabular-nums">
        {fmtNum(row.forecast_value)} <span className="text-slate-400 text-[10px]">units</span>
      </div>
      <div className="font-mono text-[10px] text-slate-500 mt-0.5">
        ± {fmtNum(half)} ({((half / row.forecast_value) * 100).toFixed(2)}%)
      </div>
    </div>
  );
}

function KpiTile({ label, value, unit, accent = 'navy', hint }) {
  const accentColor = accent === 'gold' ? COLORS.gold : COLORS.navy;
  return (
    <div
      className="rounded-lg p-3.5 flex flex-col gap-0.5 border-l-2"
      style={{ backgroundColor: '#F8FAFC', borderLeftColor: accentColor }}
    >
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">{label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-[26px] font-semibold tabular-nums leading-none text-navy">
          {value}
        </span>
        <span className="text-[10.5px] text-slate-400">{unit}</span>
      </div>
      {hint && <div className="text-[10px] text-slate-400 mt-0.5">{hint}</div>}
    </div>
  );
}

function LegendDot({ color, label, opacity = 1, shape = 'dot' }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {shape === 'diamond' ? (
        <span className="w-2 h-2 rotate-45" style={{ backgroundColor: color }} />
      ) : shape === 'band' ? (
        <span className="w-3 h-2 rounded-sm" style={{ backgroundColor: color, opacity }} />
      ) : (
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color, opacity }} />
      )}
      <span className="text-slate-500">{label}</span>
    </span>
  );
}

// ─── Scenario explorer ───────────────────────────────────────────────────────
function ScenarioSection({ forecast, scenarios, activeTab, setActiveTab, sku, market, productMap }) {
  if (forecast.status !== 'ok' || scenarios.status !== 'ok') {
    return (
      <section className="bg-white rounded-xl shadow-card p-5">
        <SectionHead title="What-if Scenarios" subtitle="See how your forecast shifts under different conditions." />
        <div className="h-[280px] rounded-lg bg-slate-100 animate-pulse" />
      </section>
    );
  }

  const baseline = forecast.data.forecast;
  const scenario = scenarios.data[activeTab];
  // Build the scenario series from the baseline using the per-tab scale rules.
  // Lets the chart stay perfectly in sync with the delta_summary numbers without
  // a second array of points to babysit.
  // Apply per-(category, market) modulation to the base scenario impact.
  const product = productMap?.get?.(sku);
  const category = product?.category || 'tissue';
  const modifier = scenarioModifier(activeTab, category, market);

  const scenarioSeries = baseline.map((p) => {
    let baseScale = 1;
    if (scenario.scaleAll != null) baseScale = scenario.scaleAll;
    if (scenario.scale && scenario.scale[p.date] != null) baseScale = scenario.scale[p.date];
    // Modulate the delta from 1.0; default modifier=1 → identical to before.
    const modulatedScale = 1 + (baseScale - 1) * modifier;
    const value = p.forecast_value * modulatedScale;
    return { date: p.date, baseline: p.forecast_value, scenario: Math.round(value) };
  });

  // Recompute deltas from the actual series so the right card matches the
  // currently selected SKU/market/horizon (until Task 5 wires real backend).
  const totalBaseline = scenarioSeries.reduce((s, p) => s + p.baseline, 0);
  const totalScenario = scenarioSeries.reduce((s, p) => s + p.scenario, 0);
  const liveDelta = {
    total_baseline_units: totalBaseline,
    total_scenario_units: totalScenario,
    delta_units: totalScenario - totalBaseline,
    delta_percent: totalBaseline > 0 ? ((totalScenario - totalBaseline) / totalBaseline) * 100 : 0,
  };

  const positive = liveDelta.delta_percent >= 0;
  const deltaColor = positive ? RISK_TIER_COLORS.healthy : RISK_TIER_COLORS.critical;

  return (
    <section className="bg-white rounded-xl shadow-card p-5">
      <SectionHead
        title="What-if Scenarios"
        subtitle="See how your forecast shifts under different conditions."
        icon={Sparkles}
      />

      <div className="flex items-center gap-1.5 flex-wrap mb-4">
        {SCENARIO_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors ${
              activeTab === t.id
                ? 'bg-navy text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <span className="mr-1.5">{t.emoji}</span>
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={scenarioSeries} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtMonthAxis}
                tick={{ fontSize: 11, fill: '#64748B' }}
                tickLine={false}
                axisLine={{ stroke: '#E2E8F0' }}
              />
              <YAxis
                tickFormatter={fmtCompact}
                tick={{ fontSize: 11, fill: '#64748B' }}
                tickLine={false}
                axisLine={false}
                width={48}
              />
              <Tooltip content={<ScenarioTooltip />} />
              <Legend
                verticalAlign="top"
                align="right"
                height={28}
                iconType="circle"
                wrapperStyle={{ fontSize: 11, color: '#64748B' }}
              />
              <Line
                type="monotone"
                name="Baseline"
                dataKey="baseline"
                stroke={COLORS.navy}
                strokeWidth={2}
                dot={{ r: 4, fill: COLORS.navy, stroke: '#fff', strokeWidth: 2 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                name="Scenario"
                dataKey="scenario"
                stroke={COLORS.gold}
                strokeWidth={2}
                dot={{ r: 4, fill: COLORS.gold, stroke: '#fff', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <div className="lg:col-span-2 rounded-lg p-5 flex flex-col gap-3" style={{ backgroundColor: '#F8FAFC' }}>
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
            Horizon delta
          </div>
          <div className="flex items-baseline gap-2">
            {positive ? (
              <TrendingUp className="w-7 h-7 shrink-0" style={{ color: deltaColor }} strokeWidth={2.25} />
            ) : (
              <TrendingDown className="w-7 h-7 shrink-0" style={{ color: deltaColor }} strokeWidth={2.25} />
            )}
            <span
              className="font-mono text-[44px] font-semibold tabular-nums leading-none tracking-tight"
              style={{ color: deltaColor }}
            >
              {fmtSignedPct(liveDelta.delta_percent)}
            </span>
          </div>
          <div
            className="font-mono text-[15px] tabular-nums font-semibold"
            style={{ color: deltaColor }}
          >
            {fmtSigned(liveDelta.delta_units)} <span className="text-slate-400 font-normal text-[12px]">units</span>
          </div>

          <div className="border-t border-slate-200 pt-3 mt-1 grid grid-cols-2 gap-y-1 text-[11.5px]">
            <span className="text-slate-500">Baseline total</span>
            <span className="font-mono text-navy text-right tabular-nums">{fmtNum(liveDelta.total_baseline_units)}</span>
            <span className="text-slate-500">Scenario total</span>
            <span className="font-mono text-navy text-right tabular-nums">{fmtNum(liveDelta.total_scenario_units)}</span>
          </div>

          <p className="text-[12px] text-slate-600 leading-relaxed border-t border-slate-200 pt-3 mt-1">
            {scenario.summary}
          </p>
        </div>
      </div>
    </section>
  );
}

function ScenarioTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-white rounded-lg shadow-lg ring-1 ring-slate-200 px-3 py-2 text-[12px]">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
        {fmtMonthShort(row.date)}
      </div>
      <div className="flex items-center justify-between gap-4 font-mono tabular-nums">
        <span className="text-slate-500 inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.navy }} />
          Baseline
        </span>
        <span className="text-navy font-semibold">{fmtNum(row.baseline)}</span>
      </div>
      <div className="flex items-center justify-between gap-4 font-mono tabular-nums">
        <span className="text-slate-500 inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.gold }} />
          Scenario
        </span>
        <span className="font-semibold" style={{ color: COLORS.gold }}>{fmtNum(row.scenario)}</span>
      </div>
    </div>
  );
}

// ─── Anomalies ───────────────────────────────────────────────────────────────
function AnomaliesSection({ anomalies, productMap, marketMap }) {
  return (
    <section className="bg-white rounded-xl shadow-card p-5 h-full">
      <SectionHead
        title="Recent Demand Anomalies"
        subtitle="Flagged across all SKUs in the last 30 days"
        icon={AlertCircle}
      />
      {anomalies.status === 'loading' ? (
        <div className="flex flex-col gap-2.5">
          {[0,1,2].map((i) => <div key={i} className="h-[88px] rounded-lg bg-slate-100 animate-pulse" />)}
        </div>
      ) : anomalies.status === 'error' || !anomalies.data ? (
        <ErrorPanel title="Couldn't load anomalies" inline />
      ) : anomalies.data.anomalies.length === 0 ? (
        <p className="text-[12px] text-slate-500">No anomalies flagged in the last 30 days.</p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {anomalies.data.anomalies.map((a) => (
            <AnomalyCard key={a.anomaly_id} anomaly={a} productMap={productMap} marketMap={marketMap} />
          ))}
        </div>
      )}
    </section>
  );
}

function AnomalyCard({ anomaly, productMap, marketMap }) {
  const color = ANOMALY_COLOR[anomaly.type] || RISK_TIER_COLORS.watch;
  const product = productMap.get(anomaly.sku);
  const market = marketMap.get(anomaly.market);
  const productName = product?.name || anomaly.sku;
  const marketName = market?.name || anomaly.market;

  // Sign the magnitude badge per type:
  //   spike       → positive (above expected)
  //   dip         → negative (below expected)
  //   trend_break → negative (sustained downward shift, per the brief example)
  const sign = anomaly.type === 'spike' ? '+' : '−';

  return (
    <div className="rounded-lg p-3.5 ring-1 ring-slate-200 bg-white flex gap-3 items-start">
      <div className="w-1 self-stretch rounded-full shrink-0" style={{ backgroundColor: color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span
            className="inline-flex items-center px-1.5 py-0.5 rounded text-[9.5px] font-semibold uppercase tracking-wider"
            style={{ backgroundColor: `${color}1a`, color }}
          >
            {ANOMALY_LABEL[anomaly.type]}
          </span>
          <span className="text-[11px] text-slate-400 font-mono">{fmtDayDate(anomaly.detected_at)}</span>
          <span className="text-slate-300">·</span>
          <span className="text-[12px] text-navy font-medium truncate">{productName}</span>
          <span className="text-[11px] text-slate-400">{marketName}</span>
        </div>
        <p className="text-[12px] text-slate-600 leading-snug">{anomaly.explanation}</p>
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-[16px] font-semibold tabular-nums" style={{ color }}>
          {sign}{anomaly.magnitude_percent}%
        </div>
      </div>
    </div>
  );
}

// ─── Seasonality ─────────────────────────────────────────────────────────────
function SeasonalitySection({ seasonality }) {
  return (
    <section className="bg-white rounded-xl shadow-card p-5 h-full flex flex-col">
      <SectionHead
        title="12-Month Seasonality Index"
        subtitle="Index 1.0 = average month for this SKU"
      />
      {seasonality.status === 'loading' ? (
        <div className="h-[180px] rounded-lg bg-slate-100 animate-pulse" />
      ) : seasonality.status === 'error' || !seasonality.data ? (
        <ErrorPanel title="Couldn't load seasonality" inline />
      ) : (
        <>
          <div className="h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={seasonality.data.yearly_pattern}
                margin={{ top: 6, right: 6, left: -8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 10, fill: '#94A3B8' }}
                  tickLine={false}
                  axisLine={{ stroke: '#E2E8F0' }}
                  tickFormatter={(m) => MONTH_INITIALS[m - 1]}
                  interval={0}
                />
                <YAxis
                  domain={[0.8, 1.4]}
                  ticks={[0.8, 1.0, 1.2, 1.4]}
                  tick={{ fontSize: 10, fill: '#94A3B8' }}
                  tickLine={false}
                  axisLine={false}
                  width={28}
                />
                <Tooltip content={<SeasonalityTooltip />} />
                <ReferenceLine y={1.0} stroke="#94A3B8" strokeDasharray="4 4" />
                <Bar dataKey="index" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                  {seasonality.data.yearly_pattern.map((p) => (
                    <Cell key={p.month} fill={p.index >= 1.0 ? COLORS.gold : '#CBD5E1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-2">
              Recurring events
            </div>
            <div className="flex flex-wrap gap-1.5">
              {seasonality.data.events.map((ev) => (
                <span
                  key={ev.name}
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-amber-50 ring-1 ring-amber-200 text-[11px] text-amber-900"
                >
                  {prettyEventName(ev.name)}
                  <span className="font-mono font-semibold text-amber-800">+{ev.average_lift_percent}%</span>
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function SeasonalityTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const pct = (row.index - 1) * 100;
  return (
    <div className="bg-white rounded-lg shadow-lg ring-1 ring-slate-200 px-3 py-2 text-[12px]">
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
        {MONTH_NAMES_LONG[row.month - 1]}
      </div>
      <div className="font-mono text-navy font-semibold tabular-nums">
        {row.index.toFixed(2)}×
      </div>
      <div className="font-mono text-[10px] text-slate-500 mt-0.5">
        {pct >= 0 ? '+' : ''}{pct.toFixed(0)}% vs. average
      </div>
    </div>
  );
}

function prettyEventName(name) {
  return name
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
    .replace('Eid Al Fitr', 'Eid al-Fitr');
}

// ─── Shared bits ─────────────────────────────────────────────────────────────
function SectionHead({ title, subtitle, icon: Icon }) {
  return (
    <div className="flex items-baseline justify-between gap-3 mb-3">
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
      <AlertCircle className="w-5 h-5 text-slate-400" strokeWidth={2} />
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

function EmptyPanel({ message }) {
  return (
    <div className="bg-white rounded-xl shadow-card p-10 text-center">
      <div className="text-[13px] font-semibold text-navy mb-1">No data</div>
      <p className="text-[12px] text-slate-500">{message}</p>
    </div>
  );
}