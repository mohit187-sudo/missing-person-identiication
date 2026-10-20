import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, BrainCircuit, FolderPlus } from 'lucide-react';
import { apiGet } from '../services/api';
import type { OverviewStats } from '../types';
import { Alert, Card, EmptyState, PageHeader, Skeleton, StatCard } from '../components/ui';
import { useAuth, hasRole } from '../hooks/useAuth';

const PIE_COLORS = ['#f43f5e', '#0ea5e9', '#f59e0b', '#10b981', '#64748b', '#334155'];

export default function OverviewPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<OverviewStats>('/stats/overview')
      .then(setStats)
      .catch((e) => setError(e?.message ?? 'Failed to load statistics.'));
  }, []);

  return (
    <div>
      <PageHeader
        title="Dashboard Overview"
        subtitle="Statistics are computed from live database records. Demo records are counted separately and clearly labelled everywhere."
        actions={
          hasRole(user, 'administrator', 'investigator') ? (
            <Link to="/cases/new" className="btn-primary">
              <FolderPlus className="h-4 w-4" /> Register missing person
            </Link>
          ) : undefined
        }
      />

      {error && <Alert kind="error" title="Could not load dashboard">{error}</Alert>}

      {stats?.ai_available === false && (
        <div className="mb-6">
          <Alert kind="warning" title="AI model not configured — non-biometric demo mode">
            <p>
              The facial matching engine has no model weights installed, so matching endpoints
              return a setup error and NEVER fabricated scores. Case registry, metadata search,
              uploads, review workflow and video job tracking remain fully usable.
            </p>
            <p className="mt-1">
              Install weights with <code className="rounded bg-navy-800 px-1">python scripts/download_models.py</code>.
            </p>
          </Alert>
        </div>
      )}

      {!stats ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total cases" value={stats.total_cases} sub={`${stats.demo_cases} demo records`} />
          <StatCard label="Active cases" value={stats.active_cases} accent="rose" />
          <StatCard label="Located" value={stats.located_cases} accent="emerald" />
          <StatCard label="Photos / Videos" value={`${stats.total_photos} / ${stats.total_videos}`} accent="violet" />
          <StatCard
            label="Matches awaiting review"
            value={stats.matches_pending_review}
            accent="amber"
            sub="Human verification required"
          />
          <StatCard label="Confirmed for investigation" value={stats.matches_confirmed} accent="emerald" />
          <StatCard label="Processing jobs" value={stats.jobs_running + stats.jobs_completed} sub={`${stats.jobs_running} running`} />
          <StatCard
            label="AI engine"
            value={stats.ai_available ? 'Online' : 'Offline'}
            accent={stats.ai_available ? 'emerald' : 'amber'}
            sub={stats.ai_available ? 'Embedding model loaded' : 'Setup required — no fake scores'}
          />
        </div>
      )}

      {stats && (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">Cases by status</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={Object.entries(stats.cases_by_status).map(([name, value]) => ({ name, value }))}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={(e) => `${e.name}: ${e.value}`}
                  >
                    {Object.entries(stats.cases_by_status).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#0b1529', border: '1px solid #1f3356' }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">Activity (live records)</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    { name: 'Cases (30d)', value: stats.cases_last_30_days },
                    { name: 'Matches (7d)', value: stats.matches_last_7_days },
                    { name: 'Pending review', value: stats.matches_pending_review },
                    { name: 'Rejected', value: stats.matches_rejected },
                  ]}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f3356" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#0b1529', border: '1px solid #1f3356' }} />
                  <Bar dataKey="value" fill="#0ea5e9" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {stats && stats.total_cases === 0 && (
        <div className="mt-6">
          <EmptyState
            title="No cases registered yet"
            description="Register a missing-person case or run the demo seed script (python scripts/seed_demo.py) to explore the platform with clearly-labelled synthetic records."
          />
        </div>
      )}

      <div className="mt-6">
        <Alert kind="info" title="Responsible-use notice">
          <p className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Potential-match similarity scores are technical measurements — not probabilities of
              identity. No case status changes and no law-enforcement action are ever triggered
              automatically. Every candidate requires investigator review and independent
              corroboration.{' '}
              <Link to="/privacy" className="text-sky-300 underline">
                Privacy & security settings
              </Link>
            </span>
          </p>
        </Alert>
      </div>
    </div>
  );
}
