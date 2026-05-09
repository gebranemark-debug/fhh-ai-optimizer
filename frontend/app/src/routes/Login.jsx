import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';

/**
 * Sign-in screen — the only public route in the app. ProtectedRoute redirects
 * here when a request lands without a valid token; on success we send the user
 * back to the page they were trying to reach (location.state.from), or to the
 * Overview if they navigated to /login directly.
 */
export default function Login() {
  const { status, login, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // If already signed in, don't render the form — bounce out immediately.
  // This handles the case where a user hits /login with a live token.
  if (status === 'auth') {
    const dest = location.state?.from?.pathname || '/';
    return <Navigate to={dest} replace />;
  }

  // Bootstrap is still in flight: render a placeholder rather than the form so
  // we don't flash an empty login screen at a user who's actually signed in.
  if (status === 'loading') {
    return (
      <div className="min-h-screen w-screen flex items-center justify-center bg-canvas">
        <div className="text-sm text-slate-500">Checking session…</div>
      </div>
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      const dest = location.state?.from?.pathname || '/';
      navigate(dest, { replace: true });
    } catch (_) {
      // Error message surfaced via context; nothing else to do here.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen w-screen flex items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-[400px]">
        <div className="flex items-center gap-2 mb-6 select-none">
          <div className="w-8 h-8 rounded-md bg-navy flex items-center justify-center">
            <span className="font-mono text-[12px] font-semibold text-gold tracking-tight">FHH</span>
          </div>
          <div className="leading-tight">
            <div className="text-[16px] font-semibold text-navy tracking-tight">FHH AI Optimizer</div>
            <div className="text-[10px] uppercase tracking-[0.14em] text-slate-400 font-medium">Predictive Operations</div>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-card p-6 flex flex-col gap-4"
        >
          <div>
            <h1 className="text-base font-semibold text-navy mb-1">Sign in</h1>
            <p className="text-[12px] text-slate-500">
              Enter your operator or admin credentials to continue.
            </p>
          </div>

          <Field
            label="Email"
            id="login-email"
            type="email"
            value={email}
            onChange={setEmail}
            autoFocus
            autoComplete="email"
            required
          />
          <Field
            label="Password"
            id="login-password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            required
          />

          {error && (
            <div
              role="alert"
              className="rounded-lg bg-red-50 ring-1 ring-red-200 px-3 py-2 text-[12.5px] text-red-800"
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !email || !password}
            className="mt-1 h-10 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="text-[11px] text-slate-400 text-center mt-4">
          Trouble signing in? Contact the FHH AI Optimizer admin.
        </div>
      </div>
    </div>
  );
}

function Field({ label, id, type, value, onChange, autoFocus, autoComplete, required }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="text-[11px] uppercase tracking-[0.14em] text-slate-500 font-semibold">
        {label}
      </span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        required={required}
        className="h-10 rounded-lg border border-slate-200 px-3 text-sm text-navy placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-navy/20 focus:border-navy/40 transition"
      />
    </label>
  );
}
