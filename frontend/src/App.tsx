import { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Layout } from './components/Layout';
import { hasRole, useAuth } from './hooks/useAuth';
import { Spinner } from './components/ui';

import LoginPage from './pages/LoginPage';
import OverviewPage from './pages/OverviewPage';
import MissingPersonsPage from './pages/MissingPersonsPage';
import RegisterCasePage from './pages/RegisterCasePage';
import CaseDetailPage from './pages/CaseDetailPage';
import FaceMatchingPage from './pages/FaceMatchingPage';
import VideoAnalysisPage from './pages/VideoAnalysisPage';
import PotentialMatchesPage from './pages/PotentialMatchesPage';
import InvestigationsPage from './pages/InvestigationsPage';
import NotificationsPage from './pages/NotificationsPage';
import UserManagementPage from './pages/UserManagementPage';
import AuditLogsPage from './pages/AuditLogsPage';
import PrivacySecurityPage from './pages/PrivacySecurityPage';
import ReportsPage from './pages/ReportsPage';

/** UX-only guard. The backend independently enforces every permission. */
function RequireAuth({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Checking your session…" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && !hasRole(user, ...roles)) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <h1 className="text-2xl font-bold text-white">Access restricted</h1>
        <p className="mt-2 text-slate-300">
          Your role does not permit this page. The same rule is enforced on every API endpoint.
        </p>
      </div>
    );
  }
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <OverviewPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases"
        element={
          <RequireAuth>
            <MissingPersonsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/new"
        element={
          <RequireAuth roles={['administrator', 'investigator']}>
            <RegisterCasePage />
          </RequireAuth>
        }
      />
      <Route
        path="/cases/:caseId"
        element={
          <RequireAuth>
            <CaseDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/matching"
        element={
          <RequireAuth roles={['administrator', 'investigator']}>
            <FaceMatchingPage />
          </RequireAuth>
        }
      />
      <Route
        path="/videos"
        element={
          <RequireAuth roles={['administrator', 'investigator']}>
            <VideoAnalysisPage />
          </RequireAuth>
        }
      />
      <Route
        path="/matches"
        element={
          <RequireAuth roles={['administrator', 'investigator']}>
            <PotentialMatchesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/investigations"
        element={
          <RequireAuth>
            <InvestigationsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/notifications"
        element={
          <RequireAuth>
            <NotificationsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/users"
        element={
          <RequireAuth roles={['administrator']}>
            <UserManagementPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <RequireAuth roles={['administrator']}>
            <AuditLogsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/privacy"
        element={
          <RequireAuth>
            <PrivacySecurityPage />
          </RequireAuth>
        }
      />
      <Route
        path="/reports"
        element={
          <RequireAuth roles={['administrator']}>
            <ReportsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
