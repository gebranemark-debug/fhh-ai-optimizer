import PagePlaceholder from '../components/PagePlaceholder.jsx';

export default function MachinesIndex() {
  return (
    <PagePlaceholder
      kicker="Fleet"
      title="Machines"
      blueprint={[
        'Full list of all 4 machines with health summary',
        'Click a machine to drill into its detail page',
        'Reuses the same machine card style as Overview, in a denser list layout',
      ]}
      endpoints={['GET /machines']}
    />
  );
}
