import PagePlaceholder from '../components/PagePlaceholder.jsx';

export default function NotFound() {
  return (
    <PagePlaceholder
      kicker="404"
      title="Page not found"
      blueprint={[
        'The route you requested does not exist in the FHH AI Optimizer.',
        'Use the left rail to navigate to one of the five primary sections.',
      ]}
      endpoints={[]}
    />
  );
}
