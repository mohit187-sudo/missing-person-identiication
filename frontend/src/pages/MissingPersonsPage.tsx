import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FolderPlus, Filter } from 'lucide-react';
import { apiGet } from '../services/api';
import type { CaseListItem, Page } from '../types';
import {
  Badge,
  Card,
  DemoBadge,
  EmptyState,
  Pagination,
  PageHeader,
  SearchBar,
  TableSkeleton,
} from '../components/ui';
import { hasRole, useAuth } from '../hooks/useAuth';

const STATUSES = ['missing', 'investigating', 'potential_lead', 'located', 'closed', 'archived'];

export default function MissingPersonsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [includeDemo, setIncludeDemo] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '10' });
      if (q) params.set('q', q);
      if (status) params.set('status', status);
      params.set('include_demo', String(includeDemo));
      const res = await apiGet<Page<CaseListItem>>(`/cases?${params}`);
      setItems(res.items);
      setTotal(res.total);
      setPages(res.pages);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load cases.');
    } finally {
      setLoading(false);
    }
  }, [page, q, status, includeDemo]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Missing Persons"
        subtitle="Authorized case registry. All case information is confidential and access-restricted."
        actions={
          hasRole(user, 'administrator', 'investigator') ? (
            <Link to="/cases/new" className="btn-primary">
              <FolderPlus className="h-4 w-4" /> Register case
            </Link>
          ) : undefined
        }
      />

      <Card className="mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <SearchBar
            value={q}
            onChange={(v) => {
              setQ(v);
              setPage(1);
            }}
            placeholder="Search by case ID, name, location…"
            onSubmit={() => void load()}
          />
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                aria-label="Filter by status"
                className="input w-48"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">All statuses</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={includeDemo}
                onChange={(e) => {
                  setIncludeDemo(e.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-navy-500 bg-navy-800"
              />
              Include demo data
            </label>
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-4 rounded-md border border-rose-700 bg-rose-950/60 p-4 text-sm text-rose-100">
          {error}
        </div>
      )}

      {loading ? (
        <TableSkeleton rows={6} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No cases found"
          description="Adjust your filters, or register a new missing-person case to get started."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-navy-700">
          <table className="min-w-full divide-y divide-navy-700 text-sm">
            <thead className="bg-navy-900/70">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Case ID</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Name</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Age</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Last seen</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Status</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Photos</th>
                <th scope="col" className="px-4 py-3 text-left font-semibold text-slate-300">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-800 bg-navy-900/40">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-navy-800/50">
                  <td className="px-4 py-3">
                    <Link to={`/cases/${c.id}`} className="font-mono text-sky-300 hover:underline">
                      {c.case_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-100">{c.full_name ?? '(name unknown)'}</td>
                  <td className="px-4 py-3 text-slate-300">
                    {c.age_min ?? '?'}–{c.age_max ?? '?'}
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {c.last_seen_date ?? '—'}
                    <div className="text-xs text-slate-500">{c.last_seen_location}</div>
                  </td>
                  <td className="px-4 py-3"><Badge value={c.status} /></td>
                  <td className="px-4 py-3 text-slate-300">{c.photo_count}</td>
                  <td className="px-4 py-3">{c.is_demo ? <DemoBadge /> : <span className="text-xs text-slate-500">real record</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && items.length > 0 && (
        <Pagination page={page} pages={pages} total={total} onPage={setPage} />
      )}
    </div>
  );
}
