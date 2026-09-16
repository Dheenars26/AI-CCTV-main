import React, { useState, useEffect, useRef } from 'react';
import { zoneApi } from '../api/zoneApi';
import { ppeApi } from '../api/ppeApi';
import { camerasApi } from '../api/cameras';
import { SafetyZone, PPEProfile } from '../types/ppe';
import {
  Shield,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Layers,
  RotateCcw,
  Video,
  VideoOff,
  RefreshCw,
  Info
} from 'lucide-react';
import { getCameraStreamBaseUrl } from '../config/apiConfig';

export const ZoneManagementPage: React.FC = () => {
  const [cameras, setCameras] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<PPEProfile[]>([]);
  const [zones, setZones] = useState<SafetyZone[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null);

  const [zoneName, setZoneName] = useState('');
  const [zoneType, setZoneType] = useState<'HAZARD' | 'RESTRICTED' | 'GENERAL'>('HAZARD');
  const [selectedProfileId, setSelectedProfileId] = useState<number | undefined>(undefined);
  const [polygonCoords, setPolygonCoords] = useState<number[][]>([]);

  const [streamUrl, setStreamUrl] = useState<string>('');
  const [streamError, setStreamError] = useState<boolean>(false);
  const [showGrid, setShowGrid] = useState<boolean>(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedCameraId) {
      loadCameraZones(selectedCameraId);
      const baseUrl = getCameraStreamBaseUrl();
      setStreamUrl(`${baseUrl}/api/v1/cameras/${selectedCameraId}/stream?t=${Date.now()}`);
      setStreamError(false);
    } else {
      setStreamUrl('');
    }
  }, [selectedCameraId]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [camRes, profData] = await Promise.all([
        camerasApi.list(),
        ppeApi.getProfiles()
      ]);
      const camList = camRes?.data || [];
      setCameras(camList);
      setProfiles(profData || []);
      if (camList && camList.length > 0) {
        setSelectedCameraId(camList[0].id);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load cameras/profiles');
    } finally {
      setLoading(false);
    }
  };

  const loadCameraZones = async (camId: number) => {
    try {
      const data = await zoneApi.getZones(camId);
      setZones(data || []);
    } catch (err: any) {
      console.error('Error loading zones:', err);
    }
  };

  const handleRefreshStream = () => {
    if (selectedCameraId) {
      const baseUrl = getCameraStreamBaseUrl();
      setStreamUrl(`${baseUrl}/api/v1/cameras/${selectedCameraId}/stream?t=${Date.now()}`);
      setStreamError(false);
    }
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    const normalizedPoint = [parseFloat(x.toFixed(4)), parseFloat(y.toFixed(4))];
    setPolygonCoords((prev) => [...prev, normalizedPoint]);
  };

  const handleUndoPoint = () => {
    setPolygonCoords((prev) => prev.slice(0, -1));
  };

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Clear canvas so the underlying live camera video stream is visible
    ctx.clearRect(0, 0, w, h);

    // Optional faint guide grid for precision alignment
    if (showGrid) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
    }

    // Draw existing configured zones
    zones.forEach((z) => {
      if (z.polygon_coordinates && z.polygon_coordinates.length >= 3) {
        ctx.beginPath();
        z.polygon_coordinates.forEach((pt, idx) => {
          const px = pt[0] * w;
          const py = pt[1] * h;
          if (idx === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();

        const isRestricted = z.zone_type === 'RESTRICTED';
        const isHazard = z.zone_type === 'HAZARD';

        ctx.strokeStyle = isRestricted ? '#f43f5e' : isHazard ? '#f97316' : '#38bdf8';
        ctx.fillStyle = isRestricted
          ? 'rgba(244, 63, 94, 0.28)'
          : isHazard
          ? 'rgba(249, 115, 22, 0.28)'
          : 'rgba(56, 189, 248, 0.28)';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.fill();

        // Sleek Zone Badge Label
        const firstPt = z.polygon_coordinates[0];
        const labelText = `${z.name} (${z.zone_type})`;
        ctx.font = 'bold 11px system-ui, -apple-system, sans-serif';
        const textMetrics = ctx.measureText(labelText);
        const textWidth = textMetrics.width;
        const lx = Math.max(8, Math.min(w - textWidth - 18, firstPt[0] * w));
        const ly = Math.max(22, Math.min(h - 10, firstPt[1] * h - 8));

        ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
        ctx.fillRect(lx - 4, ly - 14, textWidth + 12, 18);
        ctx.strokeStyle = isRestricted ? '#f43f5e' : isHazard ? '#f97316' : '#38bdf8';
        ctx.lineWidth = 1;
        ctx.strokeRect(lx - 4, ly - 14, textWidth + 12, 18);

        ctx.fillStyle = '#ffffff';
        ctx.fillText(labelText, lx + 2, ly);
      }
    });

    // Draw actively drawn polygon
    if (polygonCoords.length > 0) {
      ctx.beginPath();
      polygonCoords.forEach((pt, idx) => {
        const px = pt[0] * w;
        const py = pt[1] * h;
        if (idx === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });

      if (polygonCoords.length >= 3) {
        ctx.closePath();
        ctx.fillStyle = 'rgba(56, 189, 248, 0.32)';
        ctx.fill();
      }

      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Draw vertex markers with sequence numbers
      polygonCoords.forEach((pt, idx) => {
        const px = pt[0] * w;
        const py = pt[1] * h;

        // Outer glow
        ctx.fillStyle = '#0284c7';
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fill();

        // Inner white point
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(px, py, 3, 0, Math.PI * 2);
        ctx.fill();

        // Sequence badge
        ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
        ctx.fillRect(px + 8, py - 16, 16, 16);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1;
        ctx.strokeRect(px + 8, py - 16, 16, 16);

        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 10px system-ui, sans-serif';
        ctx.fillText(`${idx + 1}`, px + 12, py - 4);
      });
    }
  };

  useEffect(() => {
    drawCanvas();
  }, [polygonCoords, zones, showGrid]);

  const handleSaveZone = async () => {
    if (!selectedCameraId || !zoneName.trim()) {
      setError('Please provide a zone name');
      return;
    }
    if (polygonCoords.length < 3) {
      setError('Polygon must contain at least 3 vertices. Click on the camera viewport to add vertices.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await zoneApi.createZone({
        camera_id: selectedCameraId,
        name: zoneName,
        zone_type: zoneType,
        polygon_coordinates: polygonCoords,
        ppe_profile_id: selectedProfileId,
        enabled: true
      });

      setSuccess(`Safety Zone '${zoneName}' created successfully.`);
      setZoneName('');
      setPolygonCoords([]);
      loadCameraZones(selectedCameraId);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create safety zone');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteZone = async (id: number) => {
    if (!confirm('Are you sure you want to delete this safety zone?')) return;
    try {
      await zoneApi.deleteZone(id);
      if (selectedCameraId) loadCameraZones(selectedCameraId);
    } catch (err: any) {
      setError(err?.message || 'Failed to delete zone');
    }
  };

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId);

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-xs">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Safety Zone & Polygon Rules Management
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Draw custom polygon safety zones directly over live camera viewports and assign PPE profiles.
            </p>
          </div>
        </div>

        {/* Camera Selector */}
        <div className="flex items-center gap-2.5">
          <label className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
            <Video className="w-3.5 h-3.5 text-blue-600" />
            Active Camera:
          </label>
          <select
            value={selectedCameraId || ''}
            onChange={(e) => setSelectedCameraId(Number(e.target.value))}
            className="bg-slate-50 border border-slate-200 text-slate-800 rounded-xl px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 shadow-xs cursor-pointer"
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                CAM-{c.id}: {c.name} ({c.location || 'Default'})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2.5 font-medium shadow-xs">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center gap-2.5 font-medium shadow-xs">
          <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live Camera Viewport & Canvas Drawer */}
        <div className="lg:col-span-2 bg-white border border-slate-200/80 rounded-2xl p-5 shadow-card space-y-3.5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-blue-600" />
              Live Camera Viewport & Zone Marker
            </h2>
            
            <div className="flex items-center gap-2">
              {/* Toggle Grid */}
              <button
                type="button"
                onClick={() => setShowGrid((prev) => !prev)}
                className={`text-xs px-2.5 py-1.5 rounded-xl font-medium transition border shadow-xs flex items-center gap-1.5 ${
                  showGrid
                    ? 'bg-blue-50 text-blue-700 border-blue-200'
                    : 'bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200'
                }`}
                title="Toggle guide grid"
              >
                Grid: {showGrid ? 'ON' : 'OFF'}
              </button>

              {/* Undo Last Point */}
              <button
                type="button"
                onClick={handleUndoPoint}
                disabled={polygonCoords.length === 0}
                className="text-xs bg-slate-50 hover:bg-slate-100 disabled:opacity-40 text-slate-700 border border-slate-200 px-2.5 py-1.5 rounded-xl font-medium transition shadow-xs flex items-center gap-1.5"
                title="Undo last vertex"
              >
                <RotateCcw className="w-3.5 h-3.5 text-slate-500" /> Undo Point
              </button>

              {/* Clear Polygon */}
              <button
                type="button"
                onClick={() => setPolygonCoords([])}
                disabled={polygonCoords.length === 0}
                className="text-xs bg-rose-50 hover:bg-rose-100 disabled:opacity-40 text-rose-700 border border-rose-200 px-2.5 py-1.5 rounded-xl font-medium transition shadow-xs flex items-center gap-1.5"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-500" /> Clear
              </button>

              {/* Refresh Stream */}
              <button
                type="button"
                onClick={handleRefreshStream}
                className="text-xs bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 p-1.5 rounded-xl font-medium transition shadow-xs"
                title="Reload Camera Stream"
              >
                <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
              </button>
            </div>
          </div>

          {/* Viewport Container with Live Camera Image and Transparent Canvas Overlay */}
          <div className="relative aspect-video bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 shadow-xl select-none group">
            {/* Live Camera Stream Underlay */}
            {selectedCamera && streamUrl && !streamError ? (
              <img
                key={`${selectedCamera.id}-${streamUrl}`}
                src={streamUrl}
                alt={selectedCamera.name}
                onError={() => setStreamError(true)}
                decoding="async"
                className="absolute inset-0 w-full h-full object-fill pointer-events-none"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 gap-3 pointer-events-none bg-slate-950/90">
                <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400">
                  <VideoOff className="w-6 h-6" />
                </div>
                <div className="text-center px-4">
                  <p className="text-xs font-semibold text-slate-300">
                    {selectedCamera ? `${selectedCamera.name} Stream Offline` : 'No Camera Selected'}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5 max-w-sm">
                    {selectedCamera
                      ? 'Camera stream is currently inactive or initializing. You can still mark safety zones over the canvas.'
                      : 'Please select an active camera from the dropdown above.'}
                  </p>
                </div>
                {selectedCamera && (
                  <button
                    type="button"
                    onClick={handleRefreshStream}
                    className="pointer-events-auto px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl text-xs font-medium flex items-center gap-1.5 transition shadow-xs"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Reconnect Live Stream
                  </button>
                )}
              </div>
            )}

            {/* Interactive Polygon Drawing Canvas Layer */}
            <canvas
              ref={canvasRef}
              width={640}
              height={360}
              onClick={handleCanvasClick}
              className="absolute inset-0 w-full h-full cursor-crosshair z-10"
            />

            {/* Live Camera Feed Indicator Tag */}
            {selectedCamera && !streamError && (
              <div className="absolute top-3 left-3 z-20 pointer-events-none flex items-center gap-2 bg-slate-950/80 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-700/60 shadow-lg text-[11px]">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-sm shadow-emerald-500/50" />
                <span className="font-bold text-white tracking-wide">{selectedCamera.name}</span>
                <span className="text-slate-400 font-mono text-[10px] uppercase border-l border-slate-700 pl-2">LIVE STREAM</span>
              </div>
            )}

            {/* Helper Guidance Pill */}
            <div className="absolute bottom-3 left-3 z-20 pointer-events-none bg-slate-950/85 backdrop-blur-md px-3 py-1.5 rounded-xl border border-slate-800 text-[11px] text-slate-300 flex items-center gap-2 shadow-md">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
              <span>Click on the camera image to place boundary points (min 3)</span>
            </div>
          </div>

          <div className="text-xs text-slate-500 flex items-center justify-between font-medium">
            <span>
              Vertices Placed: <strong className="text-blue-600 font-bold">{polygonCoords.length}</strong> {polygonCoords.length < 3 ? `(${3 - polygonCoords.length} more required)` : '(Ready to save)'}
            </span>
            <span className="text-slate-400">Clicking on live camera maps normalized coords [0.0 - 1.0]</span>
          </div>
        </div>

        {/* Zone Configuration Form & Camera Zones List */}
        <div className="space-y-6">
          <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-card space-y-4">
            <h2 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
              <Plus className="w-4 h-4 text-blue-600" />
              Configure Safety Zone
            </h2>

            <div className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Zone Name</label>
                <input
                  type="text"
                  placeholder="e.g. Chemical Storage Area"
                  value={zoneName}
                  onChange={(e) => setZoneName(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 shadow-xs"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Zone Type</label>
                <select
                  value={zoneType}
                  onChange={(e: any) => setZoneType(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 shadow-xs cursor-pointer"
                >
                  <option value="HAZARD">HAZARD (Enforces PPE Profile)</option>
                  <option value="RESTRICTED">RESTRICTED (Unauthorized Area Entry)</option>
                  <option value="GENERAL">GENERAL (General Monitoring)</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Associated PPE Profile</label>
                <select
                  value={selectedProfileId || ''}
                  onChange={(e) => setSelectedProfileId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-3 py-2 text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 shadow-xs cursor-pointer"
                >
                  <option value="">None (Use default profile)</option>
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} (Required: {p.required_equipment?.join(', ')})
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="button"
                onClick={handleSaveZone}
                disabled={loading || polygonCoords.length < 3}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-xl text-xs shadow-xs transition cursor-pointer disabled:cursor-not-allowed"
              >
                {loading ? 'Saving Zone...' : 'Save Safety Zone'}
              </button>
            </div>
          </div>

          {/* Active Camera Zones List */}
          <div className="bg-white border border-slate-200/80 rounded-2xl p-5 shadow-card space-y-3.5">
            <h2 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Active Zones for Camera ({zones.length})
            </h2>

            {zones.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No safety zones configured for this camera</p>
            ) : (
              <div className="space-y-2">
                {zones.map((z) => (
                  <div key={z.id} className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-xs text-slate-900">{z.name}</div>
                      <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                          z.zone_type === 'RESTRICTED'
                            ? 'bg-rose-50 text-rose-700 border-rose-200'
                            : z.zone_type === 'HAZARD'
                            ? 'bg-amber-50 text-amber-800 border-amber-200'
                            : 'bg-blue-50 text-blue-700 border-blue-200'
                        }`}>
                          {z.zone_type}
                        </span>
                        <span>{z.polygon_coordinates?.length} vertices</span>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteZone(z.id)}
                      className="p-1.5 bg-white hover:bg-rose-50 text-slate-400 hover:text-rose-600 rounded-lg border border-slate-200 shadow-xs transition cursor-pointer"
                      title="Delete Zone"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ZoneManagementPage;
