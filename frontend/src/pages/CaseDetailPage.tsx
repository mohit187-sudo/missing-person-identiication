import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Archive, ImagePlus, Trash2 } from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost, ApiRequestError, fetchPhotoBlob } from '../services/api';
import type { MissingPersonCase, Photo } from '../types';
import {
  Alert,
  Badge,
  Card,
  ConfirmDialog,
  DemoBadge,
  Field,
  formatDate,
  PageHeader,
  Skeleton,
} from '../components/ui';
import { hasRole, useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';

function PhotoThumb({ photo }: { photo: Photo }) {
  const [src, setSrc] = useState('');
  useEffect(() => {
    let url = '';
    void fetchPhotoBlob(photo.case_id, photo.id).then((u) => {
      url = u;
      setSrc(u);
    });
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [photo.case_id, photo.id]);
  return src ? (
    <img src={src} alt={`Case photo ${photo.original_filename}`} className="h-32 w-32 rounded-lg object-cover" />
  ) : (
    <Skeleton className="h-32 w-32" />
  );
}

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [data, setData] = useState<MissingPersonCase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [statusNote, setStatusNote] = useState('');
  const [newStatus, setNewStatus] = useState('');
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const canEdit = hasRole(user, 'administrator', 'investigator');

  const load = useCallback(() => {
    if (!caseId) return;
    apiGet<MissingPersonCase>(`/cases/${caseId}`)
      .then(setData)
      .catch((e) => setError(e?.message ?? 'Case not found'));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="py-10">
        <Alert kind="error" title="Unable to load case">{error}</Alert>
        <Link to="/cases" className="btn-secondary mt-4 inline-flex"><ArrowLeft className="h-4 w-4" /> Back to cases</Link>
      </div>
    );
  }
  if (!data) return <div className="space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-64 w-full" /></div>;

  const saveStatus = async () => {
    if (!newStatus && !statusNote.trim()) return;
    setSaving(true);
    try {
      await apiPatch(`/cases/${data.id}`, {
        ...(newStatus ? { status: newStatus } : {}),
        status_note: statusNote,
      });
      toast('success', 'Case updated. Change recorded in status history.');
      setNewStatus('');
      setStatusNote('');
      load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  const uploadPhoto = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
    form.append('is_primary', 'false');
    try {
      const res = await apiPost<Photo & { ai?: { embedding_generated: boolean; reason: string } }>(
        `/cases/${data.id}/photos`,
        form,
      );
      if (res.ai?.embedding_generated) {
        toast('success', 'Photo uploaded and facial embedding generated.');
      } else {
        toast('warning', `Photo uploaded. Embedding not generated: ${res.ai?.reason || 'AI model unavailable'}`);
      }
      load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <Link to="/cases" className="mb-4 inline-flex items-center gap-1 text-sm text-sky-300 hover:underline">
        <ArrowLeft className="h-4 w-4" /> Back to cases
      </Link>

      <PageHeader
        title={`${data.case_number}${data.full_name ? ` — ${data.full_name}` : ' — (name unknown)'}`}
        subtitle={`Registered ${formatDate(data.created_at)} · Last updated ${formatDate(data.updated_at)}`}
        actions={
          <>
            {data.is_demo && <DemoBadge />}
            <Badge value={data.status} />
            {canEdit && (
              <button className="btn-danger" onClick={() => setArchiveOpen(true)}>
                <Archive className="h-4 w-4" /> Archive case
              </button>
            )}
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">Case details</h2>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-400">Age range</dt><dd className="text-slate-100">{data.age_min ?? '?'} – {data.age_max ?? '?'}</dd></div>
              <div><dt className="text-slate-400">Gender (descriptive)</dt><dd className="text-slate-100">{data.gender ?? '—'}</dd></div>
              <div><dt className="text-slate-400">Last-seen date</dt><dd className="text-slate-100">{data.last_seen_date ?? '—'}</dd></div>
              <div><dt className="text-slate-400">Last-seen location</dt><dd className="text-slate-100">{data.last_seen_location || '—'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-400">Physical description</dt><dd className="whitespace-pre-wrap text-slate-100">{data.physical_description || '—'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-400">Clothing description</dt><dd className="whitespace-pre-wrap text-slate-100">{data.clothing_description || '—'}</dd></div>
              <div><dt className="text-slate-400">Reporting agency</dt><dd className="text-slate-100">{data.contact_agency}</dd></div>
              <div><dt className="text-slate-400">Contact</dt><dd className="text-slate-100">{data.contact_info}</dd></div>
              <div><dt className="text-slate-400">Consent recorded</dt><dd className="text-slate-100">{data.consent_recorded ? 'Yes' : 'No'}</dd></div>
              <div><dt className="text-slate-400">Authorization ref.</dt><dd className="text-slate-100">{data.authorization_reference || '—'}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-400">Legal basis</dt><dd className="whitespace-pre-wrap text-slate-100">{data.legal_basis || '—'}</dd></div>
            </dl>
          </Card>

          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">Authorized photographs</h2>
            {data.photos.length === 0 ? (
              <p className="text-sm text-slate-400">No photographs uploaded yet.</p>
            ) : (
              <div className="flex flex-wrap gap-4">
                {data.photos.map((p) => (
                  <div key={p.id} className="text-center">
                    <PhotoThumb photo={p} />
                    <p className="mt-1 max-w-[9rem] truncate text-xs text-slate-400">{p.original_filename}</p>
                    <p className="text-xs text-slate-500">{p.embedding_count} embedding(s)</p>
                    {canEdit && (
                      <button
                        className="mt-1 text-xs text-rose-400 hover:underline"
                        onClick={async () => {
                          await apiDelete(`/cases/${data.id}/photos/${p.id}`);
                          toast('success', 'Photo removed.');
                          load();
                        }}
                      >
                        <Trash2 className="inline h-3 w-3" /> Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {canEdit && (
              <label className="btn-secondary mt-4 inline-flex cursor-pointer">
                <ImagePlus className="h-4 w-4" /> {uploading ? 'Uploading…' : 'Add photo'}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => void uploadPhoto(e.target.files?.[0])}
                />
              </label>
            )}
            <p className="mt-3 text-xs text-slate-500">
              JPEG/PNG/WEBP only · max {8} MB · files stored in private storage, served only through
              authenticated endpoints.
            </p>
          </Card>
        </div>

        <div className="space-y-6">
          {canEdit && (
            <Card>
              <h2 className="mb-4 text-lg font-semibold text-white">Update status</h2>
              <div className="space-y-3">
                <Field label="New status" hint="Status 'located' requires a verification note.">
                  <select className="input" value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                    <option value="">(keep current)</option>
                    {['missing', 'investigating', 'potential_lead', 'located', 'closed'].map((s) => (
                      <option key={s} value={s}>{s.replace('_', ' ')}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Verification / change note">
                  <textarea
                    className="input min-h-[80px]"
                    value={statusNote}
                    onChange={(e) => setStatusNote(e.target.value)}
                    placeholder="Document human verification, corroboration, or reason for change."
                  />
                </Field>
                <button className="btn-primary w-full" onClick={saveStatus} disabled={saving}>
                  {saving ? 'Saving…' : 'Save change'}
                </button>
              </div>
            </Card>
          )}

          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">Status history</h2>
            <ol className="space-y-3">
              {data.status_history.map((h) => (
                <li key={h.id} className="border-l-2 border-navy-600 pl-3 text-sm">
                  <div className="flex items-center gap-2">
                    {h.from_status && <Badge value={h.from_status} />}
                    {h.from_status && <span className="text-slate-500">→</span>}
                    <Badge value={h.to_status} />
                  </div>
                  {h.note && <p className="mt-1 text-slate-300">{h.note}</p>}
                  <p className="mt-0.5 text-xs text-slate-500">{formatDate(h.created_at)}</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive this case?"
        message="The case will be soft-deleted and retained according to the configured retention policy. This action is audit-logged."
        confirmLabel="Archive"
        danger
        onCancel={() => setArchiveOpen(false)}
        onConfirm={async () => {
          try {
            await apiDelete(`/cases/${data.id}`);
            toast('success', 'Case archived.');
            navigate('/cases');
          } catch (err) {
            toast('error', err instanceof ApiRequestError ? err.error.message : 'Archive failed');
          } finally {
            setArchiveOpen(false);
          }
        }}
      />
    </div>
  );
}
