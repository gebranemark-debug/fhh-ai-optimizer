// Mock data store — shapes match API_CONTRACT.md v1.1 exactly.
export const COMPONENT_ORDER = ['headbox','visconip','yankee','aircap','softreel','rewinder'];
export const machines = [
  { machine_id: 'al-nakheel', name: 'Al Nakheel', location: 'Abu Dhabi, UAE', model: 'Valmet Advantage DCT 200TS', installation_date: '2018-06-15', status: 'running', current_speed_mpm: 2150, current_oee_percent: 91.4, risk_score: 87, risk_tier: 'critical', active_alerts_count: 3 },
  { machine_id: 'al-bardi', name: 'Al Bardi', location: 'Tenth of Ramadan, Egypt', model: 'Valmet Advantage DCT 200TS', installation_date: '2019-03-22', status: 'running', current_speed_mpm: 2080, current_oee_percent: 93.6, risk_score: 67, risk_tier: 'warning', active_alerts_count: 2 },
  { machine_id: 'al-sindian', name: 'Al Sindian', location: 'Sadat City, Egypt', model: 'Valmet Advantage DCT 200TS', installation_date: '2020-09-08', status: 'maintenance', current_speed_mpm: 0, current_oee_percent: 0, risk_score: 42, risk_tier: 'watch', active_alerts_count: 2 },
  { machine_id: 'al-snobar', name: 'Al Snobar', location: 'Amman, Jordan', model: 'Valmet Advantage DCT 200TS', installation_date: '2021-11-30', status: 'running', current_speed_mpm: 2210, current_oee_percent: 96.1, risk_score: 18, risk_tier: 'healthy', active_alerts_count: 1 },
];

export const COMPONENT_LABELS = {
  headbox: 'Headbox',
  visconip: 'ViscoNip Press',
  yankee: 'Yankee Dryer',
  aircap: 'AirCap Hood',
  softreel: 'SoftReel',
  rewinder: 'Rewinder',
};

// Short labels used in tight cards. Full names remain in COMPONENT_LABELS
// and surface via title tooltip.
export const COMPONENT_SHORT_LABELS = {
  headbox: 'Headbox',
  visconip: 'ViscoNip',
  yankee: 'Yankee',
  aircap: 'AirCap',
  softreel: 'SoftReel',
  rewinder: 'Rewinder',
};

// is_critical flag from API contract — Yankee is the $20K/hr component.
export const COMPONENT_CRITICAL = {
  headbox: false,
  visconip: false,
  yankee: true,
  aircap: false,
  softreel: false,
  rewinder: false,
};

// Short, human-readable labels for sensor cells. Full sensor_type strings
// remain available via the cell's `title` tooltip and the chart header.
export const SENSOR_SHORT_LABELS = {
  headbox_stock_consistency:  'Stock consistency',
  headbox_jet_velocity:       'Jet velocity',
  visconip_nip_load:          'Nip load',
  visconip_felt_moisture:     'Felt moisture',
  yankee_surface_temp:        'Surface temp',
  yankee_steam_pressure:      'Steam pressure',
  yankee_vibration_bearing_3: 'Vibration B3',
  aircap_inlet_temp:          'Inlet temp',
  aircap_exhaust_humidity:    'Exhaust humidity',
  softreel_tension:           'Reel tension',
  softreel_drive_current:     'Drive current',
  rewinder_drive_current:     'Drive current',
  rewinder_dancer_position:   'Dancer position',
  qcs_basis_weight_cd_stddev: 'Basis weight σ',
};

export const alerts = [
  { alert_id:'alt-2026-04-25-0017', machine_id:'al-nakheel', component_id:'yankee',   severity:'critical', risk_score:87, title:'Bearing 3 vibration trending toward failure', description:'Bearing 3 vibration RMS rising 0.4 mm/s/day for 11 days. Current reading 5.8 mm/s vs. 2–4 mm/s normal range. Predicted failure window: 24 hours.', predicted_failure_window_hours:24,  recommended_action:'CRITICAL: Stop line immediately. Replace component now.', estimated_cost_if_unaddressed_usd:480000, created_at:'2026-04-25T08:15:00Z', acknowledged:false },
  { alert_id:'alt-2026-04-25-0014', machine_id:'al-nakheel', component_id:'aircap',   severity:'warning',  risk_score:71, title:'AirCap inlet temperature drift above setpoint', description:'AirCap inlet temperature trending +6 °C above setpoint over 72 h. Energy consumption up 4.1%. Likely burner tuning required.', predicted_failure_window_hours:240, recommended_action:'Schedule burner re-tune during next 4-hour window. Verify gas pressure regulator.', estimated_cost_if_unaddressed_usd:62000, created_at:'2026-04-24T22:40:00Z', acknowledged:false },
  { alert_id:'alt-2026-04-25-0012', machine_id:'al-nakheel', component_id:'visconip', severity:'warning',  risk_score:64, title:'Felt moisture above target — sheet quality at risk', description:'ViscoNip felt moisture at 47.8% (target 35–45%). Drying load on Yankee elevated; softness index trending down.', predicted_failure_window_hours:null, recommended_action:'Inspect felt run; consider felt change at next planned stop.', estimated_cost_if_unaddressed_usd:38000, created_at:'2026-04-24T17:05:00Z', acknowledged:true },
  { alert_id:'alt-2026-04-24-0009', machine_id:'al-bardi',   component_id:'yankee',   severity:'warning',  risk_score:67, title:'Steam pressure oscillation on Yankee header', description:'Steam pressure oscillating ±0.6 bar around setpoint. Possible PRV stiction. Crepe quality variance up 12%.', predicted_failure_window_hours:168, recommended_action:'Schedule PRV inspection within 7 days. Pull historian trend on PV-2102.', estimated_cost_if_unaddressed_usd:84000, created_at:'2026-04-24T11:22:00Z', acknowledged:false },
  { alert_id:'alt-2026-04-24-0007', machine_id:'al-bardi',   component_id:'softreel', severity:'warning',  risk_score:58, title:'Reel tension drift outside tolerance', description:'SoftReel tension drifting low — 168 N/m vs. 180–220 normal. Risk of loose reels and break frequency increase.', predicted_failure_window_hours:null, recommended_action:'Recalibrate dancer load cell. Verify pneumatic supply pressure.', estimated_cost_if_unaddressed_usd:24000, created_at:'2026-04-23T19:48:00Z', acknowledged:false },
  { alert_id:'alt-2026-04-24-0005', machine_id:'al-sindian', component_id:'headbox',  severity:'info',     risk_score:41, title:'Stock temperature low at headbox during warm-up', description:'Stock temperature reading 39 °C during scheduled warm-up. Within expected range for maintenance state.', predicted_failure_window_hours:null, recommended_action:'No action — informational. Will clear when machine returns to running state.', estimated_cost_if_unaddressed_usd:0, created_at:'2026-04-23T08:10:00Z', acknowledged:true },
  { alert_id:'alt-2026-04-23-0003', machine_id:'al-sindian', component_id:'rewinder', severity:'warning',  risk_score:49, title:'Rewinder drive current spike pattern detected', description:'Repeated current spikes on rewinder main drive — 12 events in 48 h. Bearing or coupling wear suspected.', predicted_failure_window_hours:336, recommended_action:'Schedule vibration analysis at next planned stop (already in maintenance).', estimated_cost_if_unaddressed_usd:41000, created_at:'2026-04-22T14:55:00Z', acknowledged:false },
  { alert_id:'alt-2026-04-22-0002', machine_id:'al-snobar',  component_id:'visconip', severity:'info',     risk_score:22, title:'Routine felt life advisory — 18% remaining', description:'Felt life model estimates 18% remaining (≈ 14 days at current load). No anomalies detected.', predicted_failure_window_hours:null, recommended_action:'Order replacement felt; schedule swap during next planned shutdown.', estimated_cost_if_unaddressed_usd:0, created_at:'2026-04-22T07:30:00Z', acknowledged:false },
];

export const componentsByMachine = {
  'al-nakheel': [
    { component_id:'headbox',  health_score:88, tier:'healthy',  last_service_date:'2026-02-14' },
    { component_id:'visconip', health_score:64, tier:'warning',  last_service_date:'2025-11-08' },
    { component_id:'yankee',   health_score: 9, tier:'critical', last_service_date:'2024-09-12' },
    { component_id:'aircap',   health_score:72, tier:'watch',    last_service_date:'2025-12-02' },
    { component_id:'softreel', health_score:86, tier:'healthy',  last_service_date:'2026-01-20' },
    { component_id:'rewinder', health_score:91, tier:'healthy',  last_service_date:'2026-03-05' },
  ],
  'al-bardi': [
    { component_id:'headbox',  health_score:91, tier:'healthy', last_service_date:'2026-03-01' },
    { component_id:'visconip', health_score:78, tier:'watch',   last_service_date:'2025-10-22' },
    { component_id:'yankee',   health_score:58, tier:'warning', last_service_date:'2025-08-15' },
    { component_id:'aircap',   health_score:84, tier:'healthy', last_service_date:'2025-12-10' },
    { component_id:'softreel', health_score:69, tier:'watch',   last_service_date:'2025-11-28' },
    { component_id:'rewinder', health_score:88, tier:'healthy', last_service_date:'2026-02-18' },
  ],
  'al-sindian': [
    { component_id:'headbox',  health_score:82, tier:'healthy', last_service_date:'2026-01-10' },
    { component_id:'visconip', health_score:75, tier:'watch',   last_service_date:'2025-12-15' },
    { component_id:'yankee',   health_score:80, tier:'healthy', last_service_date:'2025-11-04' },
    { component_id:'aircap',   health_score:79, tier:'healthy', last_service_date:'2026-02-20' },
    { component_id:'softreel', health_score:71, tier:'watch',   last_service_date:'2025-10-30' },
    { component_id:'rewinder', health_score:62, tier:'warning', last_service_date:'2025-09-18' },
  ],
  'al-snobar': [
    { component_id:'headbox',  health_score:96, tier:'healthy', last_service_date:'2026-03-22' },
    { component_id:'visconip', health_score:89, tier:'healthy', last_service_date:'2026-01-05' },
    { component_id:'yankee',   health_score:94, tier:'healthy', last_service_date:'2025-11-30' },
    { component_id:'aircap',   health_score:92, tier:'healthy', last_service_date:'2026-02-08' },
    { component_id:'softreel', health_score:90, tier:'healthy', last_service_date:'2026-01-15' },
    { component_id:'rewinder', health_score:95, tier:'healthy', last_service_date:'2026-03-10' },
  ],
};

export const predictionsByMachine = {
  'al-nakheel': [
    { component_id:'headbox',  failure_probability:0.12,   predicted_failure_window_hours:2160, confidence:0.71, recommended_action:'Continue normal operation. Routine inspection scheduled.' },
    { component_id:'visconip', failure_probability:0.3047, predicted_failure_window_hours:720,  confidence:0.74, recommended_action:'Inspect felt run within 7 days. Consider felt change at next planned stop.' },
    { component_id:'yankee',   failure_probability:0.9998, predicted_failure_window_hours:24,   confidence:0.82, recommended_action:'CRITICAL: Stop line immediately. Replace component now.' },
    { component_id:'aircap',   failure_probability:0.1432, predicted_failure_window_hours:360,  confidence:0.68, recommended_action:'Re-tune burner during next 4-hour window. Verify gas pressure regulator.' },
    { component_id:'softreel', failure_probability:0.11,   predicted_failure_window_hours:1800, confidence:0.66, recommended_action:'No action required. Continue monitoring.' },
    { component_id:'rewinder', failure_probability:0.10,   predicted_failure_window_hours:2400, confidence:0.69, recommended_action:'No action required. Continue monitoring.' },
  ],
  'al-bardi': [
    { component_id:'headbox',  failure_probability:0.09,   predicted_failure_window_hours:2400, confidence:0.72, recommended_action:'Continue normal operation.' },
    { component_id:'visconip', failure_probability:0.21,   predicted_failure_window_hours:960,  confidence:0.70, recommended_action:'Monitor felt moisture trend. No immediate action.' },
    { component_id:'yankee',   failure_probability:0.4803, predicted_failure_window_hours:168,  confidence:0.75, recommended_action:'Schedule PRV inspection within 7 days. Pull historian trend on PV-2102.' },
    { component_id:'aircap',   failure_probability:0.13,   predicted_failure_window_hours:1080, confidence:0.69, recommended_action:'Continue normal operation.' },
    { component_id:'softreel', failure_probability:0.3214, predicted_failure_window_hours:504,  confidence:0.71, recommended_action:'Recalibrate dancer load cell. Verify pneumatic supply pressure.' },
    { component_id:'rewinder', failure_probability:0.10,   predicted_failure_window_hours:1920, confidence:0.68, recommended_action:'No action required.' },
  ],
  'al-sindian': [
    { component_id:'headbox',  failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run after machine returns to running state.' },
    { component_id:'visconip', failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run.' },
    { component_id:'yankee',   failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run.' },
    { component_id:'aircap',   failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run.' },
    { component_id:'softreel', failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run.' },
    { component_id:'rewinder', failure_probability:null, predicted_failure_window_hours:null, confidence:null, recommended_action:'Awaiting next prediction run.' },
  ],
  'al-snobar': [
    { component_id:'headbox',  failure_probability:0.04, predicted_failure_window_hours:4320, confidence:0.81, recommended_action:'No action required.' },
    { component_id:'visconip', failure_probability:0.09, predicted_failure_window_hours:2880, confidence:0.78, recommended_action:'Order replacement felt; schedule swap during next planned shutdown.' },
    { component_id:'yankee',   failure_probability:0.05, predicted_failure_window_hours:4080, confidence:0.83, recommended_action:'No action required.' },
    { component_id:'aircap',   failure_probability:0.06, predicted_failure_window_hours:3840, confidence:0.79, recommended_action:'No action required.' },
    { component_id:'softreel', failure_probability:0.07, predicted_failure_window_hours:3360, confidence:0.77, recommended_action:'No action required.' },
    { component_id:'rewinder', failure_probability:0.04, predicted_failure_window_hours:4560, confidence:0.82, recommended_action:'No action required.' },
  ],
};

function makeSensors(overrides = {}, isMaint = false) {
  const base = [
    { sensor_type:'headbox_stock_consistency',  component_id:'headbox',  unit:'%',    value:0.32,  normal_range:[0.28, 0.34] },
    { sensor_type:'headbox_jet_velocity',       component_id:'headbox',  unit:'m/s',  value:25.4,  normal_range:[23.0, 27.0] },
    { sensor_type:'visconip_nip_load',          component_id:'visconip', unit:'kN/m', value:95,    normal_range:[85, 110] },
    { sensor_type:'visconip_felt_moisture',     component_id:'visconip', unit:'%',    value:41.2,  normal_range:[35, 45] },
    { sensor_type:'yankee_surface_temp',        component_id:'yankee',   unit:'°C',   value:112.4, normal_range:[108, 118] },
    { sensor_type:'yankee_steam_pressure',      component_id:'yankee',   unit:'bar',  value:9.6,   normal_range:[9.0, 10.5] },
    { sensor_type:'yankee_vibration_bearing_3', component_id:'yankee',   unit:'mm/s', value:3.1,   normal_range:[2.0, 4.0] },
    { sensor_type:'aircap_inlet_temp',          component_id:'aircap',   unit:'°C',   value:478,   normal_range:[470, 490] },
    { sensor_type:'aircap_exhaust_humidity',    component_id:'aircap',   unit:'%',    value:38,    normal_range:[32, 42] },
    { sensor_type:'softreel_tension',           component_id:'softreel', unit:'N/m',  value:198,   normal_range:[180, 220] },
    { sensor_type:'softreel_drive_current',     component_id:'softreel', unit:'A',    value:142,   normal_range:[130, 160] },
    { sensor_type:'rewinder_drive_current',     component_id:'rewinder', unit:'A',    value:88,    normal_range:[75, 105] },
    { sensor_type:'rewinder_dancer_position',   component_id:'rewinder', unit:'mm',   value:24,    normal_range:[18, 32] },
    { sensor_type:'qcs_basis_weight_cd_stddev', component_id:'rewinder', unit:'g/m²', value:0.8,   normal_range:[0.4, 1.2] },
  ];
  return base.map((s) => {
    if (isMaint) return { ...s, value:0, is_anomaly:false, anomaly_score:0, last_reading_at:'2026-04-22T06:00:00Z' };
    const ov = overrides[s.sensor_type] || {};
    const value = ov.value !== undefined ? ov.value : s.value;
    const inRange = value >= s.normal_range[0] && value <= s.normal_range[1];
    return { ...s, value, is_anomaly: ov.is_anomaly !== undefined ? ov.is_anomaly : !inRange, anomaly_score: ov.anomaly_score !== undefined ? ov.anomaly_score : (inRange ? 0.05 : 0.6), last_reading_at:'2026-04-28T09:30:00Z' };
  });
}

export const sensorsByMachine = {
  'al-nakheel': makeSensors({
    yankee_vibration_bearing_3: { value:5.8, is_anomaly:true, anomaly_score:0.97 },
    aircap_inlet_temp:          { value:496, is_anomaly:true, anomaly_score:0.71 },
    visconip_felt_moisture:     { value:47.8,is_anomaly:true, anomaly_score:0.58 },
  }),
  'al-bardi': makeSensors({
    yankee_steam_pressure: { value:10.7, is_anomaly:true, anomaly_score:0.62 },
    softreel_tension:      { value:168,  is_anomaly:true, anomaly_score:0.55 },
  }),
  'al-sindian': makeSensors({}, true),
  'al-snobar':  makeSensors({}),
};

function genHistory(sensor, hours = 48) {
  const out = [];
  const now = new Date('2026-04-28T09:30:00Z').getTime();
  const [lo, hi] = sensor.normal_range;
  const mid = (lo + hi) / 2;
  const start = sensor.is_anomaly ? mid : sensor.value;
  for (let i = hours - 1; i >= 0; i--) {
    const t = new Date(now - i * 3600 * 1000);
    const progress = (hours - 1 - i) / (hours - 1);
    const noise = (Math.sin(i * 0.7) + Math.cos(i * 1.3)) * (hi - lo) * 0.04;
    const value = sensor.is_anomaly
      ? start + (sensor.value - start) * Math.pow(progress, 1.6) + noise
      : sensor.value + noise + Math.sin(i * 0.4) * (hi - lo) * 0.05;
    out.push({ timestamp: t.toISOString(), value: Number(value.toFixed(2)) });
  }
  return out;
}

export function getSensorHistory(machineId, sensorType) {
  const sensor = sensorsByMachine[machineId]?.find((s) => s.sensor_type === sensorType);
  if (!sensor) return null;
  return { sensor_type: sensorType, unit: sensor.unit, normal_range: sensor.normal_range, points: genHistory(sensor) };
}

const ALARM_TEMPLATES = [
  { severity:'critical', message:'Bearing 3 vibration trending above warning limit',  component_id:'yankee' },
  { severity:'warning',  message:'PV-2102 deviation > 5%',                              component_id:'yankee' },
  { severity:'warning',  message:'Yankee steam header pressure oscillation',            component_id:'yankee' },
  { severity:'warning',  message:'Bearing 3 temperature trending above warning limit',  component_id:'yankee' },
  { severity:'info',     message:'Yankee surface temp deviation < 2°C',                 component_id:'yankee' },
  { severity:'warning',  message:'ViscoNip felt moisture above target',                 component_id:'visconip' },
  { severity:'warning',  message:'Nip load fluctuation outside band',                   component_id:'visconip' },
  { severity:'info',     message:'Felt life advisory — 22% remaining',                  component_id:'visconip' },
  { severity:'warning',  message:'Hood damper position fault',                          component_id:'aircap' },
  { severity:'warning',  message:'AirCap inlet temp setpoint deviation',                component_id:'aircap' },
  { severity:'info',     message:'Exhaust humidity drift — burner re-tune advised',     component_id:'aircap' },
  { severity:'warning',  message:'Stock consistency setpoint deviation',                component_id:'headbox' },
  { severity:'info',     message:'Headbox jet velocity deviation < 1%',                 component_id:'headbox' },
  { severity:'warning',  message:'QCS scanner CD profile out of band',                  component_id:'rewinder' },
  { severity:'warning',  message:'Reel build-up rate fault',                            component_id:'softreel' },
  { severity:'warning',  message:'Dancer position out of tolerance',                    component_id:'rewinder' },
  { severity:'info',     message:'Drive current spike — single event',                  component_id:'rewinder' },
  { severity:'info',     message:'SoftReel tension trending low',                       component_id:'softreel' },
];

function genAlarms(machineId, count = 32, seed = 0) {
  const out = [];
  const base = new Date('2026-04-28T09:30:00Z').getTime();
  for (let i = 0; i < count; i++) {
    const t = ALARM_TEMPLATES[(i + seed) % ALARM_TEMPLATES.length];
    const minutesAgo = i * 47 + (i * i) % 23 + 5;
    out.push({
      alarm_id: `alm-${machineId}-${String(count - i).padStart(4, '0')}`,
      machine_id: machineId,
      component_id: t.component_id,
      severity: t.severity,
      message: t.message,
      raised_at: new Date(base - minutesAgo * 60 * 1000).toISOString(),
      resolved: i > 4 ? ((i * 7 + seed) % 3 !== 0) : false,
    });
  }
  return out;
}

export const alarmsByMachine = {
  'al-nakheel': genAlarms('al-nakheel', 34, 0),
  'al-bardi':   genAlarms('al-bardi', 31, 3),
  'al-sindian': genAlarms('al-sindian', 30, 7),
  'al-snobar':  genAlarms('al-snobar', 30, 11),
};

export const maintenanceLogByMachine = {
  'al-nakheel': [
    { entry_id:'mnt-aln-0008', date:'2026-03-05', kind:'preventive', component_id:'rewinder', summary:'Replaced rewinder drive belt and tensioner.', cost_usd:4800, technician:'A. Khalil' },
    { entry_id:'mnt-aln-0007', date:'2026-02-14', kind:'preventive', component_id:'headbox',  summary:'Cleaned and inspected headbox slice. No anomalies.', cost_usd:2200, technician:'M. Said' },
    { entry_id:'mnt-aln-0006', date:'2026-01-20', kind:'preventive', component_id:'softreel', summary:'Replaced creping blade. Set angle to 18°.', cost_usd:6400, technician:'A. Khalil' },
    { entry_id:'mnt-aln-0005', date:'2025-12-02', kind:'inspection', component_id:'aircap',   summary:'Infrared scan of hood + burner tuning. Note: bearing 3 watchlist.', cost_usd:1800, technician:'External (Valmet)' },
    { entry_id:'mnt-aln-0004', date:'2025-11-08', kind:'preventive', component_id:'visconip', summary:'Felt change. Old felt at 11% life remaining.', cost_usd:28500, technician:'A. Khalil' },
    { entry_id:'mnt-aln-0003', date:'2025-10-12', kind:'inspection', component_id:'yankee',   summary:'Vibration analysis on Yankee bearings. Bearing 3 baseline 2.4 mm/s.', cost_usd:2400, technician:'External (Valmet)' },
    { entry_id:'mnt-aln-0002', date:'2024-09-12', kind:'corrective', component_id:'yankee',   summary:'Replaced bearings 1 and 2. Bearing 3 left in service per OEM.', cost_usd:11200, technician:'External (Valmet)' },
    { entry_id:'mnt-aln-0001', date:'2024-08-04', kind:'preventive', component_id:'rewinder', summary:'Quarterly drive inspection. Lubrication topped up.', cost_usd:1500, technician:'M. Said' },
  ],
  'al-bardi': [
    { entry_id:'mnt-alb-0009', date:'2026-03-01', kind:'preventive', component_id:'headbox',  summary:'Headbox flush + slice inspection.', cost_usd:2400, technician:'H. Farouk' },
    { entry_id:'mnt-alb-0008', date:'2026-02-18', kind:'preventive', component_id:'rewinder', summary:'Belt and bearing inspection on main drive.', cost_usd:1600, technician:'H. Farouk' },
    { entry_id:'mnt-alb-0007', date:'2025-12-10', kind:'inspection', component_id:'aircap',   summary:'Annual hood inspection. Damper actuators within spec.', cost_usd:1900, technician:'External (Valmet)' },
    { entry_id:'mnt-alb-0006', date:'2025-11-28', kind:'corrective', component_id:'softreel', summary:'Dancer load cell recalibration after drift fault.', cost_usd:3200, technician:'H. Farouk' },
    { entry_id:'mnt-alb-0005', date:'2025-10-22', kind:'preventive', component_id:'visconip', summary:'Felt change. New felt installed and tensioned.', cost_usd:26800, technician:'External (Valmet)' },
    { entry_id:'mnt-alb-0004', date:'2025-09-30', kind:'corrective', component_id:'yankee',   summary:'PRV stiction repair on steam header.', cost_usd:5400, technician:'External (Valmet)' },
    { entry_id:'mnt-alb-0003', date:'2025-08-15', kind:'corrective', component_id:'yankee',   summary:'Replaced bearing 1 after vibration trend exceeded threshold.', cost_usd:12400, technician:'External (Valmet)' },
    { entry_id:'mnt-alb-0002', date:'2025-07-04', kind:'preventive', component_id:'softreel', summary:'Creping blade replacement.', cost_usd:5800, technician:'H. Farouk' },
    { entry_id:'mnt-alb-0001', date:'2025-06-12', kind:'inspection', component_id:'rewinder', summary:'Quarterly inspection. No findings.', cost_usd:1400, technician:'H. Farouk' },
  ],
  'al-sindian': [
    { entry_id:'mnt-als-0010', date:'2026-04-22', kind:'corrective', component_id:'rewinder', summary:'IN PROGRESS — drive current spike investigation. Vibration analysis underway.', cost_usd:0, technician:'External (Valmet)' },
    { entry_id:'mnt-als-0009', date:'2026-04-22', kind:'preventive', component_id:'visconip', summary:'IN PROGRESS — scheduled felt change.', cost_usd:0, technician:'O. Mansour' },
    { entry_id:'mnt-als-0008', date:'2026-02-20', kind:'preventive', component_id:'aircap',   summary:'Burner tuning + damper inspection.', cost_usd:2700, technician:'O. Mansour' },
    { entry_id:'mnt-als-0007', date:'2026-01-10', kind:'preventive', component_id:'headbox',  summary:'Headbox cleaning and gasket replacement.', cost_usd:3100, technician:'O. Mansour' },
    { entry_id:'mnt-als-0006', date:'2025-12-15', kind:'preventive', component_id:'visconip', summary:'Nip load calibration.', cost_usd:1900, technician:'O. Mansour' },
    { entry_id:'mnt-als-0005', date:'2025-11-04', kind:'preventive', component_id:'yankee',   summary:'Steam trap inspection and replacement.', cost_usd:4200, technician:'External (Valmet)' },
    { entry_id:'mnt-als-0004', date:'2025-10-30', kind:'inspection', component_id:'softreel', summary:'Drive bearing thermography scan.', cost_usd:1600, technician:'External (Valmet)' },
    { entry_id:'mnt-als-0003', date:'2025-09-18', kind:'corrective', component_id:'rewinder', summary:'Dancer position sensor replacement.', cost_usd:3400, technician:'O. Mansour' },
    { entry_id:'mnt-als-0002', date:'2025-08-01', kind:'preventive', component_id:'softreel', summary:'Creping blade replacement.', cost_usd:5200, technician:'O. Mansour' },
    { entry_id:'mnt-als-0001', date:'2025-06-22', kind:'inspection', component_id:'yankee',   summary:'Annual Yankee bearing inspection.', cost_usd:2800, technician:'External (Valmet)' },
  ],
  'al-snobar': [
    { entry_id:'mnt-asn-0008', date:'2026-03-22', kind:'preventive', component_id:'headbox',  summary:'Headbox slice cleaning.', cost_usd:1900, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0007', date:'2026-03-10', kind:'preventive', component_id:'rewinder', summary:'Drive inspection. Lubrication topped up.', cost_usd:1300, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0006', date:'2026-02-08', kind:'preventive', component_id:'aircap',   summary:'Burner re-tune and damper actuator check.', cost_usd:2500, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0005', date:'2026-01-15', kind:'preventive', component_id:'softreel', summary:'Creping blade replacement and angle calibration.', cost_usd:5600, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0004', date:'2026-01-05', kind:'preventive', component_id:'visconip', summary:'Felt inspection. Life remaining 38% — schedule swap.', cost_usd:1200, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0003', date:'2025-11-30', kind:'inspection', component_id:'yankee',   summary:'Vibration baseline scan. All bearings within spec.', cost_usd:2100, technician:'External (Valmet)' },
    { entry_id:'mnt-asn-0002', date:'2025-10-18', kind:'preventive', component_id:'rewinder', summary:'Dancer recalibration after seasonal humidity shift.', cost_usd:1800, technician:'R. Haddad' },
    { entry_id:'mnt-asn-0001', date:'2025-09-04', kind:'preventive', component_id:'headbox',  summary:'Stock consistency loop tuning.', cost_usd:1400, technician:'R. Haddad' },
  ],
};

const machinesRunning = machines.filter((m) => m.status === 'running');
const fleetAvgOee = machinesRunning.reduce((s, m) => s + m.current_oee_percent, 0) / Math.max(machinesRunning.length, 1);

export const kpisOverview = {
  fleet_avg_oee_percent: Number(fleetAvgOee.toFixed(1)),
  active_critical_alerts: alerts.filter((a) => a.severity === 'critical' && !a.acknowledged).length,
  active_warning_alerts:  alerts.filter((a) => a.severity === 'warning'  && !a.acknowledged).length,
  predicted_downtime_prevented_hours_mtd: 14,
  estimated_cost_saved_usd_mtd: 280000,
  machines_running: machinesRunning.length,
  machines_total: machines.length,
  last_updated: '2026-04-28T09:30:00Z',
};

export function getCriticalAlerts(limit = 3) {
  return alerts.filter((a) => a.severity === 'critical').sort((a, b) => b.risk_score - a.risk_score).slice(0, limit);
}
export function getMachineById(id) { return machines.find((m) => m.machine_id === id) || null; }
export function getDefaultSensorType(machineId) {
  const sensors = sensorsByMachine[machineId] || [];
  const anomalies = sensors.filter((s) => s.is_anomaly);
  if (anomalies.length > 0) return anomalies.sort((a, b) => b.anomaly_score - a.anomaly_score)[0].sensor_type;
  return 'yankee_surface_temp';
}
// ─── Alerts helpers (Step 4) ────────────────────────────────────────────────
// Pure: operates on whatever list you pass in (filtered or not). Maps an
// alert's severity → risk tier bucket per the contract's counts_by_tier shape.
//   critical severity   → critical
//   warning  severity   → warning
//   info     severity   → watch    (info-level alerts are advisory / watchlist)
// `healthy` is included for shape-completeness; alerts never bucket there.
export function getAlertCounts(list) {
  const counts = { critical: 0, warning: 0, watch: 0, healthy: 0 };
  for (const a of list || []) {
    if (a.severity === 'critical') counts.critical += 1;
    else if (a.severity === 'warning') counts.warning += 1;
    else if (a.severity === 'info') counts.watch += 1;
  }
  return counts;
}