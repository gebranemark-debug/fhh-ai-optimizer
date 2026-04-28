# Phase 3 — Claude Design Launch Prompt

**How to use:** open a fresh Claude Design session. Upload `API_CONTRACT.md` as the only attached file. Then paste everything below the line.

---

I'm building the frontend dashboard for the **FHH AI Optimizer** — a predictive maintenance + demand forecasting tool for Fine Hygienic Holding's 4 Valmet Advantage DCT 200TS tissue manufacturing lines (Al Nakheel UAE, Al Bardi Egypt, Al Sindian Egypt, Al Snobar Jordan).

The attached `API_CONTRACT.md` is the **locked source of truth**. Every UI element you build must consume one of these endpoints. Use the constants (machine IDs, component IDs, sensor types, risk tiers, severities, markets) **verbatim**. Do not invent your own. Do not rename fields. Do not change casing.

## Stack

- **React + Vite + TailwindCSS** (no Next.js, no SSR — this is a static SPA we'll deploy on GitHub Pages)
- **React Router** for client-side routing
- **Recharts** for line charts, area charts, and bar charts
- **lucide-react** for icons
- No state management library — `useState` + `useContext` is enough

## Global layout (persistent on every page)

- **Top bar (60px):** FHH text logo on the left ("FHH AI Optimizer" — text only, no image), breadcrumb in the center, placeholder user avatar on the right
- **Left nav rail (220px):** vertical nav with 5 items + icons. Active item highlighted with the gold accent color
  - Overview (LayoutDashboard icon)
  - Machines (Factory icon)
  - Alerts (Bell icon)
  - Demand Forecast (TrendingUp icon)
  - Cost Savings / ROI (DollarSign icon)
- **Main content area:** ~52% of screen width, the page-specific content
- **Chat sidebar (right, ~28% width):** ALWAYS visible on every page. Detailed spec below.

## Brand & visual system

- **Primary navy:** `#0A2540`
- **Gold accent:** `#D4AF37`
- **Risk tier colors (use these exact hex values, never deviate):**
  - `healthy` → `#10B981` (emerald)
  - `watch` → `#F59E0B` (amber)
  - `warning` → `#F97316` (orange)
  - `critical` → `#EF4444` (red)
- **Severity colors** (alarms, alerts):
  - `info` → blue `#3B82F6`
  - `warning` → orange `#F97316`
  - `critical` → red `#EF4444`
- Background: `#F8FAFC`. Cards on pure white with `shadow-sm`, `rounded-xl`, no harsh borders.
- Typography: **Inter** for UI text, **JetBrains Mono** for numeric values (sensor readings, risk scores, dollar amounts) — gives the dashboard a "trading terminal" feel.
- Spacing: 24px base unit. Cards have `p-6` (24px) padding, sections separated by `gap-6`.

## Page specs

### 1. Overview page (`/`)

- **Top KPI strip:** 4 cards reading from `GET /kpis/overview`
  - Fleet Avg OEE % (large number, % suffix)
  - Active Critical Alerts (red number, "Action required" sublabel if > 0)
  - Downtime Hours Prevented MTD (with small trend indicator)
  - Cost Saved MTD (formatted as `$280K`, with subtle gold accent)
- **Machine grid:** 4 machine cards in a 2x2 responsive grid (`GET /machines`). Each card:
  - Machine name (h3) + location (small gray)
  - Risk score as a large number (JetBrains Mono, 48px)
  - Risk tier as a colored pill chip
  - Status badge (running / idle / maintenance / offline)
  - Current speed in m/min, current OEE %
  - "View details →" link bottom-right that routes to `/machines/{machine_id}`
  - Border-left in the tier color (4px)
- **Critical alerts ticker:** below the grid, full-width card from `GET /alerts?severity=critical&limit=3`. Shows up to 3 most critical alerts with severity chip, machine name, alert title, time ago, and a small "View" button.

### 2. Machine detail page (`/machines/:machine_id`)

- **Header strip:** machine name (h1), location, status badge, current speed, current OEE %, last_updated timestamp
- **Component health row:** horizontal scrollable row of 6 component cards from `GET /machines/{id}/components`. Each card: component name, risk score (large), tier chip, "is_critical" gold star badge if applicable. Yankee always shown in second-to-third position with `is_critical: true`.
- **Predictions section:** grid of cards from `GET /machines/{id}/predictions`. Each card: component name, failure probability % (large), predicted failure window in hours, confidence %, recommended action (italic, smaller font). Color-coded border by tier.
- **Live sensors grid:** 14 sensor cells from `GET /machines/{id}/sensors`, organized in a responsive grid (4 columns on desktop). Each cell:
  - Sensor type (uppercased, monospace)
  - Current value (large, JetBrains Mono)
  - Unit (small)
  - Normal range (very small gray)
  - Red dot icon if `is_anomaly: true`
  - Click → opens drawer with history chart
- **Sensor history drawer:** opens on cell click. Pulls `GET /machines/{id}/sensors/{sensor_type}/history?window=24h&aggregation=hourly`. Renders a Recharts line chart with shaded normal-range band. Window selector chips: 1h / 24h / 7d / 30d.
- **Recent alarms table:** from `GET /machines/{id}/alarms?limit=10`. Columns: timestamp, severity chip, description, downtime minutes, resolved status.
- **Maintenance log:** from `GET /machines/{id}/maintenance-log`. Columns: date, component, type chip, cost, downtime hours, technician, notes.

### 3. Alerts page (`/alerts`)

- **Filter bar:** severity dropdown, machine dropdown, "Acknowledged" toggle, sort dropdown (severity / created_at / risk_score)
- **Counts strip:** small chips showing counts_by_tier (critical: N, warning: N, watch: N)
- **Alerts table:** from `GET /alerts?sort=severity`. Columns: severity chip, machine, component, title, predicted_failure_window_hours, estimated_cost_if_unaddressed_usd (formatted), created_at relative time, acknowledged checkmark.
- **Detail drawer** on row click: pulls `GET /alerts/{alert_id}`, shows full description, top contributing sensors, recommended action, and "Acknowledge" button (UI only — no backend mutation in this round).

### 4. Demand forecast page (`/demand`)

- **Filter bar:** SKU dropdown (`GET /products`), market dropdown (`GET /markets`), horizon slider 1-12 months
- **Main chart:** Recharts area chart from `GET /forecast?sku=...&market=...&horizon_months=...`. Shows forecast line with shaded confidence band (lower_bound to upper_bound). Vertical reference lines on `seasonality_events` dates with labels.
- **Regressors used:** small chip row showing which regressors the model used.
- **Side panel:** seasonality breakdown from `GET /demand/seasonality?sku=...`. Mini bar chart for the 12-month yearly_pattern, plus event lift table.
- **Scenario planner card:** below the main chart.
  - Scenario type selector (radio buttons): seasonality_shift / price_change / competitor_entry / supply_disruption
  - Event dropdown (when type is seasonality_shift): ramadan / eid_al_fitr / back_to_school
  - Magnitude slider (-50% to +50%)
  - "Run scenario" button → calls `POST /forecast/scenario`
  - Result: overlays scenario_forecast as a dashed line on the main chart, plus a delta summary card showing baseline units, scenario units, delta units, delta %.
- **Demand anomalies card:** from `GET /demand/anomalies`. Compact list of recent anomalies with type chip (spike/dip/trend_break), magnitude %, explanation.

### 5. Cost Savings / ROI page (`/roi`)

- **Window selector:** MTD / QTD / YTD / All-time tabs
- **Hero number:** total cost saved (very large, gold, JetBrains Mono, $ formatted) from `GET /kpis/cost-savings`
- **Stat row below hero:** total_predictions, predictions_acted_on (with success rate %), estimated_downtime_hours_prevented
- **Per-machine breakdown:** horizontal bar chart from `breakdown_by_machine`. Each bar in the machine's risk-tier color or a neutral navy.

## Chat sidebar spec (right rail, every page)

This is the always-visible right column. Width: ~28% of screen on desktop, collapsible to icon-only on screens <1280px.

- **Header:** "Assistant" title + "New chat" button (icon + text). New chat triggers `DELETE /chat/conversations/{id}` if a conversation exists, then resets state.
- **Empty state (no conversation yet):**
  - Friendly welcome line: "Hi! I can read your live sensor data, machine health, and forecasts. Ask me anything."
  - 4 suggested prompt chips from `GET /chat/suggested-prompts?current_page=...&current_machine_id=...&current_sku=...`. Click a chip → fills the input AND auto-submits.
- **Conversation state:**
  - Scrollable message list. User bubbles right-aligned in navy, assistant bubbles left-aligned in light gray.
  - Each assistant message shows below the text:
    - "Sources" line: comma-separated `data_sources_used` endpoints in small gray monospace
    - 2-3 followup chips from `suggested_followups` — clicking submits as a new user message
  - Loading state: 3-dot typing indicator while waiting for response
- **Input:** text field at the bottom with send button. Pressing Enter submits. On submit:
  - Call `POST /chat` with `{ message, conversation_id (if exists), context: { current_page, current_machine_id, current_sku, current_market } }`
  - Pull `current_page` from React Router location, `current_machine_id` from URL params, `current_sku` and `current_market` from page state when on `/demand`
  - On 200, append assistant reply to the message list. Save the returned `conversation_id` if it was a new conversation.
  - On 429 (`rate_limited`): show "Slow down a moment" inline error
  - On 503 (`chat_unavailable` / `model_unavailable`): show "Assistant is temporarily unavailable" error with retry button
- **Streaming support:** if implementing, use `fetch` with `Accept: text/event-stream`. Render tokens incrementally. Optional — non-streaming is fine for the demo.
- **Resume conversation:** on mount, if a `conversation_id` is in localStorage, call `GET /chat/conversations/{id}` to rehydrate the message list.

## What NOT to do in this round

**Do not write the fetch() calls yet.** Use mock data inline (a single `mockData.js` file) that matches every API contract response shape exactly. I will review the visuals first; once approved, we'll wire fetch() to the FastAPI backend at `http://localhost:8000` in a follow-up prompt.

## Mock data requirements

Create `src/mockData.js` with realistic FHH data:

- **4 machines** at different risk levels — one **critical** (Al Nakheel, risk 87, Yankee bearing 3 issue), one **warning** (Al Bardi, risk 67), one **watch** (Al Sindian, risk 42), one **healthy** (Al Snobar, risk 18)
- **24 components total** (4 × 6) with varied risk scores and realistic maintenance dates
- **At least 8 alerts** spanning all severities, with realistic FHH-flavored descriptions
- **At least 30 alarms per machine** with realistic Valmet DCS terminology
- **All 14 sensor types per machine** with current values, some inside normal range and some flagged as anomalies on the critical machine
- **24 hours of hourly sensor history** per sensor for charting
- **At least 12 SKUs** across categories: tissue, baby_care, adult_care, fine_guard, wellness, cosmetics. Use realistic Fine product names (e.g. `fine-facial-100`, `fine-toilet-mega`, `fine-baby-s3`)
- **All 5 markets**
- **6 months of historical forecast points + 6 months of forward forecast** for at least one SKU × market combo
- **Realistic seasonality:** include Ramadan and Eid lifts in the seasonality data
- **An empty conversation state** for the chat (one mock conversation exists with 2 user + 2 assistant messages for visual reference)

## Deliverables

- Full React + Vite project, ready to `npm run dev`
- All 5 pages + persistent chat sidebar working with mock data
- `src/mockData.js` with all required mock content
- `README.md` with run instructions
- **Save all files to disk. Do not stream full file contents back to chat.** Confirm each file is saved before moving to the next.

## Workflow

1. First, build the layout shell, brand system, and routing skeleton. Show me a screenshot.
2. Then build the Overview page. Show me a screenshot.
3. Then Machine detail. Screenshot.
4. Then Alerts, Demand, ROI in that order.
5. Last: the chat sidebar wired to mock conversation data.
6. Final review pass — confirm every UI element references the contract correctly.

Let's start with step 1: layout shell + brand system + routing. Confirm you've read the API contract and tell me what stack components you'll install before writing code.
