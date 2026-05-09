import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';

/**
 * Wraps any nested routes that require an authenticated user.
 *
 * - "loading" status (token cached, /auth/me in flight): render a tiny
 *   placeholder so we don't flash either the app or the login screen.
 * - "anon": redirect to /login, preserving the intended destination in
 *   location state so Login can bounce the user back after sign-in.
 * - "auth": render the protected children via <Outlet />.
 */
export default function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="min-h-screen w-screen flex items-center justify-center bg-canvas">
        <div className="text-sm text-slate-500">Loading…</div>
      </div>
    );
  }

  if (status !== 'auth') {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
