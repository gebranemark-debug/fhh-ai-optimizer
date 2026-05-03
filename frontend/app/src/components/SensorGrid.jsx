import { COMPONENT_LABELS, SENSOR_SHORT_LABELS } from '../mockData.js';
import { RISK_TIER_COLORS } from '../brand/tokens.js';

// 14 sensor cells. Anomalous cells get a colored ring + dot. Click selects.
// Layout: 2 / 3 / 4 columns by breakpoint. Short, human labels in the cell;
// full sensor_type contract string shown via the `title` tooltip.
export default function SensorGrid({ sensors, selected, onSelect, isMaintenance }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2.5">
      {sensors.map((s) => (
        <SensorCell
          key={s.sensor_type}
          sensor={s}
          selected={s.sensor_type === selected}
          onClick={() => onSelect(s.sensor_type)}
          isMaintenance={isMaintenance}
        />
      ))}
    </div>
  );
}

function SensorCell({ sensor, selected, onClick, isMaintenance }) {
  // Three-state coloring:
  // - critical: backend flagged anomaly AND value is outside the spec band
  // - watch: backend flagged anomaly but value is still inside the spec band
  //   (drift detection — leading indicator, not yet at hard limit)
  // - normal: not flagged
  const [lo, hi] = sensor.normal_range || [0, 0];
  const inBand = sensor.value >= lo && sensor.value <= hi;
  const flagged = sensor.is_anomaly && !isMaintenance;
  const tone = !flagged ? 'normal' : inBand ? 'watch' : 'critical';

  const ring = selected
    ? 'ring-2 ring-navy'
    : tone === 'critical'
    ? 'ring-1 ring-red-200'
    : tone === 'watch'
    ? 'ring-1 ring-amber-200'
    : 'ring-1 ring-slate-200';
  const bg =
    tone === 'critical' ? 'bg-red-50/50' : tone === 'watch' ? 'bg-amber-50/40' : 'bg-white';
  const valueColor =
    tone === 'critical' ? 'text-risk-critical' : tone === 'watch' ? 'text-amber-600' : 'text-navy';
  const dotColor =
    tone === 'critical' ? RISK_TIER_COLORS.critical : RISK_TIER_COLORS.watch;

  const shortLabel = SENSOR_SHORT_LABELS[sensor.sensor_type] || labelize(sensor.sensor_type);

  return (
    <button
      onClick={onClick}
      title={
        tone === 'watch'
          ? `${sensor.sensor_type} — drift toward limit (in spec but trending)`
          : sensor.sensor_type
      }
      className={`text-left rounded-lg p-3 transition-all ${ring} ${bg} hover:shadow-card`}
    >
      <div className="flex items-center justify-between gap-1.5 mb-1">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold truncate">
          {shortLabel}
        </div>
        {tone !== 'normal' && (
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0 animate-pulse"
            style={{ backgroundColor: dotColor }}
          />
        )}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`font-mono text-lg font-semibold tabular-nums ${valueColor}`}>
          {isMaintenance ? '—' : formatVal(sensor.value)}
        </span>
        <span className="font-mono text-[10px] text-slate-400">{sensor.unit}</span>
      </div>
      <div className="text-[10px] text-slate-400 font-mono mt-0.5">
        {sensor.normal_range[0]}–{sensor.normal_range[1]} {sensor.unit}
      </div>
      <div className="text-[9px] text-slate-400 mt-1 flex items-center gap-1">
        <span className="uppercase tracking-wider">{COMPONENT_LABELS[sensor.component_id] || sensor.component_id}</span>
      </div>
    </button>
  );
}

function formatVal(v) {
  if (v === 0) return '0';
  if (Math.abs(v) >= 100) return Math.round(v).toLocaleString();
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(2);
}

function labelize(sensorType) {
  // Fallback only — drops the component prefix.
  // headbox_stock_consistency → "Stock consistency"
  const parts = sensorType.split('_');
  parts.shift();
  const rejoined = parts.join(' ');
  return rejoined.charAt(0).toUpperCase() + rejoined.slice(1);
}