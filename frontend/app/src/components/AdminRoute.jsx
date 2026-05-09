import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';

/**
 * Gate for admin-only routes.
 *
 * Sits inside <ProtectedRoute>, so the auth bootstrap has already settled
 * by the time we render — status is "auth" with a populated user. If a
 * non-admin somehow lands here (typed URL, stale tab) we silently redirect
 * to "/" rather than throwing a 403, which keeps the operator demo flow
 * unbroken.
 *
 * The backend remains the source of truth: the GET /auth/users endpoint
 * is gated by require_role("admin"), so even bypassing this guard yields
 * an empty/error UI rather than data exposure.
 */
export default function AdminRoute() {
  const { user } = useAuth();
  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
