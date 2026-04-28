export const COLORS = { navy:'#0A2540', gold:'#D4AF37', canvas:'#F8FAFC', cardBorder:'#E2E8F0', textMuted:'#64748B' };

export const RISK_TIER_COLORS = { healthy:'#10B981', watch:'#F59E0B', warning:'#F97316', critical:'#EF4444' };
export const RISK_TIER_LABELS = { healthy:'Healthy', watch:'Watch', warning:'Warning', critical:'Critical' };
export const SEVERITY_COLORS = { info:'#3B82F6', warning:'#F97316', critical:'#EF4444' };

export const TIER_PILL_CLASSES = {
  healthy:  'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  watch:    'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  warning:  'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  critical: 'bg-red-50 text-red-700 ring-1 ring-red-200',
};
export const SEVERITY_PILL_CLASSES = {
  info:     'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  warning:  'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  critical: 'bg-red-50 text-red-700 ring-1 ring-red-200',
};

// NEW for Step 3:
export const TIER_SOFT_BG = { healthy:'#ECFDF5', watch:'#FFFBEB', warning:'#FFF7ED', critical:'#FEF2F2' };
export const MAINT_KIND_CLASSES = {
  preventive: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  corrective: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  inspection: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',
}