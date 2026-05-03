import { useEffect, useState } from 'react';
import { getMachines } from '../lib/api.js';
import MachineGrid from '../components/MachineGrid.jsx';

export default function MachinesIndex() {
  const [machines, setMachines] = useState({ status: 'loading', data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    getMachines()
      .then((data) => { if (!cancelled) setMachines({ status: 'ok', data, error: null }); })
      .catch((error) => { if (!cancelled) setMachines({ status: 'error', data: null, error }); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="px-8 py-7 max-w-[1200px]">
      <header className="mb-6">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
          Fleet
        </div>
        <h1 className="text-[28px] font-semibold text-navy tracking-tight mt-1">
          Machines
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {machines.status === 'ok'
            ? `${machines.data.length} production lines · sorted by risk`
            : 'Loading production lines…'}
        </p>
      </header>

      {machines.status === 'ok' ? (
        <MachineGrid
          machines={[...machines.data].sort((a, b) => b.risk_score - a.risk_score)}
        />
      ) : machines.status === 'error' ? (
        <div className="rounded-xl bg-red-50 ring-1 ring-red-200 p-4 text-[12px] text-red-800">
          Couldn't load machines. Check the network and refresh.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-[180px] rounded-xl bg-slate-100 animate-pulse" />
          ))}
        </div>
      )}
    </div>
  );
}