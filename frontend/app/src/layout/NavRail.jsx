import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Factory, Bell, TrendingUp, DollarSign } from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/machines', label: 'Machines', icon: Factory },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/demand', label: 'Demand Forecast', icon: TrendingUp },
  { to: '/roi', label: 'Cost Savings', icon: DollarSign },
];

export default function NavRail() {
  return (
    <aside className="w-[220px] shrink-0 bg-white border-r border-slate-200 flex flex-col">
      <nav className="flex-1 px-3 py-5">
        <div className="px-3 pb-2 text-[10px] uppercase tracking-[0.16em] text-slate-400 font-semibold">
          Workspace
        </div>
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  [
                    'group relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                    isActive
                      ? 'bg-navy text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-navy',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-gold" />
                    )}
                    <Icon
                      className={`w-[18px] h-[18px] ${
                        isActive ? 'text-gold' : 'text-slate-400 group-hover:text-navy'
                      }`}
                      strokeWidth={isActive ? 2.25 : 1.75}
                    />
                    <span className="font-medium">{label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer block */}
      <div className="px-4 py-4 border-t border-slate-100">
        <div className="rounded-lg bg-canvas border border-slate-200 p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
            Fleet
          </div>
          <div className="font-mono text-sm text-navy">3 / 4 running</div>
          <div className="text-[11px] text-slate-500 mt-0.5">1 in maintenance</div>
        </div>
        <div className="mt-3 px-1 text-[10px] text-slate-400 font-mono">
          v0.1 · API contract v1.1
        </div>
      </div>
    </aside>
  );
}
