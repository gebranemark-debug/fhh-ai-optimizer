import PagePlaceholder from '../components/PagePlaceholder.jsx';

export default function DemandForecast() {
  return (
    <PagePlaceholder
      kicker="Predictive"
      title="Demand Forecast"
      blueprint={[
        'Filter bar — SKU, market, horizon (1–12 months)',
        'Main chart — Recharts area chart with confidence band + seasonality reference lines',
        'Side panel — yearly seasonality bar chart + event lift table',
        'Scenario planner — type, event, magnitude → POST /forecast/scenario, dashed overlay',
        'Demand anomalies card — recent spikes / dips / trend breaks',
      ]}
      endpoints={[
        'GET /products',
        'GET /markets',
        'GET /forecast?sku=...&market=...&horizon_months=...',
        'GET /demand/seasonality?sku=...',
        'POST /forecast/scenario',
        'GET /demand/anomalies',
      ]}
    />
  );
}
