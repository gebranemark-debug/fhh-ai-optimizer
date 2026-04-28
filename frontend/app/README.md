# FHH AI Optimizer — Frontend

Predictive maintenance + demand forecasting dashboard for Fine Hygienic Holding's 4 Valmet Advantage DCT 200TS tissue lines (Al Nakheel, Al Bardi, Al Sindian, Al Snobar).

This is the React + Vite + TailwindCSS SPA that consumes the API defined in `API_CONTRACT.md` (v1.1). Deploys as a static bundle (target: GitHub Pages).

## Stack

- React 18 + Vite 5
- TailwindCSS 3
- React Router v6
- Recharts (charts)
- lucide-react (icons)
- Inter (UI) + JetBrains Mono (numerics) loaded from Google Fonts

No state library — `useState` + `useContext` only.

## Run locally

```bash
npm install
npm run dev
```

Then open http://localhost:5173.

## Build

```bash
npm run build
npm run preview
```

## Project structure

```
src/
  main.jsx                    # React + Router bootstrap
  App.jsx                     # Route table
  index.css                   # Tailwind + global styles
  brand/
    tokens.js                 # Brand colors, risk-tier hex, severity hex (single source)
  layout/
    AppShell.jsx              # 60px topbar + 220px nav + main + 28% chat sidebar
    TopBar.jsx                # Logo, breadcrumb, avatar
    NavRail.jsx               # 5-item vertical nav with gold active accent
    ChatSidebar.jsx           # Persistent right rail (full chat wired in Step 6)
  routes/
    Overview.jsx              # /
    MachinesIndex.jsx         # /machines
    MachineDetail.jsx         # /machines/:machine_id
    Alerts.jsx                # /alerts
    DemandForecast.jsx        # /demand
    ROI.jsx                   # /roi
    NotFound.jsx
  components/
    PagePlaceholder.jsx       # Step 1 placeholder shared across routes
  mockData.js                 # Empty in Step 1; populated in Step 2
```

## Build status (phased)

- [x] **Step 1** — Layout shell, brand system, routing skeleton
- [ ] Step 2 — Overview page + mock data
- [ ] Step 3 — Machine detail page
- [ ] Step 4 — Alerts, Demand, ROI pages
- [ ] Step 5 — Chat sidebar wired to mock conversation
- [ ] Step 6 — Backend wiring (replace mocks with `fetch` to `http://localhost:8000`)

## Brand tokens

All risk-tier and severity hex values live in `src/brand/tokens.js` and are also wired into Tailwind (`tailwind.config.js`). Never hand-roll a new color — import from tokens or use the `risk-*` / `severity-*` Tailwind classes so charts and pills stay in sync.

## API contract

The locked spec lives at the project root as `API_CONTRACT.md`. Every UI surface consumes one of the documented endpoints; constants (machine IDs, component IDs, sensor types, tier names) are used verbatim with no renames.
