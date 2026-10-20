import { useCallback, useEffect, useState } from 'react';
import { UserPlus } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { apiGet, apiPatch, apiPost, ApiRequestError } from '../services/api';
import type { Page, User } from '../types';
import { Alert, Badge, Card, Field, formatDate, Modal, PageHeader, SearchBar, TableSkeleton } from '../components/ui';
import { useToast } from '../hooks/useToast';

const schema = z.object({
  email: z.string().email('Valid email required'),
  full_name: z.string().min(1, 'Name is required').max(255),
  password: z.string().min(10, 'Password must be at least 10 characters'),
  role: z.enum(['administrator', 'investigator', 'rescue_team']),
  agency: z.string().max(255).default(''),
  phone: z.string().max(64).default(''),
});
type FormValues = z.infer<typeof schema>;

export default function UserManagementPage() {
  const { toast } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { role: 'investigator', agency: '', phone: '' } });

  const load = useCallback(() => {
    setLoading(true);
    apiGet<Page<User>>(`/admin/users?page_size=50${q ? `&q=${encodeURIComponent(q)}` : ''}`)
      .then((r) => setUsers(r.items))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [q]);

  useEffect(() => {
    load();
  }, [load]);

  const createUser = async (values: FormValues) => {
    setServerError(null);
    try {
      await apiPost('/admin/users', values);
      toast('success', 'User account created.');
      setOpen(false);
      reset();
      load();
    } catch (err) {
      setServerError(err instanceof ApiRequestError ? err.error.message : 'Failed to create user.');
    }
  };

  const toggleActive = async (u: User) => {
    try {
      await apiPatch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      toast('success', `User ${u.is_active ? 'deactivated' : 'activated'}.`);
      load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Update failed');
    }
  };

  return (
    <div>
      <PageHeader
        title="User Management"
        subtitle="Admin-managed accounts only — public sign-up is disabled. Roles are enforced on every backend endpoint."
        actions={
          <button className="btn-primary" onClick={() => setOpen(true)}>
            <UserPlus className="h-4 w-4" /> Create user
          </button>
        }
      />

      <Card className="mb-6">
        <SearchBar value={q} onChange={setQ} placeholder="Search users by name or email…" onSubmit={load} />
      </Card>

      {loading ? (
        <TableSkeleton rows={5} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-navy-700">
          <table className="min-w-full divide-y divide-navy-700 text-sm">
            <thead className="bg-navy-900/70">
              <tr>
                {['Name', 'Email', 'Role', 'Agency', 'Status', 'Last login', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-semibold text-slate-300">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800 bg-navy-900/40">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-navy-800/50">
                  <td className="px-4 py-3 text-slate-100">{u.full_name}</td>
                  <td className="px-4 py-3 text-slate-300">{u.email}</td>
                  <td className="px-4 py-3"><Badge value="queued" label={u.role.replace('_', ' ')} /></td>
                  <td className="px-4 py-3 text-slate-400">{u.agency || '—'}</td>
                  <td className="px-4 py-3">
                    <Badge value={u.is_active ? 'completed' : 'failed'} label={u.is_active ? 'active' : 'deactivated'} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{formatDate(u.last_login_at)}</td>
                  <td className="px-4 py-3">
                    <button className="btn-secondary px-3 py-1.5" onClick={() => void toggleActive(u)}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={open} title="Create user account" onClose={() => setOpen(false)}>
        {serverError && <div className="mb-4"><Alert kind="error">{serverError}</Alert></div>}
        <form onSubmit={handleSubmit(createUser)} className="space-y-4" noValidate>
          <Field label="Full name" error={errors.full_name?.message} required>
            <input {...register('full_name')} className="input" />
          </Field>
          <Field label="Email" error={errors.email?.message} required>
            <input {...register('email')} type="email" className="input" />
          </Field>
          <Field label="Temporary password" error={errors.password?.message} hint="Min 10 characters. User should change it after first sign-in." required>
            <input {...register('password')} type="password" className="input" />
          </Field>
          <Field label="Role" error={errors.role?.message} required>
            <select {...register('role')} className="input">
              <option value="investigator">Authorized investigator</option>
              <option value="rescue_team">Rescue-team user</option>
              <option value="administrator">Administrator</option>
            </select>
          </Field>
          <Field label="Agency">
            <input {...register('agency')} className="input" />
          </Field>
          <Field label="Phone">
            <input {...register('phone')} className="input" />
          </Field>
          <button type="submit" className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Creating…' : 'Create account'}
          </button>
        </form>
      </Modal>
    </div>
  );
}
