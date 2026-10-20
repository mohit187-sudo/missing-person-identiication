import { useEffect, useState, ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  Bell,
  BrainCircuit,
  ClipboardList,
  FileBarChart,
  Film,
  LayoutDashboard,
  LogOut,
  Menu,
  SearchCheck,
  Shield,
  ShieldCheck,
  UserCog,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { useAuth, hasRole } from '../hooks/useAuth';
import { apiGet } from '../services/api';

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  roles?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Overview', icon: <LayoutDashboard className="h-5 w-5" /> },
  { to: '/cases', label: 'Missing Persons', icon: <Users className="h-5 w-5" /> },
  {
    to: '/cases/new',
    label: 'Register Case',
    icon: <UserPlus className="h-5 w-5" />,
    roles: ['administrator', 'investigator'],
  },
  {
    to: '/matching',
    label: 'AI Face Matching',
    icon: <BrainCircuit className="h-5 w-5" />,
    roles: ['administrator', 'investigator'],
  },
  {
    to: '/videos',
    label: 'CCTV Analysis',
    icon: <Film className="h-5 w-5" />,
    roles: ['administrator', 'investigator'],
  },
  {
    to: '/matches',
    label: 'Potential Matches',
    icon: <SearchCheck className="h-5 w-5" />,
    roles: ['administrator', 'investigator'],
  },
  { to: '/investigations', label: 'Investigation Cases', icon: <ClipboardList className="h-5 w-5" /> },
  { to: '/notifications', label: 'Notifications', icon: <Bell className="h-5 w-5" /> },
  {
    to: '/admin/users',
    label: 'User Management',
    icon: <UserCog className="h-5 w-5" />,
    roles: ['administrator'],
  },
  {
    to: '/admin/audit',
    label: 'Audit Logs',
    icon: <ShieldCheck className="h-5 w-5" />,
    roles: ['administrator'],
  },
  { to: '/privacy', label: 'Privacy & Security', icon: <Shield className="h-5 w-5" /> },
  {
    to: '/reports',
    label: 'Reports & Analytics',
    icon: <FileBarChart className="h-5 w-5" />,
    roles: ['administrator'],
  },
];

function SideNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  return (
    <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3" aria-label="Main navigation">
      {NAV_ITEMS.filter((item) => !item.roles || hasRole(user, ...item.roles)).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
              isActive
                ? 'bg-sky-600/20 text-sky-300'
                : 'text-slate-300 hover:bg-navy-800 hover:text-white'
            }`
          }
        >
          {item.icon}
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = () =>
      apiGet<{ unread: number }>('/notifications/unread-count')
        .then((r) => alive && setUnread(r.unread))
        .catch(() => undefined);
    load();
    const t = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-navy-700 bg-navy-900/95 lg:flex">
        <div className="flex items-center gap-2 border-b border-navy-700 px-4 py-4">
          <SearchCheck className="h-7 w-7 text-sky-400" />
          <div>
            <p className="text-sm font-bold leading-tight text-white">Missing Person</p>
            <p className="text-xs text-slate-400">Identification System</p>
          </div>
        </div>
        <SideNav />
        <div className="border-t border-navy-700 p-4">
          <p className="truncate text-sm font-semibold text-white">{user?.full_name}</p>
          <p className="truncate text-xs text-slate-400">
            {user?.email} · {user?.role?.replace('_', ' ')}
          </p>
          <button
            className="btn-secondary mt-3 w-full"
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-navy-900 shadow-xl">
            <div className="flex items-center justify-between border-b border-navy-700 px-4 py-4">
              <p className="font-bold text-white">Menu</p>
              <button aria-label="Close menu" onClick={() => setMobileOpen(false)}>
                <X className="h-6 w-6 text-slate-300" />
              </button>
            </div>
            <SideNav onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        {/* Topbar */}
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-navy-700 bg-navy-950/90 px-4 py-3 backdrop-blur">
          <button
            className="rounded-md p-2 text-slate-300 hover:bg-navy-800 lg:hidden"
            aria-label="Open navigation menu"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="hidden text-sm text-slate-400 lg:block">
            Authorized access only — all actions are audit-logged.
          </div>
          <div className="flex items-center gap-3">
            <NavLink
              to="/notifications"
              className="relative rounded-md p-2 text-slate-300 hover:bg-navy-800"
              aria-label={`Notifications (${unread} unread)`}
            >
              <Bell className="h-5 w-5" />
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1 text-xs font-bold text-white">
                  {unread > 99 ? '99+' : unread}
                </span>
              )}
            </NavLink>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>

        <footer className="border-t border-navy-800 px-6 py-4 text-center text-xs text-slate-500">
          Missing Person Identification System — for lawful investigations with appropriate
          authorization. Similarity scores are technical measures, never identification
          probabilities. Human verification is mandatory.
        </footer>
      </div>
    </div>
  );
}
