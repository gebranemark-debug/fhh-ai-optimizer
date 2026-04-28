import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceArea, CartesianGrid } from 'recharts';
import { COLORS, RISK_TIER_COLORS } from '../brand/tokens.js';

export default function SensorHistoryChart({ data, sensor, isMaintenance }) {
  if (isMaintenance || !data || !data.points?.length) {
    return (
      <div className="h-[260px] flex items-center justify-center text-sm text-slate-400">
        {isMaintenance ? 'No live readings — machine in maintenance.' : 'Select a sensor to see history.'}
      </div>
    );
  }
  const [lo, hi] = data.normal_range;
  const lineColor = sensor?.is_anomaly ? RISK_TIER_COLORS.critical : COLORS.navy;
  const points = data.points.map((p) => ({
    t: p.timestamp,
    v: p.value,
    label: new Date(p.timestamp).toLocaleString('en-US', { hour: '2-digit', hour12: false, day: 'numeric', month: 'short', timeZone: 'UTC' }),
  }));
  const values = points.map((p) => p.v);
  const yMin = Math.min(lo, ...values) - (hi - lo) * 0.15;
  const yMax = Math.max(hi, ...values) + (hi - lo) * 0.15;

  return (
    <div className="h-[260px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <defs>
            <linearGradient id="histFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={lineColor} stopOpacity={0.18} />
              <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#F1F5F9" vertical={false} />
          <XAxis dataKey="label" interval={Math.max(1, Math.floor(points.length / 8))} tick={{ fontSize: 10, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }} stroke="#E2E8F0" tickLine={false} />
          <YAxis domain={[yMin, yMax]} tick={{ fontSize: 10, fill: '#94A3B8', fontFamily: 'JetBrains Mono, monospace' }} stroke="#E2E8F0" tickLine={false} width={44} tickFormatter={(v) => (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1))} />
          <ReferenceArea y1={lo} y2={hi} fill={RISK_TIER_COLORS.healthy} fillOpacity={0.08} stroke={RISK_TIER_COLORS.healthy} strokeOpacity={0.25} strokeDasharray="3 3" />
          <Tooltip contentStyle={{ background: 'white', border: '1px solid #E2E8F0', borderRadius: 8, fontSize: 12, fontFamily: 'Inter, sans-serif' }} labelStyle={{ color: '#64748B', fontSize: 10 }} formatter={(v) => [`${v} ${data.unit}`, 'Reading']} />
          <Area type="monotone" dataKey="v" stroke={lineColor} strokeWidth={2} fill="url(#histFill)" dot={false} activeDot={{ r: 4, fill: lineColor }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}