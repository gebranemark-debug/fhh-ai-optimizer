import { useCallback, useEffect, useState } from 'react';
import { Plus, UserPlus, CheckCircle2 } from 'lucide-react';
import { getUsers } from '../lib/api.js';
import CreateUserModal from '../components/CreateUserModal.jsx';

/**
 * Admin-only Users management page. Routing is gated by AdminRoute; we
 * additionally surface a friendly empty state and inline error banner
 * since the backend will 403 if a non-admin somehow reaches the API.
 */
export default function Users() {
  const [users, setUsers] = useState({ status: 'loading', data: null, error: null });
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState(null); // { kind: 'success', message: string }

  const fetchUsers = useCallback(async () => {
    setUsers((s) => ({ ...s, status: s.status === 'ok' ? 'ok' : 'loading' }));
    try {
      const data = await getUsers();
      setUsers({ status: 'ok', data, error: null });
    } catch (error) {
      setUsers({ status: 'error', data: null, error });
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  // Auto-dismiss the success toast after a short delay.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  function handleCreated(created) {
    setToast({
      kind: 'success',
      message: `Created ${created.full_name || created.email} as ${created.role}.`,
    });
    fetchUsers();
  }

  return (
    <div className="px-8 py-7 max-w-[1100px] flex flex-col gap-5">
      <header className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-navy tracking-tight">Users</h1>
          <p className="text-[12.5px] text-slate-500 mt-0.5">
            Admins and operators with access to the FHH AI Optimizer.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy/90 transition"
        >
          <Plus className="w-3.5 h-3.5" />
          Add user
        </button>
      </header>

      {toast && (
        <div
          role="status"
          className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg bg-emerald-50 ring-1 ring-emerald-200 text-[12.5px] text-emerald-800"
        >
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{toast.message}</span>
        </div>
      )}

      <section className="bg-white rounded-xl shadow-card overflow-hidden">
        {users.status === 'loading' ? (
          <TableSkeleton />
        ) : users.status === 'error' ? (
          <div className="px-5 py-6 text-[13px] text-red-800 bg-red-50">
            Couldn't load users: {users.error?.message || 'Unknown error.'}
          </div>
        ) : users.data.length === 0 ? (
          <EmptyState onAdd={() => setModalOpen(true)} />
        ) : (
          <UsersTable users={users.data} />
        )}
      </section>

      <CreateUserModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function UsersTable({ users }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-[0.14em] text-slate-400 font-semibold border-b border-slate-100">
            <Th>Name</Th>
            <Th>Email</Th>
            <Th>Role</Th>
            <Th>Created</Th>
            <Th>Last login</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {users.map((u) => (
            <tr key={u.id} className="hover:bg-slate-50 transition-colors">
              <Td>
                <div className="text-[13px] text-navy font-medium">
                  {u.full_name || <span className="text-slate-400 italic">No name</span>}
                  {!u.is_active && (
                    <span className="ml-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                      inactive
                    </span>
                  )}
                </div>
              </Td>
              <Td>
                <span className="text-[12.5px] text-slate-700 font-mono">{u.email}</span>
              </Td>
              <Td>
                <RoleBadge role={u.role} />
              </Td>
              <Td>
                <span className="text-[12px] text-slate-600 font-mono" title={u.created_at}>
                  {relativeTime(u.created_at)}
                </span>
              </Td>
              <Td>
                {u.last_login_at ? (
                  <span className="text-[12px] text-slate-600 font-mono" title={u.last_login_at}>
                    {relativeTime(u.last_login_at)}
                  </span>
                ) : (
                  <span className="text-[12px] text-slate-400 italic">never</span>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RoleBadge({ role }) {
  const cls =
    role === 'admin'
      ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
      : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200';
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wide ${cls}`}>
      {role}
    </span>
  );
}

function Th({ children }) {
  return <th className="px-5 py-3 font-semibold">{children}</th>;
}

function Td({ children }) {
  return <td className="px-5 py-3 align-middle">{children}</td>;
}

function EmptyState({ onAdd }) {
  return (
    <div className="px-5 py-12 text-center">
      <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-slate-100 text-slate-500 mb-3">
        <UserPlus className="w-5 h-5" />
      </div>
      <div className="text-sm font-semibold text-navy">No users yet</div>
      <p className="text-[12.5px] text-slate-500 mt-0.5 mb-4 max-w-[360px] mx-auto">
        Invite operators and admins to give them access to the dashboard.
      </p>
      <button
        type="button"
        onClick={onAdd}
        className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-lg bg-navy text-white text-sm font-medium hover:bg-navy/90 transition"
      >
        <Plus className="w-3.5 h-3.5" />
        Add the first user
      </button>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="px-5 py-4 flex flex-col gap-2.5">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-[44px] rounded-md bg-slate-100 animate-pulse" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso) {
  if (!iso) return '';
  const then = typeof iso === 'string' ? new Date(iso) : iso;
  const ms = Date.now() - then.getTime();
  if (Number.isNaN(ms)) return '';
  const sec = Math.round(ms / 1000);
  if (sec < 60) return 'just now';
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
