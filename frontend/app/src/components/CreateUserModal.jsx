import { useEffect, useId, useState } from 'react';
import { X } from 'lucide-react';
import { createUser } from '../lib/api.js';

const ROLES = [
  { value: 'operator', label: 'Operator' },
  { value: 'admin', label: 'Admin' },
];

const PASSWORD_MIN_LEN = 8;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Modal form for the admin Users page — create a new app_user via
 * POST /auth/register. The backend gates that endpoint to admins (after the
 * bootstrap user), so we don't need a client-side role check; if a non-admin
 * somehow opens this modal the API will 403.
 *
 * Surfaces field-level validation errors for the common backend responses:
 *   - 409 conflict (duplicate email) → email field
 *   - 422 validation → first body.detail.loc to its field if recognised, else
 *     a top-of-form fallback
 */
export default function CreateUserModal({ open, onClose, onCreated }) {
  const titleId = useId();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('operator');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({}); // { email?, full_name?, role?, password?, confirm?, _form? }

  // Reset state every time the modal is (re)opened.
  useEffect(() => {
    if (!open) return;
    setEmail('');
    setFullName('');
    setRole('operator');
    setPassword('');
    setConfirmPassword('');
    setErrors({});
    setSubmitting(false);
  }, [open]);

  // Esc closes; lock body scroll while open.
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

  function validate() {
    const e = {};
    const trimmedEmail = email.trim();
    const trimmedName = fullName.trim();
    if (!trimmedEmail) e.email = 'Required.';
    else if (!EMAIL_RE.test(trimmedEmail)) e.email = 'Enter a valid email address.';
    if (!trimmedName) e.full_name = 'Required.';
    if (!password) e.password = 'Required.';
    else if (password.length < PASSWORD_MIN_LEN) e.password = `At least ${PASSWORD_MIN_LEN} characters.`;
    if (!confirmPassword) e.confirm = 'Required.';
    else if (password && confirmPassword !== password) e.confirm = "Passwords don't match.";
    return e;
  }

  function fieldErrorsFromApi(err) {
    // Backend error envelope variants:
    //   - {error: {code, message, status}}        (our custom 401/403/404/409)
    //   - {detail: [{type, loc:[...], msg}, ...]} (FastAPI validation 422)
    const out = {};
    const body = err?.body;
    if (!body) {
      out._form = err?.message || 'Could not create user.';
      return out;
    }
    if (err.status === 409 || body?.error?.code === 'email_taken') {
      out.email = body?.error?.message || 'An account with this email already exists.';
      return out;
    }
    if (Array.isArray(body?.detail)) {
      for (const item of body.detail) {
        const field = (item.loc || []).slice(-1)[0];
        const msg = item.msg || 'Invalid value.';
        if (field === 'email') out.email = msg.replace(/^Value error,\s*/, '');
        else if (field === 'password') out.password = msg.replace(/^Value error,\s*/, '');
        else if (field === 'full_name') out.full_name = msg.replace(/^Value error,\s*/, '');
        else if (field === 'role') out.role = msg.replace(/^Value error,\s*/, '');
        else out._form = msg;
      }
      return out;
    }
    out._form = body?.error?.message || body?.detail || err.message || 'Could not create user.';
    return out;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;

    const localErrors = validate();
    if (Object.keys(localErrors).length > 0) {
      setErrors(localErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const created = await createUser({
        email: email.trim(),
        full_name: fullName.trim(),
        role,
        password,
      });
      onCreated?.(created);
      onClose();
    } catch (err) {
      setErrors(fieldErrorsFromApi(err));
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
      <div
        className="absolute inset-0 bg-navy/40"
        onClick={() => !submitting && onClose()}
      />
      <div className="relative w-full max-w-[480px] max-h-[90vh] overflow-y-auto bg-white rounded-xl shadow-xl ring-1 ring-slate-200">
        <header className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-navy">
              Add user
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Creates a new admin or operator account.
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
          <FieldText
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="off"
            placeholder="name@fhh.com"
            required
            error={errors.email}
            autoFocus
          />
          <FieldText
            label="Full name"
            type="text"
            value={fullName}
            onChange={setFullName}
            autoComplete="off"
            placeholder="Jane Doe"
            required
            error={errors.full_name}
          />
          <FieldSelect
            label="Role"
            value={role}
            onChange={setRole}
            options={ROLES}
            error={errors.role}
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <FieldText
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              placeholder={`Min ${PASSWORD_MIN_LEN} chars`}
              required
              error={errors.password}
            />
            <FieldText
              label="Confirm password"
              type="password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
              placeholder="Repeat password"
              required
              error={errors.confirm}
            />
          </div>

          {errors._form && (
            <div
              role="alert"
              className="rounded-lg bg-red-50 ring-1 ring-red-200 px-3 py-2 text-[12.5px] text-red-800"
            >
              {errors._form}
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
              {submitting ? 'Creating…' : 'Create user'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field primitives
// ---------------------------------------------------------------------------

function FieldText({ label, type, value, onChange, placeholder, autoComplete, required, error, autoFocus }) {
  const id = useId();
  return (
    <Label id={id} label={label} required={required} error={error}>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        autoFocus={autoFocus}
        aria-invalid={!!error}
        className={inputClass(!!error)}
      />
    </Label>
  );
}

function FieldSelect({ label, value, onChange, options, required, error }) {
  const id = useId();
  return (
    <Label id={id} label={label} required={required} error={error}>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        aria-invalid={!!error}
        className={inputClass(!!error)}
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

function Label({ id, label, required, error, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[11px] uppercase tracking-[0.14em] text-slate-500 font-semibold">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && (
        <span className="text-[11.5px] text-red-700">{error}</span>
      )}
    </div>
  );
}

function inputClass(hasError) {
  return [
    'h-9 rounded-lg px-2.5 text-[13px] text-navy placeholder:text-slate-400 bg-white transition outline-none',
    hasError
      ? 'border border-red-300 focus:ring-2 focus:ring-red-200 focus:border-red-400'
      : 'border border-slate-200 focus:ring-2 focus:ring-navy/20 focus:border-navy/40',
  ].join(' ');
}
