import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiGet } from '../services/api';
import type { CaseListItem, Page } from '../types';
import { Badge, Card, DemoBadge, EmptyState, PageHeader, TableSkeleton } from '../components/ui';

/** Investigation board: active casework grouped by workflow status. */
export default function InvestigationsPage() {
  const [items, setItems] = useState<CaseListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiGet<Page<CaseListItem>>('/cases?page_size=50&sort=created_desc')
      .then((r) => setItems(r.items))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, []);

  const groups: { key: string; title: string; note: string }[] = [
    { key: 'missing', title: 'Open — missing', note: 'Actively seeking information' },
    { key: 'investigating', title: 'Under investigation', note: 'Active investigative work' },
    { key: 'potential_lead', title: 'Potential leads', note: 'Reviewed match candidates in play' },
    { key: 'located', title: 'Located', note: 'Verified in person — documented' },
  ];

  return (
    <div>
      <PageHeader
        title="Investigation Cases"
        subtitle="Kanban-style view of active casework. Moving a case to 'located' always requires documented human verification — never an AI result alone."
      />

      {loading ? (
        <TableSkeleton rows={6} />
      ) : items.length === 0 ? (
        <EmptyState title="No cases yet" description="Registered cases will be organised here by workflow stage." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-4">
          {groups.map((g) => {
            const cases = items.filter((c) => c.status === g.key);
            return (
              <div key={g.key}>
                <div className="mb-3">
                  <h2 className="font-semibold text-white">{g.title}</h2>
                  <p className="text-xs text-slate-400">{g.note} · {cases.length}</p>
                </div>
                <div className="space-y-3">
                  {cases.length === 0 && (
                    <div className="rounded-lg border border-dashed border-navy-700 p-4 text-sm text-slate-500">
                      None in this stage
                    </div>
                  )}
                  {cases.map((c) => (
                    <Card key={c.id} className="!p-4">
                      <Link to={`/cases/${c.id}`} className="font-mono text-sm text-sky-300 hover:underline">
                        {c.case_number}
                      </Link>
                      <p className="mt-1 text-sm text-slate-100">{c.full_name ?? '(name unknown)'}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {c.last_seen_location || 'Location unknown'} · {c.photo_count} photo(s)
                      </p>
                      <div className="mt-2 flex items-center gap-2">
                        <Badge value={c.status} />
                        {c.is_demo && <DemoBadge />}
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
