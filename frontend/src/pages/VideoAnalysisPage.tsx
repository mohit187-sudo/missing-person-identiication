import { useCallback, useEffect, useRef, useState } from 'react';
import { Film, Play, Square, UploadCloud, FileDown } from 'lucide-react';
import { apiDownload, apiGet, apiPost, ApiRequestError } from '../services/api';
import type { Video, VideoJob, Page } from '../types';
import {
  Alert,
  Badge,
  Card,
  EmptyState,
  formatDate,
  PageHeader,
  ProgressBar,
  TableSkeleton,
} from '../components/ui';
import { useToast } from '../hooks/useToast';

export default function VideoAnalysisPage() {
  const { toast } = useToast();
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [authRef, setAuthRef] = useState('');
  const [lawful, setLawful] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [interval, setIntervalSec] = useState(1.0);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await apiGet<Page<Video>>('/videos?page_size=20');
      setVideos(res.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load videos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    pollRef.current = window.setInterval(() => {
      // Refresh job progress while anything is active.
      setVideos((prev) => {
        if (prev.some((v) => v.latest_job_status === 'running' || v.latest_job_status === 'queued')) {
          void load();
        }
        return prev;
      });
    }, 3000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [load]);

  const upload = async () => {
    if (!file || !title.trim()) {
      toast('warning', 'Choose a video file and provide a title.');
      return;
    }
    if (!lawful) {
      toast('warning', 'You must confirm the footage is lawfully obtained and authorized.');
      return;
    }
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
    form.append('title', title);
    form.append('authorization_reference', authRef);
    form.append('lawfully_obtained', 'true');
    try {
      await apiPost<Video>('/videos', form);
      toast('success', 'Video uploaded and probed successfully.');
      setFile(null);
      setTitle('');
      setAuthRef('');
      setLawful(false);
      void load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const process = async (video: Video) => {
    try {
      await apiPost<VideoJob>(`/videos/${video.id}/process`, {
        sampling_interval_seconds: interval,
      });
      toast('success', 'Processing job queued.');
      void load();
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Could not start processing');
    }
  };

  const cancel = async (video: Video) => {
    if (!video.latest_job_status) return;
    try {
      const status = await apiGet<{ latest: VideoJob | null }>(`/videos/${video.id}/status`);
      if (status.latest) {
        await apiPost(`/videos/jobs/${status.latest.id}/cancel`);
        toast('info', 'Cancellation requested — the job stops at the next frame boundary.');
        void load();
      }
    } catch (err) {
      toast('error', err instanceof ApiRequestError ? err.error.message : 'Cancel failed');
    }
  };

  return (
    <div>
      <PageHeader
        title="CCTV Video Analysis"
        subtitle="Process authorized, lawfully obtained footage only. The pipeline samples frames, detects faces, applies quality gates, and compares eligible detections against authorized case records."
      />

      <Alert kind="warning" title="Legal restriction">
        Do not upload footage you are not authorized to analyze. This system does not connect to
        live CCTV feeds, does not perform covert tracking, and does not track identity across
        unrelated cameras. Processing is limited to approved, case-related footage.
      </Alert>

      <Card className="mt-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Upload footage</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Title *</label>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Station camera 4 — 12 Oct, 09:00–11:00" />
          </div>
          <div>
            <label className="label">Authorization reference</label>
            <input className="input" value={authRef} onChange={(e) => setAuthRef(e.target.value)} placeholder="Warrant / case authorization ID" />
          </div>
          <div>
            <label className="label">Video file (MP4/AVI/MOV/MKV/WEBM, max 512 MB)</label>
            <label className="btn-secondary cursor-pointer">
              <UploadCloud className="h-4 w-4" /> {file ? file.name : 'Choose file'}
              <input type="file" accept="video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          <div>
            <label className="label">Frame sampling interval (seconds)</label>
            <input
              type="number"
              className="input"
              min={0.1}
              max={30}
              step={0.5}
              value={interval}
              onChange={(e) => setIntervalSec(Number(e.target.value))}
            />
          </div>
        </div>
        <label className="mt-4 flex items-start gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={lawful} onChange={(e) => setLawful(e.target.checked)} className="mt-1 h-4 w-4" />
          I confirm this footage was lawfully obtained and is authorized for case-related analysis.
        </label>
        <button className="btn-primary mt-4" onClick={upload} disabled={uploading}>
          {uploading ? 'Uploading & probing…' : 'Upload video'}
        </button>
      </Card>

      <div className="mt-6">
        <h2 className="mb-4 text-lg font-semibold text-white">Evidence library</h2>
        {loading ? (
          <TableSkeleton rows={4} />
        ) : error ? (
          <Alert kind="error">{error}</Alert>
        ) : videos.length === 0 ? (
          <EmptyState title="No footage uploaded" description="Authorized video evidence you upload will appear here with processing status and review reports." />
        ) : (
          <div className="space-y-4">
            {videos.map((v) => (
              <Card key={v.id}>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Film className="h-5 w-5 text-sky-400" />
                      <h3 className="font-semibold text-white">{v.title}</h3>
                      {v.latest_job_status && <Badge value={v.latest_job_status} />}
                    </div>
                    <p className="mt-1 text-sm text-slate-400">
                      {v.original_filename} · {v.width}×{v.height} · {v.duration_seconds?.toFixed(1)}s ·{' '}
                      {formatDate(v.created_at)}
                    </p>
                    <p className="text-xs text-slate-500">Authorization: {v.authorization_reference || '—'}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {(v.latest_job_status === 'queued' || v.latest_job_status === 'running') ? (
                      <button className="btn-danger" onClick={() => void cancel(v)}>
                        <Square className="h-4 w-4" /> Cancel
                      </button>
                    ) : (
                      <button className="btn-primary" onClick={() => void process(v)}>
                        <Play className="h-4 w-4" /> Process footage
                      </button>
                    )}
                    <button
                      className="btn-secondary"
                      onClick={() => void apiDownload(`/videos/${v.id}/report?format=csv`, `report_${v.id}.csv`)}
                    >
                      <FileDown className="h-4 w-4" /> CSV
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={() => void apiDownload(`/videos/${v.id}/report?format=pdf`, `report_${v.id}.pdf`)}
                    >
                      <FileDown className="h-4 w-4" /> PDF
                    </button>
                  </div>
                </div>
                {v.latest_job_status === 'running' && (
                  <div className="mt-4">
                    <ProgressBar value={v.latest_job_progress ?? 0} label="Processing" />
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
