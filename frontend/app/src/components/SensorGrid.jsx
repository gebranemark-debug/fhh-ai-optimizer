import { COMPONENT_LABELS } from '../mockData.js';
import { RISK_TIER_COLORS } from '../brand/tokens.js';

export default function SensorGrid({ sensors, selected, onSelect, isMaintenance }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2.5">
      {sensors.map((s) => (
        <SensorCell key={s.sensor_type} sensor={s} selected={s.sensor_type === selected} onClick={() => onSelect(s.sensor_type)} isMaintenance={isMaintenance} />
      ))}
    </div>
  );
}

function SensorCell({ sensor, selected, onClick, isMaintenance }) {
  const anomaly = sensor.is_anomaly && !isMaintenance;
  const ring = selected ? 'ring-2 ring-navy' : anomaly ? 'ring-1 ring-red-200' : 'ring-1 ring-slate-200';
  const bg = anomaly ? 'bg-red-50/50' : 'bg-white';
  const label = labelize(sensor.sensor_type);

  return (
    <button onClick={onClick} className={`text-left rounded-lg p-3 transition-all ${ring} ${bg} hover:shadow-card`}>
      <div className="flex items-center justify-between gap-1.5 mb-1">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold truncate" title={label}>{label}</div>
        {anomaly && <span className="w-1.5 h-1.5 rounded-full shrink-0 animate-pulse" style={{ backgroundColor: RISK_TIER_COLORS.critical }} />}
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`font-mono text-lg font-semibold tabular-nums ${anomaly ? 'text-risk-critical' : 'text-navy'}`}>
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
  const parts = sensorType.split('_');
  parts.shift();
  const rejoined = parts.join(' ');
  return rejoined.charAt(0).toUpperCase() + rejoined.slice(1);
}