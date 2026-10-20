import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, CheckCheck } from 'lucide-react';
import { apiGet, apiPost } from '../services/api';
import type { Notification, Page } from '../types';
import { EmptyState, formatDate, PageHeader, TableSkeleton } from '../components/ui';
import { useToast } from '../hooks/useToast';

export default function NotificationsPage() {
  const { toast } = useToast();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiGet<Page<Notification>>(`/notifications?page_size=30&unread_only=${unreadOnly}`)
      .then((r) => setItems(r.items))
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [unreadOnly]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Notifications"
        subtitle="Minimal, privacy-preserving alerts — full personal case details are never included in notifications."
        actions={
          <>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} className="h-4 w-4" />
              Unread only
            </label>
            <button
              className="btn-secondary"
              onClick={async () => {
                await apiPost('/notifications/read-all');
                toast('success', 'All notifications marked as read.');
                load();
              }}
            >
              <CheckCheck className="h-4 w-4" /> Mark all read
            </button>
          </>
        }
      />

      {loading ? (
        <TableSkeleton rows={5} />
      ) : items.length === 0 ? (
        <EmptyState title="No notifications" description="Job completions and match-review requests will appear here." />
      ) : (
        <ul className="space-y-3">
          {items.map((n) => (
            <li
              key={n.id}
              className={`card flex items-start gap-3 !p-4 ${n.is_read ? 'opacity-70' : 'border-sky-700'}`}
            >
              <Bell className={`mt-1 h-5 w-5 ${n.is_read ? 'text-slate-500' : 'text-sky-400'}`} />
              <div className="flex-1">
                <p className="font-medium text-slate-100">{n.title}</p>
                {n.body && <p className="mt-0.5 text-sm text-slate-300">{n.body}</p>}
                <p className="mt-1 text-xs text-slate-500">{formatDate(n.created_at)}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                {n.link && (
                  <Link to={n.link} className="text-sm text-sky-300 hover:underline">
                    Open
                  </Link>
                )}
                {!n.is_read && (
                  <button
                    className="text-xs text-slate-400 hover:text-white"
                    onClick={async () => {
                      await apiPost(`/notifications/${n.id}/read`);
                      load();
                    }}
                  >
                    Mark read
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
