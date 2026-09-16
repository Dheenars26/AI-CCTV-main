import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { evidenceApi } from '../api/evidence';
import { PermissionGuard } from '../components/PermissionGuard';
import { Film, Download, Trash2, ShieldCheck, RefreshCw, Video, Image as ImageIcon, X, Maximize2 } from 'lucide-react';
import { resolveApiUrl } from '../config/apiConfig';

export const EvidencePage: React.FC = () => {
  const queryClient = useQueryClient();
  const [previewItem, setPreviewItem] = useState<any | null>(null);

  const { data: evidenceRes, isLoading, refetch } = useQuery({
    queryKey: ['evidence'],
    queryFn: () => evidenceApi.list(),
    refetchInterval: 3000,
  });

  const purgeMutation = useMutation({
    mutationFn: (id: string) => evidenceApi.purge(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evidence'] })
  });

  const purgeAllMutation = useMutation({
    mutationFn: () => evidenceApi.purgeAll(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['evidence'] })
  });

  const items = evidenceRes?.data || [];

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-xs">
            <Film className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Evidence Archive & Frame Ring Buffer
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Secure video clip recordings and AI high-resolution snapshot evidence files.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {items.length > 0 && (
            <PermissionGuard permission="evidence:purge">
              <button
                onClick={() => {
                  if (confirm(`Are you sure you want to permanently purge ALL ${items.length} evidence archive items and media files?`)) {
                    purgeAllMutation.mutate();
                  }
                }}
                disabled={purgeAllMutation.isPending}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-xs font-semibold rounded-xl transition-all shadow-xs disabled:opacity-50"
                title="Purge All Archived Evidence Files"
              >
                <Trash2 className="w-4 h-4" /> Purge All Evidence
              </button>
            </PermissionGuard>
          )}

          <button
            onClick={() => refetch()}
            className="p-2 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors"
            title="Refresh Evidence Archive"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid of Evidence Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {isLoading ? (
          [1, 2, 3].map((i) => (
            <div key={i} className="h-64 bg-white p-5 rounded-2xl border border-slate-200 shadow-card animate-pulse" />
          ))
        ) : items.length === 0 ? (
          <div className="col-span-full bg-white p-12 rounded-2xl border border-slate-200/80 shadow-card text-center text-slate-400 space-y-3">
            <ShieldCheck className="w-12 h-12 text-emerald-500 mx-auto" />
            <div>
              <h3 className="text-base font-semibold text-slate-800">No Evidence Clips Archived</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Ring buffer auto-archives video recordings and snapshots when threat classifications exceed threshold.
              </p>
            </div>
          </div>
        ) : (
          items.map((item) => {
            const evId = item.evidence_id || item.id || '';
            const isVideo = Boolean(item.video_url);
            const fileName = `Evidence #${evId ? String(evId).slice(-8) : 'File'}`;

            return (
              <div
                key={evId}
                className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-card hover:shadow-card-hover transition-all space-y-3.5"
              >
                {/* Header row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    {isVideo ? (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-[11px] font-bold rounded-lg border border-blue-200">
                        <Video className="w-3 h-3" /> VIDEO
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 text-[11px] font-bold rounded-lg border border-purple-200">
                        <ImageIcon className="w-3 h-3" /> IMAGE
                      </span>
                    )}
                    <span className="font-mono text-xs font-semibold text-slate-700">{fileName}</span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>

                {/* Theater Media Viewport */}
                <div
                  onClick={() => setPreviewItem(item)}
                  className="w-full aspect-video bg-slate-950 rounded-xl flex items-center justify-center border border-slate-800/80 shadow-inner overflow-hidden cursor-pointer group relative"
                  title="Click to expand full screen"
                >
                  {isVideo ? (
                    <video
                      src={resolveApiUrl(item.video_url)}
                      controls
                      preload="auto"
                      playsInline
                      className="w-full h-full object-contain rounded-xl pointer-events-auto"
                    />
                  ) : (
                    <img
                      src={resolveApiUrl(item.snapshot_url)}
                      alt={`Evidence ${evId}`}
                      className="w-full h-full object-contain rounded-xl group-hover:scale-105 transition-transform duration-200"
                    />
                  )}
                  <div className="absolute bottom-2 right-2 bg-slate-900/80 backdrop-blur-xs text-white p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none border border-slate-700">
                    <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
                  </div>
                </div>

                {/* Footer action buttons */}
                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setPreviewItem(item)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-xl text-xs font-semibold border border-blue-200 shadow-xs transition-colors"
                    >
                      <Maximize2 className="w-3.5 h-3.5" /> Inspect
                    </button>
                    <a
                      href={resolveApiUrl(item.video_url || item.snapshot_url)}
                      download={`evidence_${evId}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold border border-slate-200 shadow-xs transition-colors"
                    >
                      <Download className="w-3.5 h-3.5 text-slate-500" /> Download
                    </a>
                  </div>

                  <PermissionGuard permission="evidence:purge">
                    <button
                      onClick={() => {
                        if (confirm(`Purge evidence file '${fileName}'?`)) purgeMutation.mutate(evId);
                      }}
                      className="p-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 rounded-xl border border-rose-200 shadow-xs transition-colors"
                      title="Purge Evidence File"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </PermissionGuard>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Responsive Fullscreen/Lightbox Modal */}
      {previewItem && (
        <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-xs z-50 flex items-center justify-center p-3 sm:p-5 overflow-y-auto">
          <div className="bg-slate-900 rounded-2xl max-w-4xl w-full border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[92vh] sm:max-h-[88vh] my-auto animate-in fade-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-950/80 shrink-0">
              <div className="flex items-center gap-2.5 text-white">
                <div className="w-7 h-7 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center border border-blue-500/30">
                  <Film className="w-3.5 h-3.5" />
                </div>
                <div>
                  <span className="font-bold text-xs sm:text-sm">High-Resolution Evidence Inspection</span>
                  <span className="text-slate-400 text-[11px] font-mono block">
                    ID: {previewItem.evidence_id || previewItem.id || 'N/A'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setPreviewItem(null)}
                className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800 transition-colors"
                title="Close viewer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Media Viewport */}
            <div className="flex-1 min-h-0 bg-black flex items-center justify-center p-2 sm:p-4 overflow-hidden">
              {previewItem.video_url ? (
                <video
                  src={resolveApiUrl(previewItem.video_url)}
                  controls
                  autoPlay
                  playsInline
                  className="max-w-full max-h-[65vh] object-contain rounded-xl"
                />
              ) : (
                <img
                  src={resolveApiUrl(previewItem.snapshot_url)}
                  alt="Evidence"
                  className="max-w-full max-h-[65vh] object-contain rounded-xl"
                />
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between shrink-0 text-xs">
              <span className="text-slate-400 font-mono text-[11px]">
                Recorded: {new Date(previewItem.created_at).toLocaleString()}
              </span>
              <a
                href={resolveApiUrl(previewItem.video_url || previewItem.snapshot_url)}
                download={`evidence_${previewItem.evidence_id || previewItem.id}`}
                target="_blank"
                rel="noreferrer"
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <Download className="w-3.5 h-3.5" /> Download Media
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EvidencePage;
