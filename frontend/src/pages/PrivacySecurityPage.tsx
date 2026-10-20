import { useCallback, useEffect, useState } from 'react';
import { Shield, Lock, FileWarning, Trash2 } from 'lucide-react';
import { apiGet, apiPatch, apiPost, apiPut, ApiRequestError } from '../services/api';
import type { RetentionPolicy } from '../types';
import { Alert, Badge, Card, Field, PageHeader, TableSkeleton } from '../components/ui';
import { hasRole, useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';

export default function PrivacySecurityPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [requestType, setRequestType] = useState('correction');
  const [subjectRef, setSubjectRef] = useState('');
  const [description, setDescription] = useState('');
  const isAdmin = hasRole(user, 'administrator');

  const load = useCallback(() => {
    apiGet<RetentionPolicy[]>('/privacy/retention-policies')
      .then(setPolicies)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updatePolicy = async (p: RetentionPolicy, days: number) => {
    try {
      await apiPut(`/privacy/retention-policies/${p.resource_type}`, {
        retention_days: days,
        action: p.action,
        is_active: p.is_active,
        description: p.description,
      });
      toast('success', `Retention updated for ${p.resource_type}.`);
      load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Update failed');
    }
  };

  const runRetention = async () => {
    try {
      const res = await apiPost<{ report: Record<string, number> }>('/privacy/run-retention');
      toast('success', `Retention pass complete: ${JSON.stringify(res.report)}`);
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Retention run failed');
    }
  };

  const submitRequest = async () => {
    if (description.trim().length < 10) {
      toast('warning', 'Please describe the request (min 10 characters).');
      return;
    }
    try {
      await apiPost('/privacy/correction-requests', {
        subject_reference: subjectRef,
        request_type: requestType,
        description,
      });
      toast('success', 'Request submitted to administrators.');
      setSubjectRef('');
      setDescription('');
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Submission failed');
    }
  };

  return (
    <div>
      <PageHeader
        title="Privacy & Security Settings"
        subtitle="Data-minimization controls, retention schedules, biometric-data restrictions, and the documented process for correcting mistaken matches."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-white">
            <Shield className="h-5 w-5 text-sky-400" /> Retention policies
          </h2>
          <p className="mb-4 text-sm text-slate-400">
            Secure-deletion schedules per resource type. Biometric embeddings and rejected match
            candidates are deleted according to these approved policies.
          </p>

          {loading ? (
            <TableSkeleton rows={4} />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-navy-700 text-sm">
                <thead>
                  <tr>
                    {['Resource', 'Retention (days)', 'Action', 'Active', ''].map((h) => (
                      <th key={h} className="px-3 py-2 text-left text-slate-300">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-800">
                  {policies.map((p) => (
                    <tr key={p.id}>
                      <td className="px-3 py-2">
                        <p className="text-slate-100">{p.resource_type}</p>
                        <p className="text-xs text-slate-500">{p.description}</p>
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="number"
                          className="input w-28"
                          defaultValue={p.retention_days}
                          disabled={!isAdmin}
                          onBlur={(e) => {
                            const v = Number(e.target.value);
                            if (v !== p.retention_days && v > 0) void updatePolicy(p, v);
                          }}
                        />
                      </td>
                      <td className="px-3 py-2"><Badge value="queued" label={p.action} /></td>
                      <td className="px-3 py-2">{p.is_active ? 'Yes' : 'No'}</td>
                      <td className="px-3 py-2">
                        {isAdmin && (
                          <button
                            className="btn-secondary px-2 py-1 text-xs"
                            onClick={async () => {
                              await apiPatch(`/privacy/retention-policies/${p.resource_type}`, {
                                retention_days: p.retention_days,
                                action: p.action,
                                is_active: !p.is_active,
                                description: p.description,
                              });
                              load();
                            }}
                          >
                            Toggle
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {isAdmin && (
            <button className="btn-danger mt-4" onClick={runRetention}>
              <Trash2 className="h-4 w-4" /> Run secure-deletion pass now
            </button>
          )}
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
              <Lock className="h-5 w-5 text-emerald-400" /> Security posture
            </h2>
            <ul className="space-y-2 text-sm text-slate-300">
              <li>✓ Short-lived JWT access tokens + rotating refresh tokens</li>
              <li>✓ Argon2id password hashing</li>
              <li>✓ Role-based authorization on every endpoint</li>
              <li>✓ Login rate limiting and account lockout</li>
              <li>✓ Security headers (CSP, HSTS-ready, frame denial)</li>
              <li>✓ CORS allowlist (no wildcards)</li>
              <li>✓ Private storage — photos/videos never publicly served</li>
              <li>✓ Upload validation (type, size, decode verification, hashing)</li>
              <li>✓ SQL injection prevention via ORM parameterization</li>
              <li>✓ Audit logging of all sensitive operations</li>
              <li>✓ Biometric embeddings restricted to authorized roles</li>
              <li>✓ Malware-scan integration point on uploads</li>
            </ul>
          </Card>

          <Card>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
              <FileWarning className="h-5 w-5 text-amber-400" /> Mistaken match?
            </h2>
            <p className="mb-3 text-sm text-slate-400">
              Any person affected by a mistaken match or record can request correction or deletion.
              Requests go to administrators and are audit-tracked.
            </p>
            <div className="space-y-3">
              <Field label="Request type">
                <select className="input" value={requestType} onChange={(e) => setRequestType(e.target.value)}>
                  <option value="correction">Correct a record / mistaken match</option>
                  <option value="deletion">Deletion request</option>
                  <option value="access">Access request</option>
                </select>
              </Field>
              <Field label="Case / subject reference">
                <input className="input" value={subjectRef} onChange={(e) => setSubjectRef(e.target.value)} placeholder="e.g. MPI-2026-000123" />
              </Field>
              <Field label="Description">
                <textarea className="input min-h-[80px]" value={description} onChange={(e) => setDescription(e.target.value)} />
              </Field>
              <button className="btn-primary w-full" onClick={submitRequest}>Submit request</button>
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-6">
        <Alert kind="info" title="Privacy notice">
          This system is intended solely for lawful missing-person investigations with appropriate
          authorization. Face search is never available to anonymous visitors. Demographic
          characteristics are never used to infer identity. Data is minimized, retention is
          configurable, and deletion follows approved schedules.
        </Alert>
      </div>
    </div>
  );
}
