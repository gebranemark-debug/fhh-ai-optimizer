// Reusable placeholder shown for routes whose real content lands in later steps.
// Mirrors the visual language we'll reuse — same card chrome, same type scale —
// so Step 1 already conveys the design system.
export default function PagePlaceholder({ title, kicker, blueprint, endpoints }) {
  return (
    <div className="p-8 max-w-[1100px]">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400 font-semibold">
        {kicker}
      </div>
      <h1 className="text-[28px] font-semibold text-navy tracking-tight mt-1">{title}</h1>
      <p className="text-sm text-slate-500 mt-1.5">
        Layout shell only. Mock data and full page composition land in the next steps.
      </p>

      <div className="mt-7 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="lg:col-span-2 bg-white rounded-xl shadow-card p-6">
          <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold mb-3">
            Blueprint
          </div>
          <ul className="space-y-2.5">
            {blueprint.map((b, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-slate-700">
                <span className="mt-[7px] w-1.5 h-1.5 rounded-full bg-gold shrink-0" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-white rounded-xl shadow-card p-6">
          <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold mb-3">
            Contract endpoints
          </div>
          <ul className="space-y-2 font-mono text-[12px] text-slate-700 leading-snug">
            {endpoints.map((e, i) => (
              <li key={i} className="flex items-baseline gap-2">
                <span className="text-emerald-600 font-semibold w-7 shrink-0">
                  {e.split(' ')[0]}
                </span>
                <span className="text-slate-700 break-all">
                  {e.split(' ').slice(1).join(' ')}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <div className="mt-5 rounded-xl border border-dashed border-slate-300 bg-white/40 p-10 text-center">
        <div className="text-xs text-slate-400 font-mono uppercase tracking-wider">
          Page composition placeholder
        </div>
        <div className="text-sm text-slate-500 mt-1">
          {title} content will render here.
        </div>
      </div>
    </div>
  );
}
