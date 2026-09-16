import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { AlertBanner } from './components/AlertBanner';

import { MobileNotificationToast } from './components/MobileNotificationToast';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';

const LiveMonitoringPage = lazy(() => import('./pages/LiveMonitoringPage').then(m => ({ default: m.LiveMonitoringPage })));
const CameraListPage = lazy(() => import('./pages/CameraListPage').then(m => ({ default: m.CameraListPage })));
const CameraDetailPage = lazy(() => import('./pages/CameraDetailPage').then(m => ({ default: m.CameraDetailPage })));
const AlertListPage = lazy(() => import('./pages/AlertListPage').then(m => ({ default: m.AlertListPage })));
const AlertDetailPage = lazy(() => import('./pages/AlertDetailPage').then(m => ({ default: m.AlertDetailPage })));
const DetectionHistoryPage = lazy(() => import('./pages/DetectionHistoryPage').then(m => ({ default: m.DetectionHistoryPage })));
const EvidencePage = lazy(() => import('./pages/EvidencePage').then(m => ({ default: m.EvidencePage })));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage').then(m => ({ default: m.NotificationsPage })));
const SystemStatusPage = lazy(() => import('./pages/SystemStatusPage').then(m => ({ default: m.SystemStatusPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const ZoneManagementPage = lazy(() => import('./pages/ZoneManagementPage').then(m => ({ default: m.ZoneManagementPage })));

const PageFallback: React.FC = () => (
  <div className="flex items-center justify-center min-h-[60vh] text-slate-500 font-sans text-xs font-medium animate-pulse">
    Loading module...
  </div>
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5000,
    },
  },
});

const ProtectedLayout: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-3 text-slate-600 text-xs font-sans">
        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <span className="font-semibold text-slate-700">Authenticating Gateway...</span>
        <button
          onClick={() => {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
          }}
          className="mt-2 text-[11px] text-blue-600 hover:text-blue-800 hover:underline cursor-pointer"
        >
          Cancel & Return to Login
        </button>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <WebSocketProvider>
      <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
        <MobileNotificationToast />
        <AlertBanner />
        <Navbar />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 p-4 sm:p-6 overflow-y-auto flex flex-col min-h-0 bg-slate-50">
            <Suspense fallback={<PageFallback />}>
              <Outlet />
            </Suspense>
          </main>
        </div>
      </div>
    </WebSocketProvider>
  );
};

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />

                <Route element={<ProtectedLayout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/monitoring" element={<LiveMonitoringPage />} />
                  <Route path="/cameras" element={<CameraListPage />} />
                  <Route path="/notifications" element={<AlertListPage />} />
                  <Route path="/notifications/:id" element={<AlertDetailPage />} />
                  <Route path="/alerts" element={<Navigate to="/notifications" replace />} />
                  <Route path="/alerts/:id" element={<AlertDetailPage />} />
                  <Route path="/detections" element={<DetectionHistoryPage />} />
                  <Route path="/evidence" element={<EvidencePage />} />
                  <Route path="/system" element={<SystemStatusPage />} />
                  <Route path="/zones" element={<ZoneManagementPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
