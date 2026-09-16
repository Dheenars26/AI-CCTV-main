import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { camerasApi } from '../api/cameras';
import { CameraStreamPlayer } from '../components/CameraStreamPlayer';
import { RefreshCw, Camera as CameraIcon, Scan, Expand } from 'lucide-react';

export const LiveMonitoringPage: React.FC = () => {
  const { data: camerasRes, isLoading, refetch } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasApi.list(),
  });

  const [fitMode, setFitMode] = useState<'contain' | 'cover'>('contain');
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);

  const cameras = camerasRes?.data || [];
  const camera = cameras.find((c) => c.id === selectedCameraId) || cameras[0];

  return (
    <div className="flex flex-col flex-1 h-[calc(100vh-6.5rem)] min-h-[500px] w-full gap-3 font-sans">
      {/* Top Stream Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white px-4 py-2.5 rounded-2xl border border-slate-200/80 shadow-card shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shadow-xs">
            <CameraIcon className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                Live Monitoring Feed
              </h2>
              {camera && (
                <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                  {camera.name} ({camera.camera_number})
                </span>
              )}
            </div>
            <p className="text-[11px] text-slate-500 font-medium">
              Real-time video surveillance & AI detection stream
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Multi-Camera Selector */}
          {cameras.length > 1 && (
            <select
              value={camera?.id}
              onChange={(e) => setSelectedCameraId(Number(e.target.value))}
              className="bg-slate-50 border border-slate-300 text-xs text-slate-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium"
            >
              {cameras.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.camera_number})
                </option>
              ))}
            </select>
          )}

          {/* View Mode Toggle: Full Camera View vs Fill Screen */}
          <div className="flex items-center bg-slate-100 rounded-lg p-0.5 border border-slate-200 text-xs font-medium">
            <button
              type="button"
              onClick={() => setFitMode('contain')}
              className={`px-2.5 py-1 rounded-md flex items-center gap-1.5 transition-all text-xs ${
                fitMode === 'contain'
                  ? 'bg-white text-blue-700 font-bold border border-slate-200/80 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Full Camera View: Displays complete uncropped 100% sensor frame"
            >
              <Scan className="w-3.5 h-3.5" />
              <span>Fit View</span>
            </button>
            <button
              type="button"
              onClick={() => setFitMode('cover')}
              className={`px-2.5 py-1 rounded-md flex items-center gap-1.5 transition-all text-xs ${
                fitMode === 'cover'
                  ? 'bg-white text-blue-700 font-bold border border-slate-200/80 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Fill Screen: Stretches to fill entire display container"
            >
              <Expand className="w-3.5 h-3.5" />
              <span>Fill Screen</span>
            </button>
          </div>

          <button
            type="button"
            onClick={() => refetch()}
            className="p-1.5 bg-white hover:bg-slate-50 text-slate-600 hover:text-blue-600 rounded-lg border border-slate-200 shadow-xs transition-colors"
            title="Refresh Camera Connection"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Full Camera View Area */}
      <div className="flex-1 w-full min-h-0 flex flex-col">
        {isLoading ? (
          <div className="w-full h-full flex-1 bg-slate-200 animate-pulse rounded-2xl flex items-center justify-center text-slate-500 text-xs font-medium">
            Loading camera feed...
          </div>
        ) : !camera ? (
          <div className="bg-white p-12 rounded-2xl border border-slate-200/80 text-center text-slate-500 space-y-3 my-auto shadow-card">
            <CameraIcon className="w-12 h-12 text-slate-400 mx-auto" />
            <h3 className="text-base font-semibold text-slate-800">No Active Cameras Connected</h3>
            <p className="text-xs max-w-sm mx-auto text-slate-500">
              Ensure your camera is connected and registered in the Camera List tab.
            </p>
          </div>
        ) : (
          <CameraStreamPlayer
            camera={camera}
            fullHeight={true}
            fitMode={fitMode}
            onFitModeChange={setFitMode}
          />
        )}
      </div>
    </div>
  );
};
