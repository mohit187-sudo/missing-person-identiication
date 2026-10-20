import { ReactNode, useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle, Inbox, Loader2 } from 'lucide-react';

/* ---------- layout helpers ---------- */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-300">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/* ---------- badges ---------- */
const badgeColors: Record<string, string> = {
  missing: 'bg-rose-900/70 text-rose-200 border-rose-700',
  investigating: 'bg-sky-900/70 text-sky-200 border-sky-700',
  potential_lead: 'bg-amber-900/70 text-amber-200 border-amber-700',
  located: 'bg-emerald-900/70 text-emerald-200 border-emerald-700',
  closed: 'bg-slate-800 text-slate-300 border-slate-600',
  archived: 'bg-slate-900 text-slate-400 border-slate-700',
  pending: 'bg-amber-900/70 text-amber-200 border-amber-700',
  confirmed_for_investigation: 'bg-emerald-900/70 text-emerald-200 border-emerald-700',
  rejected: 'bg-rose-900/70 text-rose-200 border-rose-700',
  requires_manual_review: 'bg-violet-900/70 text-violet-200 border-violet-700',
  demo: 'bg-fuchsia-900/70 text-fuchsia-200 border-fuchsia-700',
  completed: 'bg-emerald-900/70 text-emerald-200 border-emerald-700',
  running: 'bg-sky-900/70 text-sky-200 border-sky-700',
  queued: 'bg-slate-800 text-slate-300 border-slate-600',
  failed: 'bg-rose-900/70 text-rose-200 border-rose-700',
  cancelled: 'bg-slate-800 text-slate-400 border-slate-700',
};

export function Badge({ value, label }: { value: string; label?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeColors[value] ?? 'bg-navy-800 text-slate-300 border-navy-600'}`}
    >
      {label ?? value.replace(/_/g, ' ')}
    </span>
  );
}

export function DemoBadge() {
  return <Badge value="demo" label="DEMO DATA" />;
}

/* ---------- feedback ---------- */
export function Alert({
  kind = 'info',
  title,
  children,
}: {
  kind?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  children: ReactNode;
}) {
  const cfg = {
    info: { cls: 'border-sky-700 bg-sky-950/60 text-sky-100', Icon: Info },
    success: { cls: 'border-emerald-700 bg-emerald-950/60 text-emerald-100', Icon: CheckCircle2 },
    warning: { cls: 'border-amber-700 bg-amber-950/60 text-amber-100', Icon: AlertTriangle },
    error: { cls: 'border-rose-700 bg-rose-950/60 text-rose-100', Icon: XCircle },
  }[kind];
  return (
    <div role="alert" className={`flex gap-3 rounded-lg border p-4 text-sm ${cfg.cls}`}>
      <cfg.Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        <div className={title ? 'mt-1 opacity-90' : ''}>{children}</div>
      </div>
    </div>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-navy-700/60 ${className}`} />;
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-navy-600 p-10 text-center">
      <Inbox className="mb-3 h-10 w-10 text-navy-400" />
      <h3 className="text-lg font-semibold text-slate-200">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-slate-400">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-300">
      <Loader2 className="h-5 w-5 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

/* ---------- modal + confirm ---------- */
export function Modal({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    if (open) window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div
        className={`max-h-[90vh] w-full overflow-y-auto rounded-xl border border-navy-600 bg-navy-900 p-6 shadow-2xl ${wide ? 'max-w-3xl' : 'max-w-lg'}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close dialog" className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel}>
      <p className="text-sm text-slate-300">{message}</p>
      <div className="mt-6 flex justify-end gap-3">
        <button className="btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm}>
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- forms ---------- */
export function Field({
  label,
  error,
  hint,
  children,
  required,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <div>
      <label className="label">
        <span>
          {label}
          {required && <span className="ml-1 text-rose-400">*</span>}
        </span>
        {children}
      </label>
      {hint && !error && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      {error && <p role="alert" className="mt-1 text-xs text-rose-400">{error}</p>}
    </div>
  );
}

/* ---------- misc ---------- */
export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div>
      {label && <div className="mb-1 flex justify-between text-xs text-slate-300"><span>{label}</span><span>{pct}%</span></div>}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-navy-700">
        <div
          className={`h-full rounded-full transition-all ${pct >= 100 ? 'bg-emerald-500' : 'bg-sky-500'}`}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (p: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-300">
      <span>
        Page {page} of {pages} · {total} records
      </span>
      <div className="flex gap-2">
        <button className="btn-secondary px-3 py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </button>
        <button className="btn-secondary px-3 py-1.5" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  accent = 'sky',
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent?: 'sky' | 'emerald' | 'amber' | 'rose' | 'violet';
}) {
  const accents = {
    sky: 'border-sky-700 text-sky-300',
    emerald: 'border-emerald-700 text-emerald-300',
    amber: 'border-amber-700 text-amber-300',
    rose: 'border-rose-700 text-rose-300',
    violet: 'border-violet-700 text-violet-300',
  };
  return (
    <div className={`card border-l-4 ${accents[accent]}`}>
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-bold text-white">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

export function SearchBar({
  value,
  onChange,
  placeholder = 'Search…',
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  onSubmit?: () => void;
}) {
  return (
    <form
      role="search"
      className="flex w-full max-w-md gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit?.();
      }}
    >
      <input
        type="search"
        className="input"
        placeholder={placeholder}
        value={value}
        aria-label={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      {onSubmit && (
        <button type="submit" className="btn-secondary">
          Search
        </button>
      )}
    </form>
  );
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function formatScore(score: number): string {
  return score.toFixed(4);
}
