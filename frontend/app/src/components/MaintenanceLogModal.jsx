import { useEffect, useId, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { COMPONENT_LABELS, COMPONENT_ORDER } from '../mockData.js';
import { postMaintenanceEntry } from '../lib/api.js';

const MAINT_TYPES = [
  { value: 'preventive', label: 'Preventive' },
  { value: 'corrective', label: 'Corrective' },
  { value: 'predictive', label: 'Predictive' },
  { value: 'inspection', label: 'Inspection' },
];

/**
 * Modal form for adding a user-written maintenance entry.
 *
 * Form fields per the Path C handoff:
 *   maintenance_type (select), work_description (textarea), cost_usd (number, optional),
 *   duration_hours (number, optional), technician_name (text), performed_at (datetime-local),
 *   component_id (optional select).
 *
 * Calls POST /machines/{machine_id}/maintenance-log via the api.js helper which
 * injects the bearer token. On success, fires onCreated with the new entry
 * (in mockData shape, source="user") so the parent can splice it into the
 * existing list, then closes itself.
 */
export default function MaintenanceLogModal({
  open,
  onClose,
  onCreated,
  machineId,
  currentUserName,
}) {
  const titleId = useId();
  const dialogRef = useRef(null);

  const [maintenanceType, setMaintenanceType] = useState('preventive');
  const [workDescription, setWorkDescription] = useState('');
  const [costUsd, setCostUsd] = useState('');
  const [durationHours, setDurationHours] = useState('');
  const [technicianName, setTechnicianName] = useState('');
  const [performedAt, setPerformedAt] = useState(() => defaultDateTimeLocal());
  const [componentId, setComponentId] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Reset state every time the modal is (re)opened so a previous attempt
  // doesn't leak across machines or sessions.
  useEffect(() => {
    if (!open) return;
    setMaintenanceType('preventive');
    setWorkDescription('');
    setCostUsd('');
    setDurationHours('');
    setTechnicianName(currentUserName || '');
    setPerformedAt(defaultDateTimeLocal());
    setComponentId('');
    setError(null);
    setSubmitting(false);
  }, [open, currentUserName]);

  // Escape closes; click-outside on the backdrop closes; body scroll locked
  // while open so background content can't scroll behind the dialog.
  useEffect(() => {
    if (!open) return;
    function onKey(e) {
      if (e.key === 'Escape' && !submitting) onClose();
    }
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, submitting, onClose]);

  if (!open) return null;

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    setError(null);

    const trimmedWork = workDescription.trim();
    const trimmedTech = technicianName.trim();
    if (!trimmedWork || !trimmedTech) {
      setError('Work description and technician name are required.');
      return;
    }

    const payload = {
      maintenance_type: maintenanceType,
      work_description: trimmedWork,
      technician_name: trimmedTech,
    };
    if (costUsd !== '') payload.cost_usd = Number(costUsd);
    if (durationHours !== '') payload.duration_hours = Number(durationHours);
    if (performedAt) payload.performed_at = toIsoUtc(performedAt);
    if (componentId) payload.component_id = componentId;

    setSubmitting(true);
    try {
      const created = await postMaintenanceEntry(machineId, payload);
      onCreated?.(created);
      onClose();
    } catch (err) {
      setError(err?.message || 'Could not save the entry. Please try again.');
      setSubmitting(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-[60] flex items-center justify-center px-4"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-navy/40"
        onClick={() => !submitting && onClose()}
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className="relative w-full max-w-[560px] max-h-[90vh] overflow-y-auto bg-white rounded-xl shadow-xl ring-1 ring-slate-200"
      >
        <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-navy">
              Add maintenance entry
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Logging to{' '}
              <span className="font-mono text-navy">{machineId}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={() => !submitting && onClose()}
            aria-label="Close"
            className="text-slate-400 hover:text-navy transition p-1 -m-1"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <FieldSelect
              label="Type"
              value={maintenanceType}
              onChange={setMaintenanceType}
              options={MAINT_TYPES}
              required
            />
            <FieldSelect
              label="Component (optional)"
              value={componentId}
              onChange={setComponentId}
              options={[
                { value: '', label: '— None —' },
                ...COMPONENT_ORDER.map((id) => ({
                  value: id,
                  label: COMPONENT_LABELS[id] || id,
                })),
              ]}
            />
          </div>

          <FieldTextarea
            label="Work description"
            value={workDescription}
            onChange={setWorkDescription}
            placeholder="What was done? Any anomalies, parts replaced, follow-ups…"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <FieldNumber
              label="Cost (USD)"
              value={costUsd}
              onChange={setCostUsd}
              min={0}
              step="0.01"
              placeholder="e.g. 1850.50"
            />
            <FieldNumber
              label="Duration (hours)"
              value={durationHours}
              onChange={setDurationHours}
              min={0}
              step="0.1"
              placeholder="e.g. 2.5"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <FieldText
              label="Technician"
              value={technicianName}
              onChange={setTechnicianName}
              required
              placeholder="Full name"
            />
            <FieldDateTime
              label="Performed at"
              value={performedAt}
              onChange={setPerformedAt}
            />
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-lg bg-red-50 ring-1 ring-red-200 px-3 py-2 text-[12.5px] text-red-800"
            >
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => !submitting && onClose()}
              disabled={submitting}
              className="h-9 px-3 rounded-lg text-sm text-slate-600 hover:text-navy hover:bg-slate-100 transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="h-9 px-4 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy/90 transition disabled:opacity-50"
            >
              {submitting ? 'Saving…' : 'Save entry'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function defaultDateTimeLocal() {
  // <input type="datetime-local"> wants "YYYY-MM-DDTHH:MM" without seconds /
  // timezone. Build it from the user's local clock so the picker shows "now".
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function toIsoUtc(localValue) {
  // Treat the datetime-local string as wall-clock in the user's timezone, then
  // convert to UTC ISO so the backend stores a timezone-aware timestamp.
  if (!localValue) return null;
  const d = new Date(localValue);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

// ---------------------------------------------------------------------------
// Field primitives (no abstraction across forms — kept local to this file)
// ---------------------------------------------------------------------------

function FieldText({ label, value, onChange, placeholder, required }) {
  return (
    <Label label={label} required={required}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className={inputClass}
      />
    </Label>
  );
}

function FieldNumber({ label, value, onChange, placeholder, min, step }) {
  return (
    <Label label={label}>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        step={step}
        className={inputClass}
      />
    </Label>
  );
}

function FieldDateTime({ label, value, onChange }) {
  return (
    <Label label={label}>
      <input
        type="datetime-local"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </Label>
  );
}

function FieldSelect({ label, value, onChange, options, required }) {
  return (
    <Label label={label} required={required}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className={inputClass}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Label>
  );
}

function FieldTextarea({ label, value, onChange, placeholder, required }) {
  return (
    <Label label={label} required={required}>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        rows={3}
        className={`${inputClass} h-auto py-2 leading-snug resize-y min-h-[72px]`}
      />
    </Label>
  );
}

function Label({ label, required, children }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[11px] uppercase tracking-[0.14em] text-slate-500 font-semibold">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      {children}
    </label>
  );
}

const inputClass =
  'h-9 rounded-lg border border-slate-200 px-2.5 text-[13px] text-navy placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 transition bg-white';
