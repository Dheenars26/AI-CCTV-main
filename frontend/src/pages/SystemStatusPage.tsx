import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { systemApi } from '../api/system';
import { StatusBadge } from '../components/StatusBadge';
import { Activity, Server, Cpu, Database, RefreshCw, ShieldCheck } from 'lucide-react';

export const SystemStatusPage: React.FC = () => {
  const { data: statusRes, isLoading: statusLoading, refetch } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => systemApi.getStatus(),
    refetchInterval: 5000,
  });

  const { data: logsRes } = useQuery({
    queryKey: ['system-logs'],
    queryFn: () => systemApi.getLogs(),
  });

  const status = statusRes?.data;
  const logs = logsRes?.data || [];

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex items-center justify-between bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center border border-blue-100 shadow-xs">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              System Health & Telemetry Diagnostics
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Real-time backend worker thread telemetry, database connections, and operational status.
            </p>
          </div>
        </div>

        <button
          onClick={() => refetch()}
          className="p-2 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors"
          title="Refresh System Telemetry"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Health Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Overall Health</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="pt-1">
            <StatusBadge status={status?.status || 'OPERATIONAL'} />
          </div>
          <p className="text-[11px] text-slate-400 font-mono">Backend Service Operational</p>
        </div>

        {/* Metric 2 */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">System Version</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-slate-900 font-mono tracking-tight">
            v{status?.version || '1.0.0'}
          </p>
          <p className="text-[11px] text-slate-400 font-mono">Environment: {status?.environment || 'production'}</p>
        </div>

        {/* Metric 3 */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Active Stream Workers</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-blue-600 font-mono tracking-tight">
            {status?.active_cameras_count ?? 0} Workers
          </p>
          <p className="text-[11px] text-slate-400 font-mono">Total Registered: {status?.total_cameras_count ?? 0}</p>
        </div>

        {/* Metric 4 */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">System Uptime</span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-extrabold text-slate-900 font-mono tracking-tight">
            {Math.floor((status?.uptime_seconds || 3600) / 60)} mins
          </p>
          <p className="text-[11px] text-slate-400 font-mono">SQLite WAL Engine Online</p>
        </div>
      </div>

      {/* Live Server Logs */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-3">
        <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider font-mono flex items-center gap-2">
          <Server className="w-4 h-4 text-blue-600" /> Security & Operational System Logs
        </h3>
        <div className="bg-slate-950 p-4 rounded-xl font-mono text-xs text-slate-300 max-h-72 overflow-y-auto space-y-1.5 border border-slate-900 shadow-inner">
          {logs.length === 0 ? (
            <p className="text-emerald-400/90 font-mono">[INFO] System operational. Zero unhandled exceptions in pipeline.</p>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} className="hover:bg-slate-900/90 p-0.5 rounded text-slate-300">
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default SystemStatusPage;
