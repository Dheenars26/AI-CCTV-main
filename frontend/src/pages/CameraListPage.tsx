import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { camerasApi } from '../api/cameras';
import { CameraCreatePayload } from '../types/api';
import { StatusBadge } from '../components/StatusBadge';
import { PermissionGuard } from '../components/PermissionGuard';
import { Camera, Plus, Play, Square, Trash2, Eye, RefreshCw, X } from 'lucide-react';
import { Link } from 'react-router-dom';

export const CameraListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [formData, setFormData] = useState<CameraCreatePayload>({
    name: '',
    camera_number: '',
    rtsp_url: '',
    source_type: 'rtsp',
    location: '',
    enabled: false,
    fire_smoke_enabled: true,
    ppe_enabled: true,
    person_enabled: true,
    zone_enabled: true
  });

  const { data: camerasRes, isLoading, refetch } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasApi.list(),
  });

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (payload: CameraCreatePayload) => camerasApi.create(payload),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      setIsModalOpen(false);
      setFormData({
        name: '',
        camera_number: '',
        rtsp_url: '',
        source_type: 'rtsp',
        location: '',
        enabled: false,
        fire_smoke_enabled: true,
        ppe_enabled: true,
        person_enabled: true,
        zone_enabled: true
      });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Failed to create camera.');
    }
  });

  const startMutation = useMutation({
    mutationFn: (id: number) => camerasApi.start(id),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Failed to start camera stream.');
    }
  });

  const stopMutation = useMutation({
    mutationFn: (id: number) => camerasApi.stop(id),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Failed to stop camera stream.');
    }
  });

  const [isConfirmDeleteAllOpen, setIsConfirmDeleteAllOpen] = useState<boolean>(false);

  const deleteAllMutation = useMutation({
    mutationFn: () => camerasApi.deleteAll(),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      setIsConfirmDeleteAllOpen(false);
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Failed to delete all cameras.');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => camerasApi.delete(id),
    onSuccess: () => {
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.error?.message || err?.response?.data?.detail || err?.message || 'Failed to delete camera.');
    }
  });

  const cameras = camerasRes?.data || [];

  return (
    <div className="space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-card">
        <div>
          <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Camera className="w-4 h-4" />
            </div>
            <span>Camera Management</span>
          </h2>
          <p className="text-xs text-slate-500 font-medium">Manage CCTV stream sources, AI detection pipelines, and status.</p>
        </div>

        <div className="flex items-center gap-2.5">
          <PermissionGuard permission="cameras:write">
            <div className="flex items-center gap-2">
              {cameras.length > 0 && (
                <button
                  onClick={() => setIsConfirmDeleteAllOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold rounded-xl transition-all shadow-xs"
                  title="Remove all registered cameras from system"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Remove All
                </button>
              )}

              <button
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl transition-all shadow-sm hover:shadow"
              >
                <Plus className="w-4 h-4" /> Add Camera
              </button>
            </div>
          </PermissionGuard>

          <button
            onClick={() => refetch()}
            className="p-2 bg-white hover:bg-slate-50 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors"
            title="Refresh Camera List"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center justify-between text-xs text-rose-700 font-medium shadow-xs">
          <span>⚠️ {errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-800 font-bold">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Camera Table */}
      <div className="bg-white rounded-2xl overflow-hidden border border-slate-200/80 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-bold border-b border-slate-200">
              <tr>
                <th className="p-4">Camera Name</th>
                <th className="p-4">Number</th>
                <th className="p-4">Source Type</th>
                <th className="p-4">Stream Endpoint</th>
                <th className="p-4">Location</th>
                <th className="p-4">Active AI Modules</th>
                <th className="p-4">Status</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400 font-medium">Loading cameras...</td>
                </tr>
              ) : cameras.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-12 text-center text-slate-500 font-medium">
                    <Camera className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                    No cameras registered yet. Click "Add Camera" to configure a stream.
                  </td>
                </tr>
              ) : (
                cameras.map((cam) => (
                  <tr key={cam.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="p-4 font-bold text-slate-900">{cam.name}</td>
                    <td className="p-4 font-mono text-slate-600">{cam.camera_number}</td>
                    <td className="p-4 uppercase font-mono text-slate-600 font-semibold">{cam.source_type}</td>
                    <td className="p-4 font-mono text-slate-500 max-w-[200px] truncate" title={cam.sanitized_rtsp_url}>
                      {cam.sanitized_rtsp_url}
                    </td>
                    <td className="p-4 text-slate-600">{cam.location || 'N/A'}</td>
                    <td className="p-4">
                      <div className="flex flex-wrap gap-1">
                        {cam.fire_smoke_enabled !== false && (
                          <span className="px-2 py-0.5 bg-rose-50 text-rose-700 border border-rose-200 rounded text-[10px] font-semibold">
                            🔥 Fire/Smoke
                          </span>
                        )}
                        {cam.ppe_enabled !== false && (
                          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded text-[10px] font-semibold">
                            🛡️ Safety PPE
                          </span>
                        )}
                        {cam.zone_enabled !== false && (
                          <span className="px-2 py-0.5 bg-amber-50 text-amber-800 border border-amber-200 rounded text-[10px] font-semibold">
                            🚷 Safety Zones
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="p-4">
                      {cam.enabled ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
                          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                          ON (Active)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          <span className="w-2 h-2 rounded-full bg-slate-400" />
                          OFF (Stopped)
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-right space-x-1.5">
                      <Link
                        to={`/cameras/${cam.id}`}
                        className="p-1.5 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-600 rounded-lg inline-block border border-slate-200 transition-colors shadow-xs"
                        title="View Camera Details"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </Link>

                      <PermissionGuard permission="cameras:write">
                        {cam.enabled ? (
                          <button
                            onClick={() => stopMutation.mutate(cam.id)}
                            disabled={stopMutation.isPending || startMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 disabled:opacity-50 text-amber-800 rounded-xl border border-amber-200 transition-all text-xs font-semibold shadow-xs"
                            title="Turn OFF Camera"
                          >
                            <Square className={`w-3 h-3 fill-amber-600 text-amber-600 ${stopMutation.isPending ? 'animate-pulse' : ''}`} />
                            <span>Turn OFF</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => startMutation.mutate(cam.id)}
                            disabled={startMutation.isPending || stopMutation.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-50 text-emerald-700 rounded-xl border border-emerald-200 transition-all text-xs font-semibold shadow-xs"
                            title="Turn ON Camera"
                          >
                            <Play className={`w-3 h-3 fill-emerald-600 text-emerald-600 ${startMutation.isPending ? 'animate-pulse' : ''}`} />
                            <span>Turn ON</span>
                          </button>
                        )}

                        <button
                          onClick={() => {
                            if (confirm(`Delete camera '${cam.name}'?`)) deleteMutation.mutate(cam.id);
                          }}
                          className="p-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg border border-rose-200 transition-colors shadow-xs"
                          title="Delete Camera"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </PermissionGuard>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Registration Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-xl w-full border border-slate-200 shadow-2xl text-slate-900 flex flex-col max-h-[92vh] sm:max-h-[88vh] my-auto overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Pinned Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 shrink-0 bg-white">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-100">
                  <Camera className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm sm:text-base font-bold text-slate-900">Register Camera Source</h3>
                  <p className="text-[11px] text-slate-500 font-medium">Add an RTSP CCTV stream, USB webcam, or local video file.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1.5 rounded-xl hover:bg-slate-100 transition-colors"
                title="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Form Body */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate(formData);
              }}
              className="flex flex-col flex-1 min-h-0 overflow-hidden"
            >
              <div className="overflow-y-auto px-5 py-4 space-y-3.5 text-xs flex-1">
                {/* Name and Code */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Camera Name</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                      placeholder="e.g. Main Entrance Hall"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Camera Number / Code</label>
                    <input
                      type="text"
                      value={formData.camera_number}
                      onChange={(e) => setFormData({ ...formData, camera_number: e.target.value })}
                      required
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                      placeholder="e.g. CAM-01"
                    />
                  </div>
                </div>

                {/* Source Type and Location */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Source Type</label>
                    <select
                      value={formData.source_type}
                      onChange={(e) => setFormData({ ...formData, source_type: e.target.value as any })}
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                    >
                      <option value="webcam">Laptop / USB Webcam (Device Index)</option>
                      <option value="rtsp">RTSP IP Camera Stream</option>
                      <option value="file">Local MP4 Video File</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-700 font-semibold mb-1">Location / Zone</label>
                    <input
                      type="text"
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-900 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                      placeholder="e.g. Sector 2 Workshop"
                    />
                  </div>
                </div>

                {/* RTSP / Stream Address */}
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">
                    {formData.source_type === 'webcam'
                      ? 'Webcam Device Index (0 = Default Laptop Camera)'
                      : formData.source_type === 'file'
                      ? 'Video File Path (e.g. demo.mp4)'
                      : 'RTSP Stream URL'}
                  </label>
                  <input
                    type="text"
                    value={formData.rtsp_url}
                    onChange={(e) => setFormData({ ...formData, rtsp_url: e.target.value })}
                    required
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl p-2.5 text-slate-900 font-mono focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
                    placeholder={
                      formData.source_type === 'webcam'
                        ? '0'
                        : formData.source_type === 'file'
                        ? 'demo.mp4'
                        : 'rtsp://admin:pass@192.168.1.100:554/Streaming/Channels/101'
                    }
                  />
                </div>

                {/* AI Modules Checklist */}
                <div className="pt-2 border-t border-slate-100">
                  <p className="font-semibold text-slate-700 mb-2">Enable AI Detection Pipelines</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <label className="flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={formData.fire_smoke_enabled}
                        onChange={(e) => setFormData({ ...formData, fire_smoke_enabled: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium text-slate-800 text-[11px]">Fire & Smoke</span>
                    </label>
                    <label className="flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={formData.ppe_enabled}
                        onChange={(e) => setFormData({ ...formData, ppe_enabled: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium text-slate-800 text-[11px]">Worker PPE</span>
                    </label>
                    <label className="flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={formData.person_enabled}
                        onChange={(e) => setFormData({ ...formData, person_enabled: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium text-slate-800 text-[11px]">Worker Tracking</span>
                    </label>
                    <label className="flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded-xl border border-slate-200 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={formData.zone_enabled}
                        onChange={(e) => setFormData({ ...formData, zone_enabled: e.target.checked })}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="font-medium text-slate-800 text-[11px]">Safety Zones</span>
                    </label>
                  </div>
                </div>

                {/* Initial Camera State */}
                <div className="pt-2 border-t border-slate-100">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-800 text-xs">Initial Camera State</p>
                      <p className="text-[11px] text-slate-500">
                        Camera is added in <strong>OFF</strong> state by default. Turn ON manually whenever ready.
                      </p>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer shrink-0">
                      <input
                        type="checkbox"
                        checked={formData.enabled}
                        onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                        className="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                      />
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${formData.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'}`}>
                        {formData.enabled ? 'Start ON' : 'Keep OFF'}
                      </span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Pinned Modal Footer */}
              <div className="flex items-center justify-end gap-2.5 px-5 py-3.5 border-t border-slate-100 shrink-0 bg-slate-50/90 rounded-b-2xl">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-200/70 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-xl shadow-sm hover:shadow transition-all disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Adding Camera...' : formData.enabled ? 'Add & Turn ON' : 'Add Camera (OFF)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete All Confirmation Modal */}
      {isConfirmDeleteAllOpen && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
          <div className="bg-white p-5 sm:p-6 rounded-2xl max-w-md w-full space-y-4 border border-rose-200 shadow-2xl max-h-[90vh] overflow-y-auto my-auto animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 border border-rose-100">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-rose-700">Delete All Cameras?</h3>
                <p className="text-xs text-slate-500 font-medium">Permanent system action</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Are you sure you want to delete all registered cameras? This action is permanent and stops all real-time streams and AI detection workers.
            </p>
            <div className="flex justify-end gap-2.5 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsConfirmDeleteAllOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteAllMutation.mutate()}
                disabled={deleteAllMutation.isPending}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-all disabled:opacity-50"
              >
                {deleteAllMutation.isPending ? 'Deleting...' : 'Yes, Delete All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
