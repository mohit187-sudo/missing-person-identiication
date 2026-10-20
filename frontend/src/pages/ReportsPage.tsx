import { useEffect, useState } from 'react';
import { FileDown, FileText } from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from 'recharts';
import { apiDownload, apiGet } from '../services/api';
import type { OverviewStats } from '../types';
import { Alert, Card, PageHeader, Skeleton, StatCard } from '../components/ui';
import { useToast } from '../hooks/useToast';

interface ActivitySummary {
  since: string;
  actions: { action: string; count: number }[];
  disclaimer: string;
}

export default function ReportsPage() {
  const { toast } = useToast();
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [activity, setActivity] = useState<ActivitySummary | null>(null);

  useEffect(() => {
    apiGet<OverviewStats>('/stats/overview').then(setStats).catch(() => undefined);
    apiGet<ActivitySummary>('/reports/activity-summary').then(setActivity).catch(() => undefined);
  }, []);

  return (
    <div>
      <PageHeader
        title="Reports & Analytics"
        subtitle="Exports and charts are generated from actual database records. No synthetic accuracy metrics are ever presented."
        actions={
          <>
            <button
              className="btn-secondary"
              onClick={() =>
                void apiDownload('/reports/cases?format=csv', 'cases_report.csv').catch(() =>
                  toast('error', 'CSV export failed'),
                )
              }
            >
              <FileDown className="h-4 w-4" /> Cases CSV
            </button>
            <button
              className="btn-primary"
              onClick={() =>
                void apiDownload('/reports/cases?format=pdf', 'cases_report.pdf').catch(() =>
                  toast('error', 'PDF export failed'),
                )
              }
            >
              <FileText className="h-4 w-4" /> Cases PDF
            </button>
          </>
        }
      />

      {!stats ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total cases" value={stats.total_cases} />
          <StatCard label="Photos" value={stats.total_photos} accent="violet" />
          <StatCard label="Videos" value={stats.total_videos} accent="amber" />
          <StatCard label="Matches (7 days)" value={stats.matches_last_7_days} accent="emerald" />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 text-lg font-semibold text-white">Case status distribution</h2>
          <div className="h-72">
            {stats && (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={Object.entries(stats.cases_by_status).map(([name, value]) => ({ name, value }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f3356" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#0b1529', border: '1px solid #1f3356' }} />
                  <Bar dataKey="value" fill="#6366f1" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 text-lg font-semibold text-white">Investigation activity (30 days)</h2>
          <div className="h-72">
            {activity && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activity.actions.slice(0, 12)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f3356" />
                  <XAxis dataKey="action" stroke="#94a3b8" fontSize={9} angle={-25} textAnchor="end" height={60} />
                  <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#0b1529', border: '1px solid #1f3356' }} />
                  <Legend />
                  <Line type="monotone" dataKey="count" stroke="#0ea5e9" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {activity && (
        <div className="mt-6">
          <Alert kind="info" title="Report data notice">{activity.disclaimer}</Alert>
        </div>
      )}
    </div>
  );
}
