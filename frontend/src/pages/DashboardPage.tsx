import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { systemApi } from '../api/system';
import { camerasApi } from '../api/cameras';
import { alertsApi } from '../api/alerts';
import { ppeApi } from '../api/ppeApi';
import { CameraStreamPlayer } from '../components/CameraStreamPlayer';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { Camera, Flame, Wind, AlertTriangle, ShieldCheck, ShieldAlert, Activity, Bell, Eye } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getSafeTimestamp } from '../utils/dateUtils';

export const DashboardPage: React.FC = () => {
  const { data: statsRes, isLoading: statsLoading } = useQuery({
    queryKey: ['system-stats'],
    queryFn: () => systemApi.getStats(),
    refetchInterval: 3000,
  });

  const { data: camerasRes, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasApi.list(),
  });

  const { data: alertsRes, isLoading: alertsLoading } = useQuery({
    queryKey: ['alerts', { limit: 6 }],
    queryFn: () => alertsApi.list({ limit: 6 }),
    refetchInterval: 3000,
  });

  const { data: safetyStats } = useQuery({
    queryKey: ['safety-statistics'],
    queryFn: () => ppeApi.getSafetyStatistics(),
    refetchInterval: 3000,
  });

  const stats = statsRes?.data;
  const cameras = camerasRes?.data || [];
  const rawAlerts = alertsRes?.data || [];
  const recentAlerts = React.useMemo(() => {
    return [...rawAlerts].sort((a, b) => getSafeTimestamp(b) - getSafeTimestamp(a));
  }, [rawAlerts]);

  return (
    <div className="space-y-6">
      {/* Overview Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3">
        {/* Total Cameras */}
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">Total Cams</span>
            <div className="w-6 h-6 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Camera className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-slate-900">
            {statsLoading ? '...' : safetyStats?.total_cameras ?? stats?.total_cameras ?? cameras.length}
          </p>
          <div className="text-[10px] text-slate-400 font-medium">System Total</div>
        </div>

        {/* Online Cameras */}
        <div className="bg-white p-3.5 rounded-2xl border border-emerald-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">Online</span>
            <div className="w-6 h-6 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-emerald-600">
            {statsLoading ? '...' : safetyStats?.online_cameras ?? stats?.online_cameras ?? cameras.filter(c => c.enabled).length}
          </p>
          <div className="text-[10px] text-emerald-600/80 font-medium">Active Streams</div>
        </div>

        {/* Offline Cameras */}
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Offline</span>
            <div className="w-6 h-6 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center">
              <Activity className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-slate-500">
            {statsLoading ? '...' : safetyStats?.offline_cameras ?? stats?.offline_cameras ?? cameras.filter(c => !c.enabled).length}
          </p>
          <div className="text-[10px] text-slate-400 font-medium">Standby / Off</div>
        </div>

        {/* Active Fire Alerts */}
        <div className="bg-white p-3.5 rounded-2xl border border-rose-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700">Fire Alerts</span>
            <div className="w-6 h-6 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
              <Flame className="w-3.5 h-3.5 animate-bounce" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-rose-600">
            {safetyStats?.active_fire_alerts ?? stats?.active_fire_alerts ?? 0}
          </p>
          <div className="text-[10px] text-rose-500/80 font-medium">Thermal Alert</div>
        </div>

        {/* Active Smoke Alerts */}
        <div className="bg-white p-3.5 rounded-2xl border border-amber-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">Smoke Alerts</span>
            <div className="w-6 h-6 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Wind className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-amber-600">
            {safetyStats?.active_smoke_alerts ?? stats?.active_smoke_alerts ?? 0}
          </p>
          <div className="text-[10px] text-amber-600/80 font-medium">Aerosol Haze</div>
        </div>

        {/* PPE Violations (24h) */}
        <div className="bg-white p-3.5 rounded-2xl border border-purple-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700">PPE Alert</span>
            <div className="w-6 h-6 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-purple-600">
            {safetyStats?.ppe_violations_24h ?? 0}
          </p>
          <div className="text-[10px] text-purple-500/80 font-medium">Last 24 Hours</div>
        </div>

        {/* Workers Detected */}
        <div className="bg-white p-3.5 rounded-2xl border border-sky-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-sky-700">Workers</span>
            <div className="w-6 h-6 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center">
              <Activity className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-sky-600">
            {safetyStats?.workers_detected_24h ?? 0}
          </p>
          <div className="text-[10px] text-sky-600/80 font-medium">Active Tracked</div>
        </div>

        {/* Zone Violations */}
        <div className="bg-white p-3.5 rounded-2xl border border-orange-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-orange-700">Zones</span>
            <div className="w-6 h-6 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-orange-600">
            {safetyStats?.zone_violations_24h ?? 0}
          </p>
          <div className="text-[10px] text-orange-600/80 font-medium">Breach Count</div>
        </div>

        {/* Critical Incidents */}
        <div className="bg-white p-3.5 rounded-2xl border border-red-200/80 shadow-card hover:shadow-card-hover transition-all space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-red-700">Incidents</span>
            <div className="w-6 h-6 rounded-lg bg-red-50 text-red-600 flex items-center justify-center">
              <Flame className="w-3.5 h-3.5" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-red-600">
            {safetyStats?.critical_incidents_active ?? 0}
          </p>
          <div className="text-[10px] text-red-600/80 font-medium">High Priority</div>
        </div>
      </div>

      {/* Main Grid: Live Camera Stream Grid & Recent Alerts Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Camera Grid (2/3 width) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
              <Camera className="w-4 h-4 text-blue-600" /> Live Stream Monitor
            </h3>
            <Link to="/monitoring" className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-1">
              Open Full Matrix →
            </Link>
          </div>

          {camerasLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[1, 2].map((i) => (
                <div key={i} className="w-full aspect-video bg-slate-200 animate-pulse rounded-2xl" />
              ))}
            </div>
          ) : cameras.length === 0 ? (
            <div className="bg-white p-8 rounded-2xl border border-slate-200/80 text-center text-slate-500 space-y-2 shadow-card">
              <p className="font-medium">No cameras registered in system.</p>
              <Link to="/cameras" className="inline-block text-xs font-semibold text-blue-600 hover:underline">Add New Camera</Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cameras.slice(0, 4).map((cam) => (
                <CameraStreamPlayer key={cam.id} camera={cam} />
              ))}
            </div>
          )}
        </div>

        {/* Recent Notifications Feed (1/3 width) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
              <Bell className="w-4 h-4 text-blue-600" /> Recent Notifications
            </h3>
            <Link to="/notifications" className="text-xs text-blue-600 hover:text-blue-700 font-semibold">
              View All →
            </Link>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-card space-y-2.5 min-h-[350px]">
            {alertsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-xl" />
                ))}
              </div>
            ) : recentAlerts.length === 0 ? (
              <div className="text-center py-12 text-slate-400 space-y-1.5">
                <ShieldCheck className="w-9 h-9 text-emerald-500 mx-auto" />
                <p className="text-xs font-semibold text-slate-700">No active notifications</p>
                <p className="text-[11px] text-slate-400 font-medium">All camera streams clear</p>
              </div>
            ) : (
              recentAlerts.map((alert) => (
                <Link
                  key={alert.id}
                  to={`/notifications/${alert.id}`}
                  className="block p-3 rounded-xl bg-slate-50/70 hover:bg-slate-100/90 border border-slate-200/70 transition-all space-y-1.5 shadow-xs group"
                  title="Click to view evidence image and remedy"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {alert.class_name === 'fire' ? (
                        <Flame className="w-4 h-4 text-rose-600" />
                      ) : alert.class_name === 'smoke' ? (
                        <Wind className="w-4 h-4 text-amber-600" />
                      ) : (
                        <ShieldAlert className="w-4 h-4 text-blue-600" />
                      )}
                      <span className="font-bold text-xs text-slate-900 uppercase">
                        {alert.class_name ? `${alert.class_name} Detected` : 'Security Incident'}
                      </span>
                    </div>
                    <SeverityBadge severity={alert.severity || alert.state || (alert.class_name === 'fire' ? 'CRITICAL' : 'WARNING')} />
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-500 font-medium">
                    <span>{alert.camera_name || `Camera #${alert.camera_id}`}</span>
                    <span className="font-mono">
                      {Math.round((alert.max_confidence ?? alert.latest_confidence ?? alert.confidence ?? 0.85) * 100)}% Confidence
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-slate-200/60 text-[10px] text-blue-600 font-semibold group-hover:text-blue-800">
                    <span className="flex items-center gap-1">
                      <Eye className="w-3 h-3" />
                      Inspect Evidence & Remedy
                    </span>
                    <span>→</span>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
