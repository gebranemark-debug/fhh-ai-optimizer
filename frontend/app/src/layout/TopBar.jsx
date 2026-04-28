import { useLocation, Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

const LABELS = {
  '/': 'Overview',
  '/machines': 'Machines',
  '/alerts': 'Alerts',
  '/demand': 'Demand Forecast',
  '/roi': 'Cost Savings',
};

function buildCrumbs(pathname) {
  if (pathname === '/' || pathname === '') {
    return [{ label: 'Overview', to: '/' }];
  }
  const parts = pathname.split('/').filter(Boolean);
  const crumbs = [{ label: 'Overview', to: '/' }];
  let acc = '';
  parts.forEach((p, i) => {
    acc += '/' + p;
    const isLast = i === parts.length - 1;
    const known = LABELS[acc];
    let label;
    if (known) label = known;
    else if (parts[0] === 'machines' && i === 1) label = decodeURIComponent(p);
    else label = p;
    crumbs.push({ label, to: isLast ? null : acc });
  });
  return crumbs;
}

export default function TopBar() {
  const { pathname } = useLocation();
  const crumbs = buildCrumbs(pathname);

  return (
    <header className="h-[60px] shrink-0 bg-white border-b border-slate-200 flex items-center px-6 gap-6">
      {/* Logo */}
      <Link to="/" className="flex items-center gap-2 select-none">
        <div className="w-7 h-7 rounded-md bg-navy flex items-center justify-center">
          <span className="font-mono text-[11px] font-semibold text-gold tracking-tight">FHH</span>
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold text-navy tracking-tight">FHH AI Optimizer</div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-medium">Predictive Operations</div>
        </div>
      </Link>

      {/* Breadcrumb */}
      <nav className="flex-1 flex items-center justify-center">
        <ol className="flex items-center gap-1.5 text-sm">
          {crumbs.map((c, i) => (
            <li key={i} className="flex items-center gap-1.5">
              {i > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-300" />}
              {c.to ? (
                <Link to={c.to} className="text-slate-500 hover:text-navy transition-colors">
                  {c.label}
                </Link>
              ) : (
                <span className="text-navy font-medium">{c.label}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>

      {/* Right cluster */}
      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 text-xs text-slate-500">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span>Live</span>
        </div>
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-navy to-navy-800 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-white shadow-card">
          MA
        </div>
      </div>
    </header>
  );
}
