import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BrainCircuit, UploadCloud } from 'lucide-react';
import { apiGet, apiPost, ApiRequestError } from '../services/api';
import type { AIStatus, SearchResult } from '../types';
import { Alert, Badge, Card, formatScore, PageHeader, Spinner } from '../components/ui';
import { useToast } from '../hooks/useToast';

const DISCLAIMER =
  'Similarity scores are technical measurements between facial embeddings — they are NOT the probability that two images show the same person. No one is identified until an authorized investigator verifies the match with independent corroborating evidence.';

export default function FaceMatchingPage() {
  const { toast } = useToast();
  const [ai, setAi] = useState<AIStatus | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; steps?: string[]; demo?: string } | null>(null);

  useEffect(() => {
    apiGet<AIStatus>('/matching/ai-status').then(setAi).catch(() => undefined);
  }, []);

  const runSearch = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await apiPost<SearchResult>('/matching/search', form);
      setResult(res);
      toast('success', `Search complete — ${res.matches.length} candidate(s) returned for review.`);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        const details = err.error.details as { setup_steps?: string[]; demo_alternative?: string };
        setError({ message: err.error.message, steps: details.setup_steps, demo: details.demo_alternative });
      } else {
        setError({ message: 'Search failed unexpectedly.' });
      }
      toast('error', 'Face search could not run — see the setup notice.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="AI Face Matching"
        subtitle="Upload a photograph to rank potential matches against authorized case records. Every candidate requires human review."
      />

      {ai && !ai.available && (
        <div className="mb-6">
          <Alert kind="warning" title="Facial matching engine not configured">
            <p>{ai.detail || 'Model weights are not installed.'}</p>
            <ol className="mt-2 list-decimal pl-5">
              {ai.setup_steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <p className="mt-2">
              This system never generates simulated or random scores. Non-biometric features (case
              registry, metadata search, uploads, review workflow) remain fully available in demo mode.
            </p>
          </Alert>
        </div>
      )}

      {ai?.available && (
        <div className="mb-6">
          <Alert kind="success" title="Matching engine online">
            Model <strong>{ai.model_name}</strong> ({ai.model_version}) · {ai.embedding_dim}-dim
            embeddings · {ai.license}
          </Alert>
        </div>
      )}

      <Card>
        <h2 className="mb-2 text-lg font-semibold text-white">Search photograph</h2>
        <p className="mb-4 text-sm text-slate-400">{DISCLAIMER}</p>

        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <label className="btn-secondary cursor-pointer">
            <UploadCloud className="h-4 w-4" /> Choose image (JPEG/PNG/WEBP)
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {file && <span className="text-sm text-slate-300">{file.name} ({Math.round(file.size / 1024)} KB)</span>}
          <button className="btn-primary" disabled={!file || busy} onClick={runSearch}>
            <BrainCircuit className="h-4 w-4" /> {busy ? 'Searching…' : 'Run face search'}
          </button>
        </div>

        {busy && <div className="mt-4"><Spinner label="Detecting faces and comparing embeddings…" /></div>}

        {error && (
          <div className="mt-4">
            <Alert kind="error" title="Setup required">
              <p>{error.message}</p>
              {error.steps && (
                <ol className="mt-2 list-decimal pl-5">
                  {error.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              )}
              {error.demo && <p className="mt-2 text-xs opacity-80">{error.demo}</p>}
            </Alert>
          </div>
        )}
      </Card>

      {result && (
        <>
          <Card className="mt-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Ranked candidates</h2>
            <div className="mb-4 grid gap-3 text-sm sm:grid-cols-4">
              <div><p className="text-slate-400">Model</p><p>{result.model_name} ({result.model_version})</p></div>
              <div><p className="text-slate-400">Threshold used</p><p>{result.threshold_used}</p></div>
              <div><p className="text-slate-400">Faces detected</p><p>{result.faces_detected}</p></div>
              <div><p className="text-slate-400">Job ID</p><p className="font-mono text-xs">{result.job_id}</p></div>
            </div>

            <Alert kind="info">{result.disclaimer}</Alert>

            {result.matches.length === 0 ? (
              <p className="mt-4 text-sm text-slate-400">
                No candidate met the similarity threshold. This is NOT a statement that the person is
                unregistered — try a clearer photograph or adjust the configured threshold (after
                validation on lawfully obtained data).
              </p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full divide-y divide-navy-700 text-sm">
                  <thead>
                    <tr>
                      <th className="px-3 py-2 text-left text-slate-300">Rank</th>
                      <th className="px-3 py-2 text-left text-slate-300">Candidate case</th>
                      <th className="px-3 py-2 text-left text-slate-300">Similarity score*</th>
                      <th className="px-3 py-2 text-left text-slate-300">Threshold</th>
                      <th className="px-3 py-2 text-left text-slate-300">Review status</th>
                      <th className="px-3 py-2 text-left text-slate-300">Data</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-800">
                    {result.matches.map((m, i) => (
                      <tr key={m.id}>
                        <td className="px-3 py-2">{i + 1}</td>
                        <td className="px-3 py-2">
                          <Link to={`/cases/${m.candidate_case_id}`} className="font-mono text-sky-300 hover:underline">
                            {m.candidate_case_number}
                          </Link>
                          <div className="text-xs text-slate-400">{m.candidate_name ?? '(name unknown)'}</div>
                        </td>
                        <td className="px-3 py-2 font-mono text-amber-300">{formatScore(m.similarity_score)}</td>
                        <td className="px-3 py-2">{m.threshold_used}</td>
                        <td className="px-3 py-2"><Badge value={m.status} /></td>
                        <td className="px-3 py-2">{m.is_demo ? <Badge value="demo" label="DEMO" /> : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-slate-500">* technical similarity measure — not an identity probability.</p>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
