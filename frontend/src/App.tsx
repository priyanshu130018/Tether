import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './components/ui/Toast';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './layouts/AppLayout';

const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const TargetsListPage = lazy(() => import('./pages/TargetsListPage').then(m => ({ default: m.TargetsListPage })));
const TargetCreatePage = lazy(() => import('./pages/TargetCreatePage').then(m => ({ default: m.TargetCreatePage })));
const TargetDetailPage = lazy(() => import('./pages/TargetDetailPage').then(m => ({ default: m.TargetDetailPage })));
const AlertsPage = lazy(() => import('./pages/AlertsPage').then(m => ({ default: m.AlertsPage })));
const NotificationChannelsPage = lazy(() => import('./pages/NotificationChannelsPage').then(m => ({ default: m.NotificationChannelsPage })));
const JobsPage = lazy(() => import('./pages/JobsPage').then(m => ({ default: m.JobsPage })));
const WorkersPage = lazy(() => import('./pages/WorkersPage').then(m => ({ default: m.WorkersPage })));
const TeamManagementPage = lazy(() => import('./pages/TeamManagementPage').then(m => ({ default: m.TeamManagementPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const SystemStatusPage = lazy(() => import('./pages/SystemStatusPage').then(m => ({ default: m.SystemStatusPage })));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })));

const LoadingFallback: React.FC = () => (
  <div className="flex items-center justify-center min-h-[400px]">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
  </div>
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 3000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense fallback={<LoadingFallback />}>
            <Routes>
              {/* Public Auth Routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected Application Routes */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<DashboardPage />} />
                <Route path="targets" element={<TargetsListPage />} />
                <Route path="targets/new" element={<TargetCreatePage />} />
                <Route path="targets/:id" element={<TargetDetailPage />} />
                <Route path="alerts" element={<AlertsPage />} />
                <Route path="notifications" element={<NotificationChannelsPage />} />
                <Route path="jobs" element={<JobsPage />} />
                <Route path="workers" element={<WorkersPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="settings/team" element={<TeamManagementPage />} />
                <Route path="settings/system" element={<SystemStatusPage />} />
                <Route path="system" element={<SystemStatusPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
