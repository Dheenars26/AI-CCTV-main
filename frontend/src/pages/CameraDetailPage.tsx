import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { camerasApi } from '../api/cameras';
import { Camera as CameraType } from '../types/api';
import { CameraStreamPlayer } from '../components/CameraStreamPlayer';
import { StatusBadge } from '../components/StatusBadge';
import { ArrowLeft, Camera as CameraIcon, Activity, ShieldCheck, RefreshCw, Play, Square } from 'lucide-react';

export const CameraDetailPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { id } = useParams<{ id: string }>();
  const cameraId = Number(id);

  const { data: cameraRes, isLoading, refetch } = useQuery({
    queryKey: ['camera', cameraId],
    queryFn: () => camerasApi.get(cameraId),
    enabled: !isNaN(cameraId),
  });

  const { data: statusRes } = useQuery({
    queryKey: ['camera-status', cameraId],
    queryFn: () => camerasApi.getStatus(cameraId),
    enabled: !isNaN(cameraId),
    refetchInterval: 3000,
  });

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const startMutation = useMutation({
    mutationFn: (camId: number) => camerasApi.start(camId),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['camera', cameraId] });
      queryClient.invalidateQueries({ queryKey: ['camera-status', cameraId] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || err?.message || 'Failed to start camera stream.');
    }
  });

  const stopMutation = useMutation({
    mutationFn: (camId: number) => camerasApi.stop(camId),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['camera', cameraId] });
      queryClient.invalidateQueries({ queryKey: ['camera-status', cameraId] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || err?.message || 'Failed to stop camera stream.');
    }
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Partial<CameraType>) => camerasApi.update(cameraId, payload),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['camera', cameraId] });
      queryClient.invalidateQueries({ queryKey: ['camera-status', cameraId] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || err?.message || 'Failed to update camera settings.');
    }
  });

  const camera = cameraRes?.data;
  const runtimeState = statusRes?.data;

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading camera configuration...</div>;
  }

  if (!camera) {
    return <div className="p-8 text-center text-red-400">Camera not found.</div>;
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3">
          <Link to="/cameras" className="p-2 bg-slate-50 hover:bg-slate-100 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <CameraIcon className="w-4 h-4" />
              </div>
              <span>{camera.name}</span>
            </h2>
            <p className="text-xs text-slate-500 font-medium">Camera #{camera.camera_number} • ID {camera.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {camera.enabled ? (
            <button
              onClick={() => stopMutation.mutate(camera.id)}
              disabled={stopMutation.isPending}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 text-xs font-semibold rounded-xl transition-all shadow-xs"
              title="Stop Stream Ingestion"
            >
              <Square className="w-3.5 h-3.5" /> Stop Stream
            </button>
          ) : (
            <button
              onClick={() => startMutation.mutate(camera.id)}
              disabled={startMutation.isPending}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-semibold rounded-xl transition-all shadow-xs"
              title="Start Stream Ingestion"
            >
              <Play className="w-3.5 h-3.5" /> Start Stream
            </button>
          )}

          <StatusBadge status={runtimeState?.status || (camera.enabled ? 'CONNECTED' : 'OFFLINE')} />
          <button onClick={() => refetch()} className="p-2 bg-slate-50 hover:bg-slate-100 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Grid: Stream Player & Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stream Player (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <CameraStreamPlayer camera={camera} runtimeState={runtimeState} />

          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-3">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Stream Endpoint Configuration</h3>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-500 font-medium">Sanitized Stream URL:</span>
                <p className="font-mono text-slate-900 font-semibold truncate mt-0.5" title={camera.sanitized_rtsp_url}>
                  {camera.sanitized_rtsp_url}
                </p>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Source Type:</span>
                <p className="font-mono text-slate-900 font-semibold uppercase mt-0.5">{camera.source_type}</p>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Installed Location:</span>
                <p className="text-slate-900 font-medium mt-0.5">{camera.location || 'Unassigned'}</p>
              </div>
              <div>
                <span className="text-slate-500 font-medium">Capture FPS Target:</span>
                <p className="font-mono text-slate-900 font-semibold mt-0.5">{camera.fps_limit || 25} FPS</p>
              </div>
            </div>
          </div>
        </div>

        {/* Live Metrics & AI Controls Sidebar */}
        <div className="space-y-4">
          {/* AI Detection & Safety Module Controls */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-blue-600" /> AI Detection Pipeline Controls
            </h3>

            <div className="space-y-2.5 text-xs">
              {/* Fire & Smoke Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200/70">
                <div>
                  <span className="font-bold text-slate-900 block">🔥 Fire & Smoke Detection</span>
                  <span className="text-slate-500 text-[11px]">YOLOv8 deep learning inference</span>
                </div>
                <button
                  onClick={() => updateMutation.mutate({ fire_smoke_enabled: !(camera.fire_smoke_enabled ?? true) })}
                  disabled={updateMutation.isPending}
                  className={`px-3 py-1.5 rounded-xl font-semibold text-xs transition-all shadow-xs ${
                    camera.fire_smoke_enabled ?? true
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-slate-200 text-slate-600 border border-slate-300'
                  }`}
                >
                  {camera.fire_smoke_enabled ?? true ? 'ACTIVE' : 'OFF'}
                </button>
              </div>

              {/* PPE Safety Gear Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200/70">
                <div>
                  <span className="font-bold text-slate-900 block">🛡️ Safety PPE Compliance</span>
                  <span className="text-slate-500 text-[11px]">Vest, Helmet & Mask checks</span>
                </div>
                <button
                  onClick={() => updateMutation.mutate({ ppe_enabled: !(camera.ppe_enabled ?? true) })}
                  disabled={updateMutation.isPending}
                  className={`px-3 py-1.5 rounded-xl font-semibold text-xs transition-all shadow-xs ${
                    camera.ppe_enabled ?? true
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-slate-200 text-slate-600 border border-slate-300'
                  }`}
                >
                  {camera.ppe_enabled ?? true ? 'ACTIVE' : 'OFF'}
                </button>
              </div>

              {/* Person Tracking Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200/70">
                <div>
                  <span className="font-bold text-slate-900 block">👤 Worker Tracking</span>
                  <span className="text-slate-500 text-[11px]">Worker count & track persistence</span>
                </div>
                <button
                  onClick={() => updateMutation.mutate({ person_enabled: !(camera.person_enabled ?? true) })}
                  disabled={updateMutation.isPending}
                  className={`px-3 py-1.5 rounded-xl font-semibold text-xs transition-all shadow-xs ${
                    camera.person_enabled ?? true
                      ? 'bg-blue-50 text-blue-700 border border-blue-200'
                      : 'bg-slate-200 text-slate-600 border border-slate-300'
                  }`}
                >
                  {camera.person_enabled ?? true ? 'ACTIVE' : 'OFF'}
                </button>
              </div>

              {/* Safety Zone Polygon Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200/70">
                <div>
                  <span className="font-bold text-slate-900 block">🚷 Safety Zone Breach</span>
                  <span className="text-slate-500 text-[11px]">Hazard & restricted area polygons</span>
                </div>
                <button
                  onClick={() => updateMutation.mutate({ zone_enabled: !(camera.zone_enabled ?? true) })}
                  disabled={updateMutation.isPending}
                  className={`px-3 py-1.5 rounded-xl font-semibold text-xs transition-all shadow-xs ${
                    camera.zone_enabled ?? true
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-slate-200 text-slate-600 border border-slate-300'
                  }`}
                >
                  {camera.zone_enabled ?? true ? 'ACTIVE' : 'OFF'}
                </button>
              </div>
            </div>
          </div>

          {/* Runtime State Metrics Card */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card space-y-4">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-600" /> Runtime Diagnostics
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Real-Time FPS:</span>
                <span className="font-mono text-blue-600 font-bold">{runtimeState?.fps || 0} FPS</span>
              </div>

              <div className="flex justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Stream Resolution:</span>
                <span className="font-mono text-slate-800 font-semibold">{runtimeState?.resolution || '640x480'}</span>
              </div>

              <div className="flex justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Reconnects:</span>
                <span className="font-mono text-slate-800 font-semibold">{runtimeState?.reconnect_attempts || 0}</span>
              </div>

              <div className="flex justify-between p-3 bg-slate-50 rounded-xl border border-slate-100">
                <span className="text-slate-500 font-medium">Ingestion State:</span>
                <span className="font-semibold text-emerald-600">
                  {camera.enabled ? 'ACTIVE WORKER' : 'STANDBY'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CameraDetailPage;
