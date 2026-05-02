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
  // GET /machines/{id}/components → { machine_id, components: [...] }. Return just the array.
  const result = await _fetch(`/machines/${machineId}/components`);
  return result.components;
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

export async function getSensors(machineId) {
  // GET /machines/{id}/sensors → { machine_id, readings: [...] }. Return the readings
  // array (mockData calls this collection "sensors" — same shape per row).
  const result = await _fetch(`/machines/${machineId}/sensors`);
  return result.readings;
}

export async function getSensorHistory(machineId, sensorType) {
  // GET /machines/{id}/sensors/{type}/history → { machine_id, sensor_type, unit,
  //   window, aggregation, normal_range, points: [...] }.
  // Return the FULL object — the chart needs unit + normal_range alongside the
  // points array for rendering, matching what mockData's getSensorHistory provides.
  return _fetch(`/machines/${machineId}/sensors/${sensorType}/history`);
}

export async function getAlarms(machineId) {
  // GET /machines/{id}/alarms → { machine_id, alarms: [...], total }. Return just the array.
  const result = await _fetch(`/machines/${machineId}/alarms`);
  return result.alarms;
}

export async function getMaintenanceLog(machineId) {
  // GET /machines/{id}/maintenance-log → { machine_id, logs: [...] }. Return just the array.
  const result = await _fetch(`/machines/${machineId}/maintenance-log`);
  return result.logs;
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

export async function getCostSavings() {
  // GET /kpis/cost-savings → flat object (window, total_predictions, ...
  // estimated_cost_saved_usd, breakdown_by_machine[]). No unwrapping.
  return _fetch('/kpis/cost-savings');
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
