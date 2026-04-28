import PagePlaceholder from '../components/PagePlaceholder.jsx';

export default function Alerts() {
  return (
    <PagePlaceholder
      kicker="Operations"
      title="Alerts"
      blueprint={[
        'Filter bar — severity, machine, acknowledged, sort',
        'Counts strip — counts_by_tier chips',
        'Alerts table — severity, machine, component, title, predicted window, est. cost',
        'Detail drawer — full description, top contributing sensors, acknowledge action',
      ]}
      endpoints={[
        'GET /alerts?sort=severity',
        'GET /alerts/{alert_id}',
      ]}
    />
  );
}
