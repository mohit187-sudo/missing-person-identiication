import { useCallback, useEffect, useState } from 'react';
import { apiGet } from '../services/api';
import type { AuditLogEntry, Page } from '../types';
import { Card, formatDate, Pagination, PageHeader, SearchBar, TableSkeleton } from '../components/ui';

export default function AuditLogsPage() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [action, setAction] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: '20' });
    if (action) params.set('action', action);
    apiGet<Page<AuditLogEntry>>(`/admin/audit-logs?${params}`)
      .then((r) => {
        setItems(r.items);
        setPages(r.pages);
        setTotal(r.total);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [page, action]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Audit Logs"
        subtitle="Append-only trail of sensitive operations: sign-ins, case changes, uploads, matching searches and reviews. Retained per the approved retention policy."
      />

      <Card className="mb-6">
        <SearchBar
          value={action}
          onChange={(v) => {
            setAction(v);
            setPage(1);
          }}
          placeholder="Filter by action (e.g. auth.login, case.created, match.reviewed)…"
          onSubmit={load}
        />
      </Card>

      {loading ? (
        <TableSkeleton rows={8} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-navy-700">
          <table className="min-w-full divide-y divide-navy-700 text-sm">
            <thead className="bg-navy-900/70">
              <tr>
                {['Time', 'User', 'Action', 'Resource', 'IP', 'Details'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-semibold text-slate-300">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800 bg-navy-900/40">
              {items.map((e) => (
                <tr key={e.id} className="hover:bg-navy-800/50">
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-400">{formatDate(e.created_at)}</td>
                  <td className="px-4 py-3 text-slate-200">{e.user_email || '—'}</td>
                  <td className="px-4 py-3"><code className="rounded bg-navy-800 px-1.5 py-0.5 text-xs text-sky-300">{e.action}</code></td>
                  <td className="px-4 py-3 text-xs text-slate-400">
                    {e.resource_type}{e.resource_id ? ` · ${e.resource_id.slice(0, 8)}…` : ''}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400">{e.ip_address || '—'}</td>
                  <td className="max-w-xs truncate px-4 py-3 text-xs text-slate-400" title={JSON.stringify(e.detail)}>
                    {JSON.stringify(e.detail)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && items.length > 0 && <Pagination page={page} pages={pages} total={total} onPage={setPage} />}
    </div>
  );
}
