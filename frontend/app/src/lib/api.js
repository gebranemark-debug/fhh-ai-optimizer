/**
 * @file Centralized backend API client for the FHH AI Optimizer dashboard.
 *
 * This is the boundary between the React UI and the FastAPI backend at
 * Railway. Every fetch site in the app should call helpers from this
 * file rather than build URLs / parse responses inline. Sunday's
 * frontend wiring is a near-mechanical replacement of mockData
 * imports for these helpers — they return the **unwrapped** shape
 * mockData currently provides (e.g. `getMachines()` returns the array
 * of 4 machines, not `{machines: [...], total}`), so callers don't
 * have to change their access patterns.
 *
 * Base URL resolution:
 *   - In production (Vercel) `import.meta.env.VITE_API_URL` is set in
 *     the project's Settings → Environment Variables to the Railway URL
 *     (https://fhh-ai-optimizer-production.up.railway.app).
 *   - For local dev, copy `frontend/app/.env.example` → `.env` and
 *     leave VITE_API_URL pointing at http://127.0.0.1:8000.
 *   - When VITE_API_URL is unset entirely we fall back to localhost so
 *     `npm run dev` works out of the box.
 *
 * Endpoint specifications: see `docs/API_CONTRACT-2.md` v1.1 for the
 * full contract. Each helper below documents its raw backend response
 * shape in a comment so the unwrap step stays auditable.
 */

const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

// ---------------------------------------------------------------------------
// HTTP layer — three private helpers covering GET / POST / DELETE. Errors
// from non-2xx responses bubble up as plain Error objects with the status
// code in the message so component error boundaries can render something
// sensible.
// ---------------------------------------------------------------------------

async function _fetch(path) {
  const response = await fetch(`${API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API ${response.status} on GET ${path}`);
  }
  return response.json();
}

async function _fetchPost(path, body) {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`API ${response.status} on POST ${path}`);
  }
  return response.json();
}

async function _fetchDelete(path) {
  const response = await fetch(`${API_URL}${path}`, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(`API ${response.status} on DELETE ${path}`);
  }
  // 204 No Content has no body — guard against JSON parse on empty.
  if (response.status === 204) return null;
  return response.json();
}

// ---------------------------------------------------------------------------
// Module 1 — Maintenance
// ---------------------------------------------------------------------------

export async function getMachines() {
  // GET /machines → { machines: [...], total }. Return just the array.
  const result = await _fetch('/machines');
  return result.machines;
}

export async function getMachine(machineId) {
  // GET /machines/{id} → Machine object directly.
  return _fetch(`/machines/${machineId}`);
}

export async function getRiskScore(machineId) {
  // GET /machines/{id}/risk-score → { score, tier, highest_risk_component_id, last_updated, ... }
  return _fetch(`/machines/${machineId}/risk-score`);
}

export async function getComponents(machineId) {
  // GET /machines/{id}/components → {machine_id, components: [...]} where each
  //   entry is {component_id, machine_id, name, is_critical, risk_score,
  //   risk_tier, expected_lifetime_hours, hours_since_last_maintenance,
  //   last_maintenance_date}.
  // ComponentHealthRow expects mockData-shape:
  //   {component_id, health_score, tier, last_service_date}.
  // Adapt the field names AND invert risk→health (Railway's risk_score: 9
  // means "low risk", which mockData represented as health_score: 91).
  const result = await _fetch(`/machines/${machineId}/components`);
  return (result.components || []).map((c) => ({
    component_id: c.component_id,
    health_score: typeof c.risk_score === 'number' ? 100 - c.risk_score : null,
    tier: c.risk_tier,
    last_service_date: c.last_maintenance_date,
    // Pass through the extra fields in case other code paths consume them.
    name: c.name,
    is_critical: c.is_critical,
    expected_lifetime_hours: c.expected_lifetime_hours,
    hours_since_last_maintenance: c.hours_since_last_maintenance,
  }));
}

export async function getComponentRiskScore(machineId, componentId) {
  // GET /machines/{id}/components/{cid}/risk-score → object with score, tier,
  // predicted_failure_window_hours, top_contributing_sensors[], last_updated.
  return _fetch(`/machines/${machineId}/components/${componentId}/risk-score`);
}

export async function getPredictions(machineId) {
  // GET /machines/{id}/predictions → { machine_id, predictions: [...], generated_at }.
  // Return just the predictions array.
  const result = await _fetch(`/machines/${machineId}/predictions`);
  return result.predictions;
}

// Static normal-range lookup. The backend's sensor reading objects don't
// include normal_range per the API contract, but the SensorGrid + chart
// components expect it. Values come from API_CONTRACT.md §"Sensor types".
// When we eventually move to a richer reading payload these can be deleted.
const SENSOR_NORMAL_RANGES = {
  yankee_surface_temp:        [100, 120],
  yankee_steam_pressure:      [8, 10],
  yankee_vibration_bearing_1: [2, 4],
  yankee_vibration_bearing_2: [2, 4],
  yankee_vibration_bearing_3: [2, 4],
  yankee_blade_pressure:      [80, 120],
  visconip_nip_pressure:      [4, 6],
  visconip_nip_load:          [85, 110],
  visconip_felt_moisture:     [35, 45],
  aircap_inlet_temp:          [480, 520],
  aircap_exhaust_humidity:    [32, 42],
  aircap_energy:              [1.8, 2.4],
  headbox_stock_temp:         [45, 55],
  headbox_stock_consistency:  [0.28, 0.34],
  headbox_jet_velocity:       [23.0, 27.0],
  softreel_tension:           [180, 220],
  softreel_drive_current:     [130, 160],
  rewinder_speed:             [1800, 2222],
  rewinder_drive_current:     [75, 105],
  rewinder_dancer_position:   [18, 32],
  qcs_softness_index:         [70, 90],
  qcs_basis_weight_cd_stddev: [0.4, 1.2],
};

export async function getSensors(machineId) {
  // GET /machines/{id}/sensors → { machine_id, readings: [...] }. Return the
  // readings array, enriched with normal_range from the contract spec — the
  // backend doesn't include normal_range per-reading but the UI needs it for
  // the "X–Y unit" label and for in-range visual logic.
  const result = await _fetch(`/machines/${machineId}/sensors`);
  return result.readings.map((reading) => ({
    ...reading,
    normal_range: SENSOR_NORMAL_RANGES[reading.sensor_type] || [0, 0],
  }));
}

export async function getSensorHistory(machineId, sensorType) {
  // GET /machines/{id}/sensors/{type}/history → {machine_id, sensor_type, unit,
  //   window, aggregation, normal_range: {min, max}, points: [{timestamp, value, min, max}]}.
  // SensorHistoryChart expects mockData-shape:
  //   {sensor_type, unit, normal_range: [lo, hi], points: [{timestamp, value}]}.
  // Adapt the object→array for normal_range, and drop per-point CI fields the
  // chart doesn't render.
  const result = await _fetch(`/machines/${machineId}/sensors/${sensorType}/history`);
  const range = result.normal_range || {};
  const lo = typeof range.min === 'number' ? range.min : (SENSOR_NORMAL_RANGES[sensorType] || [0, 0])[0];
  const hi = typeof range.max === 'number' ? range.max : (SENSOR_NORMAL_RANGES[sensorType] || [0, 0])[1];
  return {
    sensor_type: result.sensor_type,
    unit: result.unit,
    normal_range: [lo, hi],
    points: (result.points || []).map((p) => ({
      timestamp: p.timestamp,
      value: p.value,
    })),
  };
}

export async function getAlarms(machineId) {
  // GET /machines/{id}/alarms → {machine_id, alarms: [...]} where each entry is
  //   {alarm_id, timestamp, severity, description, resolved_at, downtime_minutes}.
  // AlarmsTable component (built against mockData) expects
  //   {alarm_id, machine_id, component_id, severity, message, raised_at, resolved}.
  // Adapt to that shape so the renderer works without changes.
  const result = await _fetch(`/machines/${machineId}/alarms`);
  return (result.alarms || []).map((a) => ({
    alarm_id: a.alarm_id,
    machine_id: machineId,
    component_id: a.component_id || null,
    severity: a.severity,
    message: a.description,
    raised_at: a.timestamp,
    resolved: a.resolved_at !== null && a.resolved_at !== undefined,
    resolved_at: a.resolved_at,
    downtime_minutes: a.downtime_minutes,
  }));
}

export async function getMaintenanceLog(machineId) {
  // GET /machines/{id}/maintenance-log → {machine_id, logs: [...]} where each
  //   log is {log_id, component_id, maintenance_type, date_performed, cost_usd,
  //   downtime_hours, technician, notes}.
  // MaintenanceLog component expects mockData-shape
  //   {entry_id, date, kind, component_id, summary, cost_usd, technician}.
  const result = await _fetch(`/machines/${machineId}/maintenance-log`);
  return (result.logs || []).map((l) => ({
    entry_id: l.log_id,
    date: l.date_performed,
    kind: l.maintenance_type,
    component_id: l.component_id,
    summary: l.notes,
    cost_usd: l.cost_usd,
    technician: l.technician,
    downtime_hours: l.downtime_hours,
  }));
}

export async function getAlerts() {
  // GET /alerts → { alerts: [...], total, counts_by_tier }. Return just the array;
  // the existing getAlertCounts(list) helper in mockData recomputes counts.
  const result = await _fetch('/alerts');
  return result.alerts;
}

export async function getAlert(alertId) {
  // GET /alerts/{id} → Alert object directly.
  return _fetch(`/alerts/${alertId}`);
}

// ---------------------------------------------------------------------------
// Cross-cutting KPIs
// ---------------------------------------------------------------------------

export async function getKpisOverview() {
  // GET /kpis/overview → flat object (fleet_avg_oee_percent, active_*_alerts,
  // machines_running, machines_total, last_updated, etc.). No unwrapping.
  return _fetch('/kpis/overview');
}

export async function getCostSavings(window = 'mtd') {
  // GET /kpis/cost-savings?window=mtd|qtd|ytd|all → flat object
  // (window, total_predictions, ..., estimated_cost_saved_usd,
  // breakdown_by_machine[]). Default window=mtd matches the Overview KPI tile.
  const params = new URLSearchParams({ window });
  return _fetch(`/kpis/cost-savings?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Module 2 — Demand forecasting
// ---------------------------------------------------------------------------

export async function getProducts() {
  // GET /products → { products: [...], total }. Return just the array.
  const result = await _fetch('/products');
  return result.products;
}

export async function getMarkets() {
  // GET /markets → { markets: [...] }. Return just the array.
  const result = await _fetch('/markets');
  return result.markets;
}

export async function getForecast(sku, market, horizonMonths = 6) {
  // GET /forecast?sku=...&market=...&horizon_months=N →
  //   { sku, market, horizon_months, model, forecast: [...], seasonality_events,
  //     regressors_used, generated_at }.
  // Returned as-is — the chart needs forecast[] alongside seasonality_events.
  const params = new URLSearchParams({
    sku,
    market,
    horizon_months: String(horizonMonths),
  });
  return _fetch(`/forecast?${params.toString()}`);
}

export async function getForecastScenario(sku, market, horizonMonths, scenario) {
  // POST /forecast/scenario  body { sku, market, horizon_months, scenario }
  // → { baseline_forecast, scenario_forecast, delta_summary }.
  return _fetchPost('/forecast/scenario', {
    sku,
    market,
    horizon_months: horizonMonths,
    scenario,
  });
}

export async function getDemandAnomalies(sku, market) {
  // GET /demand/anomalies → { anomalies: [...] }. The backend currently ignores
  // sku / market query params (returns the global anomaly list); the params are
  // sent anyway for forward-compatibility when filtering lands.
  const params = new URLSearchParams();
  if (sku) params.set('sku', sku);
  if (market) params.set('market', market);
  const qs = params.toString() ? `?${params.toString()}` : '';
  const result = await _fetch(`/demand/anomalies${qs}`);
  return result.anomalies;
}

export async function getDemandSeasonality(sku, market) {
  // GET /demand/seasonality?sku=...&market=... → { sku, market, yearly_pattern: [...],
  // events: [...] }. Returned as-is — the page renders both the index curve
  // and the events list.
  const params = new URLSearchParams({ sku });
  if (market) params.set('market', market);
  return _fetch(`/demand/seasonality?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Module 3 — Chat assistant
// ---------------------------------------------------------------------------

export async function postChat(message, conversationId = null) {
  // POST /chat  body { message, conversation_id? }
  // → { conversation_id, reply, data_sources_used, suggested_followups, timestamp }.
  const body = { message };
  if (conversationId) body.conversation_id = conversationId;
  return _fetchPost('/chat', body);
}

export async function getChatConversation(conversationId) {
  // GET /chat/conversations/{id} → { conversation_id, created_at, messages: [...] }.
  return _fetch(`/chat/conversations/${conversationId}`);
}

export async function deleteChatConversation(conversationId) {
  // DELETE /chat/conversations/{id} → 204 No Content (returns null here).
  return _fetchDelete(`/chat/conversations/${conversationId}`);
}

export async function getSuggestedPrompts() {
  // GET /chat/suggested-prompts → { prompts: [...] }. Returned as-is so the
  // sidebar can render it directly.
  return _fetch('/chat/suggested-prompts');
}

// ---------------------------------------------------------------------------
// Health / liveness
// ---------------------------------------------------------------------------

export async function getHealth() {
  // GET /health → { status, service, version, uptime_seconds, timestamp }.
  return _fetch('/health');
}
