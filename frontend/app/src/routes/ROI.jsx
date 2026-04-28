import PagePlaceholder from '../components/PagePlaceholder.jsx';

export default function ROI() {
  return (
    <PagePlaceholder
      kicker="Business impact"
      title="Cost Savings / ROI"
      blueprint={[
        'Window selector tabs — MTD / QTD / YTD / All-time',
        'Hero number — total cost saved, gold, JetBrains Mono',
        'Stat row — total predictions, predictions acted on, downtime hours prevented',
        'Per-machine breakdown — horizontal bar chart by machine',
      ]}
      endpoints={['GET /kpis/cost-savings?window=ytd']}
    />
  );
}
