import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Camera, CameraRuntimeState } from '../types/api';
import { StatusBadge } from './StatusBadge';
import { Maximize2, Minimize2, AlertCircle, RefreshCw, Power, Loader2, VideoOff, Scan, Expand } from 'lucide-react';
import { camerasApi } from '../api/cameras';
import { getCameraStreamBaseUrl } from '../config/apiConfig';

interface CameraStreamPlayerProps {
  camera: Camera;
  runtimeState?: CameraRuntimeState;
  interactive?: boolean;
  fullHeight?: boolean;
  fitMode?: 'contain' | 'cover';
  onFitModeChange?: (mode: 'contain' | 'cover') => void;
}

/**
 * Module-level stream URL registry.
 * Stores the last-known-good stream URL per camera ID so that navigating
 * between pages (unmount/remount) reuses the SAME URL instead of creating
 * a new timestamped one — which caused the browser to open a new MJPEG
 * connection and show "Reconnecting" every time.
 */
const streamUrlRegistry = new Map<number, string>();

/**
 * Returns a stable stream URL for a camera.
 * Only generates a new timestamped URL if forceRefresh is true
 * or the camera has never been seen before.
 */
function getStreamUrl(cameraId: number, forceRefresh = false): string {
  if (!forceRefresh && streamUrlRegistry.has(cameraId)) {
    return streamUrlRegistry.get(cameraId)!;
  }
  const backendBase = getCameraStreamBaseUrl();
  const path = `/api/v1/cameras/${cameraId}/stream`;
  const url = forceRefresh ? `${backendBase}${path}?t=${Date.now()}` : `${backendBase}${path}`;
  streamUrlRegistry.set(cameraId, url);
  return url;
}

/** Clear a camera's cached URL (call when stopping the stream) */
function clearStreamUrl(cameraId: number) {
  streamUrlRegistry.delete(cameraId);
}

export const CameraStreamPlayer: React.FC<CameraStreamPlayerProps> = ({
  camera,
  runtimeState,
  interactive = true,
  fullHeight = false,
  fitMode: controlledFitMode,
  onFitModeChange,
}) => {
  const queryClient = useQueryClient();
  const [internalFitMode, setInternalFitMode] = useState<'contain' | 'cover'>('contain');
  const currentFitMode = controlledFitMode ?? internalFitMode;

  const setFitMode = useCallback((mode: 'contain' | 'cover') => {
    if (onFitModeChange) {
      onFitModeChange(mode);
    } else {
      setInternalFitMode(mode);
    }
  }, [onFitModeChange]);

  const [isLocallyActive, setIsLocallyActive] = useState<boolean>(camera.enabled);
  const [streamUrl, setStreamUrl] = useState<string>(() =>
    camera.enabled ? getStreamUrl(camera.id) : ''
  );
  const [hasError, setHasError] = useState<boolean>(false);
  const [retryCount, setRetryCount] = useState<number>(0);
  const [isFullScreen, setIsFullScreen] = useState<boolean>(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const healthPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullScreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  useEffect(() => {
    setIsLocallyActive(camera.enabled);
    if (camera.enabled) {
      // Force fresh URL so browser initiates new live stream request
      const url = getStreamUrl(camera.id, true);
      setStreamUrl(url);
      setHasError(false);
    } else {
      clearStreamUrl(camera.id);
      setStreamUrl('');
    }
  }, [camera.enabled, camera.id]);

  const isStreamEnabled = isLocallyActive;

  // Cleanup on unmount — promptly close browser streaming socket
  useEffect(() => {
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (healthPollRef.current) clearInterval(healthPollRef.current);
      if (imgRef.current) {
        imgRef.current.src = '';
      }
    };
  }, []);

  const startMutation = useMutation({
    mutationFn: (id: number) => camerasApi.start(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      queryClient.invalidateQueries({ queryKey: ['camera', camera.id] });
      queryClient.invalidateQueries({ queryKey: ['camera-status', camera.id] });
      setHasError(false);
      setRetryCount(0);
      // Force fresh URL so browser reconnects to live MJPEG stream
      const url = getStreamUrl(camera.id, true);
      setStreamUrl(url);
    }
  });

  const stopMutation = useMutation({
    mutationFn: (id: number) => camerasApi.stop(id),
    onSuccess: () => {
      clearStreamUrl(camera.id); // Clear registry so next start gets fresh URL
      setStreamUrl('');
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      queryClient.invalidateQueries({ queryKey: ['camera', camera.id] });
      queryClient.invalidateQueries({ queryKey: ['camera-status', camera.id] });
    }
  });

  const isPending = startMutation.isPending || stopMutation.isPending;

  // Background health-check: auto-recover every 5s if showing error
  useEffect(() => {
    if (healthPollRef.current) {
      clearInterval(healthPollRef.current);
      healthPollRef.current = null;
    }
    if (!isStreamEnabled) return;

    healthPollRef.current = setInterval(() => {
      if (hasError && isStreamEnabled) {
        // Force refresh URL on recovery
        const url = getStreamUrl(camera.id, true);
        setStreamUrl(url);
        setHasError(false);
        setRetryCount(0);
      }
    }, 5000);

    return () => {
      if (healthPollRef.current) clearInterval(healthPollRef.current);
    };
  }, [isStreamEnabled, hasError, camera.id]);

  // Tab visibility: reconnect when user returns to tab (only if error)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isStreamEnabled && hasError) {
        const url = getStreamUrl(camera.id, true);
        setStreamUrl(url);
        setHasError(false);
        setRetryCount(0);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [isStreamEnabled, hasError, camera.id]);

  // Clear error when runtime status is CONNECTED
  useEffect(() => {
    if (isStreamEnabled && runtimeState?.status === 'CONNECTED') {
      setHasError(false);
    }
  }, [runtimeState?.status, isStreamEnabled]);

  const handleImageError = useCallback(() => {
    if (!isStreamEnabled) {
      setHasError(true);
      return;
    }
    const nextRetry = retryCount + 1;
    setRetryCount(nextRetry);
    const backoffMs = Math.min(4000, 500 * Math.pow(1.5, retryCount));

    if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    retryTimerRef.current = setTimeout(() => {
      // Force-refresh URL on retry so browser opens a new connection
      const url = getStreamUrl(camera.id, true);
      setStreamUrl(url);
      setHasError(false);
    }, backoffMs);
  }, [isStreamEnabled, retryCount, camera.id]);

  const handleTurnOn = async () => {
    setIsLocallyActive(true);
    setHasError(false);
    // Set fresh stream URL immediately so browser initiates new stream request
    const url = getStreamUrl(camera.id, true);
    setStreamUrl(url);
    try {
      await startMutation.mutateAsync(camera.id);
    } catch {
      setHasError(true);
      setStreamUrl('');
    }
  };

  const handleTurnOff = async () => {
    setIsLocallyActive(false);
    clearStreamUrl(camera.id);
    setStreamUrl('');
    try {
      await stopMutation.mutateAsync(camera.id);
    } catch {
      setIsLocallyActive(true);
      const url = getStreamUrl(camera.id, true);
      setStreamUrl(url);
    }
  };

  const handleManualReconnect = () => {
    setHasError(false);
    setRetryCount(0);
    // Always force-refresh on manual reconnect
    const url = getStreamUrl(camera.id, true);
    setStreamUrl(url);
  };

  const toggleFullScreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
        setIsFullScreen(false);
      } else if (containerRef.current?.requestFullscreen) {
        await containerRef.current.requestFullscreen();
        setIsFullScreen(true);
      } else {
        setIsFullScreen((prev) => !prev);
      }
    } catch {
      setIsFullScreen((prev) => !prev);
    }
  }, []);

  const containerClasses = isFullScreen
    ? 'fixed inset-0 z-50 bg-black flex flex-col justify-center'
    : fullHeight
    ? 'w-full h-full flex-1 flex flex-col min-h-0 relative rounded-2xl overflow-hidden border border-slate-200/90 bg-slate-950 shadow-card'
    : 'w-full aspect-video relative rounded-2xl overflow-hidden border border-slate-200/90 bg-slate-950 shadow-card';

  return (
    <div
      ref={containerRef}
      className={`relative group overflow-hidden transition-all ${containerClasses}`}
    >
      {/* Top Overlay Header */}
      <div className="absolute top-0 inset-x-0 p-3 bg-gradient-to-b from-black/85 via-black/40 to-transparent z-10 flex items-center justify-between pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="font-semibold text-xs text-white tracking-wide truncate max-w-[180px]">
            {camera.name}
          </span>
          <span className="text-[10px] font-mono text-slate-400 bg-slate-900/80 px-1.5 py-0.5 rounded border border-slate-700">
            {camera.camera_number}
          </span>
        </div>
        <div className="pointer-events-auto flex items-center gap-2">
          <StatusBadge status={runtimeState?.status || (isStreamEnabled ? 'CONNECTED' : 'OFFLINE')} />
          {interactive && (
            <button
              type="button"
              onClick={toggleFullScreen}
              className="p-1.5 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-700 transition-colors opacity-0 group-hover:opacity-100"
              title={isFullScreen ? "Exit Fullscreen" : "Full Screen Mode"}
            >
              {isFullScreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* Stream Display / Fallback */}
      <div className="w-full h-full flex-1 flex items-center justify-center relative overflow-hidden bg-slate-950">
        {isStreamEnabled && streamUrl && !hasError ? (
          <img
            ref={imgRef}
            src={streamUrl}
            alt={camera.name}
            onError={handleImageError}
            decoding="async"
            style={{ transform: 'translateZ(0)', willChange: 'transform' }}
            className={`w-full h-full select-none ${
              currentFitMode === 'contain' ? 'object-contain' : 'object-cover'
            }`}
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-4 text-center space-y-2 text-slate-400 relative z-20">
            {hasError && isStreamEnabled ? (
              <>
                <AlertCircle className="w-8 h-8 text-red-400 animate-pulse" />
                <p className="text-xs text-red-400 font-medium">Stream Disconnected</p>
                <p className="text-[11px] text-slate-500">Auto-reconnecting…</p>
                <div className="flex items-center gap-2 mt-1">
                  <button
                    type="button"
                    onClick={handleManualReconnect}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 rounded-lg flex items-center gap-1.5 border border-slate-700 cursor-pointer"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Reconnect Stream
                  </button>
                  <button
                    type="button"
                    onClick={handleTurnOff}
                    disabled={isPending}
                    className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-xs text-red-400 rounded-lg flex items-center gap-1.5 border border-red-500/40 cursor-pointer disabled:opacity-50"
                  >
                    <Power className="w-3.5 h-3.5" /> Turn Off
                  </button>
                </div>
              </>
            ) : !isStreamEnabled ? (
              <>
                <div className="p-2.5 rounded-full bg-slate-900 border border-slate-800 text-slate-500">
                  <VideoOff className="w-6 h-6" />
                </div>
                <div className="space-y-0.5">
                  <p className="text-xs sm:text-sm font-semibold text-slate-300">Camera Stream is Off</p>
                  <p className="text-[11px] text-slate-500">Click below to turn on camera stream</p>
                </div>
                <button
                  type="button"
                  onClick={handleTurnOn}
                  disabled={isPending}
                  className="mt-1 px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition-all disabled:opacity-50 active:scale-95 cursor-pointer relative z-30"
                >
                  {startMutation.isPending ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Turning On...</>
                  ) : (
                    <><Power className="w-4 h-4" /> Turn On Camera</>
                  )}
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
                <span>Connecting to Camera Stream...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Controls Overlay (Active only when stream is playing) */}
      {interactive && isStreamEnabled && !hasError && (
        <div className="absolute bottom-0 inset-x-0 p-2.5 bg-gradient-to-t from-black/85 via-black/35 to-transparent z-10 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <div className="flex items-center gap-2 text-[11px] font-mono text-slate-300 pointer-events-auto">
            <span>FPS: {runtimeState?.fps || (camera.enabled ? 15 : 0)}</span>
            <span>•</span>
            <span>{(camera.source_type || 'RTSP').toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-2 pointer-events-auto">
            <button
              type="button"
              onClick={() => setFitMode(currentFitMode === 'contain' ? 'cover' : 'contain')}
              className="px-2.5 py-1 bg-slate-900/80 hover:bg-slate-800 text-slate-300 text-xs rounded-lg border border-slate-700 transition-colors flex items-center gap-1.5 font-medium"
              title={currentFitMode === 'contain' ? "Switch to Fill Screen" : "Switch to Full Frame View (Uncropped)"}
            >
              {currentFitMode === 'contain' ? (
                <><Expand className="w-3.5 h-3.5 text-cyan-400" /> <span>Fill Screen</span></>
              ) : (
                <><Scan className="w-3.5 h-3.5 text-cyan-400" /> <span>Full View</span></>
              )}
            </button>
            <button
              type="button"
              onClick={handleTurnOff}
              disabled={isPending}
              className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/40 text-xs rounded-lg flex items-center gap-1.5 font-semibold transition-colors disabled:opacity-50"
              title="Turn Off Camera Stream"
            >
              {stopMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Power className="w-3.5 h-3.5" />}
              <span>Turn Off</span>
            </button>
            <button
              type="button"
              onClick={toggleFullScreen}
              className="p-1.5 bg-slate-900/80 hover:bg-slate-800 text-slate-200 rounded-lg border border-slate-700 transition-colors"
              title={isFullScreen ? "Exit Fullscreen" : "Full Screen Mode"}
            >
              {isFullScreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
