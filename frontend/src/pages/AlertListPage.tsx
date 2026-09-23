import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsApi } from '../api/alerts';
import { camerasApi } from '../api/cameras';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { PermissionGuard } from '../components/PermissionGuard';
import { Bell, Flame, Wind, CheckCircle, Eye, RefreshCw, Filter, MapPin, Mail, ShieldAlert, Wrench, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { NotificationsPage as EmailDispatchView } from './NotificationsPage';
import { getSafeTimestamp, formatSafeDateTime } from '../utils/dateUtils';

export const AlertListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'notifications' | 'dispatch'>('notifications');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [classFilter, setClassFilter] = useState<string>('');

  const { data: camerasRes } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasApi.list(),
  });

  const cameraMap = useMemo(() => {
    const map: Record<number, any> = {};
    (camerasRes?.data || []).forEach((c: any) => {
      map[c.id] = c;
    });
    return map;
  }, [camerasRes]);

  const { data: alertsRes, isLoading, refetch } = useQuery({
    queryKey: ['alerts', { status: statusFilter, class_name: classFilter }],
    queryFn: () => alertsApi.list({ status: statusFilter || undefined, class_name: classFilter || undefined }),
    refetchInterval: 3000,
  });

  const acknowledgeMutation = useMutation({
    mutationFn: (id: string | number) => alertsApi.acknowledge(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['system-stats'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.error?.message || 'Failed to acknowledge notification. Please check permissions.');
    }
  });

  const resolveMutation = useMutation({
    mutationFn: (id: string | number) => alertsApi.resolve(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['system-stats'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.error?.message || 'Failed to resolve notification. Please check permissions.');
    }
  });

  const resolveAllMutation = useMutation({
    mutationFn: () => alertsApi.resolveAll(),
    onSuccess: () => {
      localStorage.setItem('cctv_notif_cleared_at', Date.now().toString());
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['system-stats'] });
    },
    onError: (error: any) => {
      alert(error?.response?.data?.error?.message || 'Failed to clear all notifications. Please check permissions.');
    }
  });

  const alerts = useMemo(() => {
    return [...(alertsRes?.data || [])].sort((a, b) => getSafeTimestamp(b) - getSafeTimestamp(a));
  }, [alertsRes?.data]);
  const activeCount = alerts.filter(a => a.state !== 'RESOLVED' && a.status !== 'RESOLVED' && a.state !== 'CLEARED').length;

  return (
    <div className="space-y-6">
      {/* Top Tab Bar & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-xs">
            <Bell className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <span>Incident Notifications</span>
              {activeCount > 0 && (
                <span className="text-[11px] font-extrabold bg-rose-50 text-rose-700 px-2 py-0.5 rounded-full border border-rose-200">
                  {activeCount} Active
                </span>
              )}
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">Real-time threat notification log, evidence snapshot records, and operator action remedy resolution.</p>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center p-1 bg-slate-100 rounded-xl border border-slate-200/80 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('notifications')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === 'notifications'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Bell className="w-3.5 h-3.5" />
            <span>Incident Notifications ({alerts.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('dispatch')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg transition-all ${
              activeTab === 'dispatch'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Mail className="w-3.5 h-3.5" />
            <span>Email Dispatch & SMTP</span>
          </button>
        </div>
      </div>

      {activeTab === 'dispatch' ? (
        <EmailDispatchView />
      ) : (
        <>
          {/* Action Bar & Filter Controls */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-card">
            <div className="text-xs text-slate-500 flex-1 min-w-0">
              Click any notification row to view high-resolution <span className="font-semibold text-slate-800">evidence snapshot</span> and execute <span className="font-semibold text-blue-600">action remedy</span>.
            </div>

            <div className="flex items-center gap-2.5 shrink-0 flex-wrap sm:flex-nowrap">
              <PermissionGuard permission="alerts:write">
                <button
                  onClick={() => {
                    if (confirm('Are you sure you want to clear and resolve all active notifications?')) {
                      resolveAllMutation.mutate();
                    }
                  }}
                  disabled={resolveAllMutation.isPending}
                  className="h-9 px-3.5 bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white font-semibold text-xs rounded-xl shadow-xs inline-flex items-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer shrink-0"
                  title="Clear all active fire and smoke notifications instantly"
                >
                  <Trash2 className={`w-3.5 h-3.5 ${resolveAllMutation.isPending ? 'animate-spin' : ''}`} />
                  <span>{resolveAllMutation.isPending ? 'Clearing...' : 'Clear All'}</span>
                </button>
              </PermissionGuard>

              {/* Status Filter */}
              <div className="h-9 inline-flex items-center gap-1.5 bg-slate-50 px-3 rounded-xl border border-slate-200 shrink-0">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-transparent text-xs text-slate-700 font-medium focus:outline-none cursor-pointer h-full pr-1"
                >
                  <option value="">All Statuses</option>
                  <option value="NEW">NEW</option>
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                  <option value="CLEARED">CLEARED</option>
                  <option value="RESOLVED">RESOLVED</option>
                </select>
              </div>

              {/* Type Filter */}
              <select
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
                className="h-9 bg-slate-50 border border-slate-200 rounded-xl px-3 text-xs text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer shrink-0"
              >
                <option value="">All Threat Types</option>
                <option value="fire">Fire</option>
                <option value="smoke">Smoke</option>
              </select>

              <button
                onClick={() => refetch()}
                className="h-9 w-9 inline-flex items-center justify-center bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors shrink-0 cursor-pointer"
                title="Refresh Notification Feed"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

      {/* Notification Table */}
      <div className="bg-white rounded-2xl overflow-hidden border border-slate-200/80 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-bold text-[11px] tracking-wider border-b border-slate-200/80">
              <tr>
                <th className="px-3 py-3">Event ID</th>
                <th className="px-3 py-3">Threat Class</th>
                <th className="px-3 py-3">Camera</th>
                <th className="px-3 py-3">Location</th>
                <th className="px-2.5 py-3">Severity</th>
                <th className="px-2.5 py-3">Confidence</th>
                <th className="px-2.5 py-3">Status</th>
                <th className="px-3 py-3 text-right whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">Loading security notification logs...</td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <CheckCircle className="w-8 h-8 text-emerald-500/60" />
                      <span className="font-medium text-slate-600">No security notifications matching filter criteria.</span>
                      <span className="text-[11px] text-slate-400">All camera streams are currently safe and nominal.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                alerts.map((alert) => (
                  <tr key={alert.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-3 py-2.5 font-mono font-semibold">
                      <Link
                        to={`/notifications/${alert.id}`}
                        className="text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1 font-mono font-bold"
                        title="Click to view evidence image and remedy"
                      >
                        {alert.alert_id || alert.id}
                      </Link>
                      <div className="text-[11px] text-slate-400 font-sans font-normal mt-0.5">
                        {formatSafeDateTime(alert.triggered_at || alert.start_time || (alert as any).created_at)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Link
                        to={`/notifications/${alert.id}`}
                        className="flex items-center gap-1.5 font-bold uppercase hover:opacity-80 transition-opacity"
                        title="Click to view evidence image and remedy"
                      >
                        {alert.class_name === 'fire' ? (
                          <div className="flex items-center gap-1 text-rose-600">
                            <Flame className="w-4 h-4 text-rose-600" />
                            <span>Fire</span>
                          </div>
                        ) : alert.class_name === 'smoke' ? (
                          <div className="flex items-center gap-1 text-amber-600">
                            <Wind className="w-4 h-4 text-amber-600" />
                            <span>Smoke</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 text-blue-600">
                            <ShieldAlert className="w-4 h-4 text-blue-600" />
                            <span>{alert.class_name || 'Incident'}</span>
                          </div>
                        )}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 font-medium text-slate-700">
                      {alert.camera_name || cameraMap[alert.camera_id]?.name || `Camera #${alert.camera_id}`}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5 text-slate-700 font-medium">
                        <MapPin className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                        <span className="truncate max-w-[140px]" title={alert.camera_location || alert.location || cameraMap[alert.camera_id]?.location || 'Unassigned'}>
                          {alert.camera_location || alert.location || cameraMap[alert.camera_id]?.location || 'Unassigned'}
                        </span>
                      </div>
                    </td>
                    <td className="px-2.5 py-2.5">
                      <SeverityBadge severity={alert.severity || alert.state || (alert.class_name === 'fire' ? 'CRITICAL' : 'WARNING')} />
                    </td>
                    <td className="px-2.5 py-2.5 font-mono text-blue-600 font-bold">
                      {Math.round((alert.max_confidence || alert.confidence || 0.85) * 100)}%
                    </td>
                    <td className="px-2.5 py-2.5">
                      <StatusBadge status={alert.state || alert.status || 'NEW'} />
                    </td>
                    <td className="px-3 py-2.5 text-right whitespace-nowrap align-middle">
                      <div className="inline-flex items-center justify-end gap-2">
                        <Link
                          to={`/notifications/${alert.id}`}
                          className="px-2.5 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl inline-flex items-center gap-1.5 font-semibold border border-blue-200 transition-colors shadow-xs"
                          title="Click to view evidence image and remedy"
                        >
                          <Eye className="w-3.5 h-3.5 text-blue-600" />
                          <span>Evidence & Remedy</span>
                        </Link>

                        <PermissionGuard permission="alerts:write">
                          {(alert.status === 'NEW' || alert.state === 'ALERT_SENT') && (
                            <button
                              onClick={() => acknowledgeMutation.mutate(alert.id || (alert as any).alert_id)}
                              disabled={acknowledgeMutation.isPending}
                              className="px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-800 rounded-xl font-semibold border border-amber-200 disabled:opacity-50 transition-colors cursor-pointer"
                            >
                              {acknowledgeMutation.isPending ? 'Working...' : 'Acknowledge'}
                            </button>
                          )}
                          {alert.status !== 'RESOLVED' && alert.state !== 'RESOLVED' && alert.state !== 'CLEARED' && (
                            <button
                              onClick={() => resolveMutation.mutate(alert.id || (alert as any).alert_id)}
                              disabled={resolveMutation.isPending}
                              className="px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-xl font-semibold border border-emerald-200 disabled:opacity-50 transition-colors cursor-pointer"
                            >
                              {resolveMutation.isPending ? 'Resolving...' : 'Resolve'}
                            </button>
                          )}
                        </PermissionGuard>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )}
</div>
  );
};

export default AlertListPage;
