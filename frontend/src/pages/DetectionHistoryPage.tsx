import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { detectionsApi } from '../api/detections';
import { Eye, Flame, Wind, RefreshCw, Filter } from 'lucide-react';

export const DetectionHistoryPage: React.FC = () => {
  const [classFilter, setClassFilter] = useState<string>('');

  const { data: detectionsRes, isLoading, refetch } = useQuery({
    queryKey: ['detections', { class_name: classFilter }],
    queryFn: () => detectionsApi.list({ class_name: classFilter || undefined, limit: 20 }),
    refetchInterval: 3000,
  });

  const detections = detectionsRes?.data || [];

  return (
    <div className="space-y-6">
      {/* Header & Filter Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-card">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-xs">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              AI Detection Frame History
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Raw YOLO object detection frames, normalized bounding boxes, and confidence scores.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-slate-50 px-2 py-1 rounded-xl border border-slate-200">
            <Filter className="w-3.5 h-3.5 text-slate-400 ml-1" />
            <select
              value={classFilter}
              onChange={(e) => setClassFilter(e.target.value)}
              className="bg-transparent text-xs text-slate-700 font-medium focus:outline-none pr-2 py-1 cursor-pointer"
            >
              <option value="">All Threat Classes</option>
              <option value="fire">Fire</option>
              <option value="smoke">Smoke</option>
            </select>
          </div>

          <button
            onClick={() => refetch()}
            className="p-2 bg-slate-50 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-xl border border-slate-200 shadow-xs transition-colors"
            title="Refresh Detection Log"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Detection Table */}
      <div className="bg-white rounded-2xl overflow-hidden border border-slate-200/80 shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 uppercase font-bold text-[11px] tracking-wider border-b border-slate-200/80">
              <tr>
                <th className="p-4">Timestamp</th>
                <th className="p-4">Camera Source</th>
                <th className="p-4">Threat Class</th>
                <th className="p-4">AI Confidence</th>
                <th className="p-4">Bounding Box (Norm)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="p-12 text-center text-slate-400">Loading detection history log...</td>
                </tr>
              ) : detections.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-12 text-center text-slate-400">
                    <p className="font-medium text-slate-600">No detection events recorded matching filters.</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">YOLO telemetry triggers will appear here in real time.</p>
                  </td>
                </tr>
              ) : (
                detections.map((det) => (
                  <tr key={det.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="p-4 font-mono text-slate-500">
                      {new Date(det.timestamp).toLocaleString()}
                    </td>
                    <td className="p-4 font-semibold text-slate-900">
                      {det.camera_name || `Camera #${det.camera_id}`}
                    </td>
                    <td className="p-4">
                      <span className="flex items-center gap-1.5 font-bold uppercase text-xs">
                        {det.class_name === 'fire' ? (
                          <div className="flex items-center gap-1 text-rose-600">
                            <Flame className="w-4 h-4 text-rose-600" />
                            <span>Fire</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 text-amber-600">
                            <Wind className="w-4 h-4 text-amber-600" />
                            <span>Smoke</span>
                          </div>
                        )}
                      </span>
                    </td>
                    <td className="p-4 font-mono text-blue-600 font-bold text-sm">
                      {Math.round(det.confidence * 100)}%
                    </td>
                    <td className="p-4 font-mono text-xs">
                      {det.bounding_box ? (
                        <span className="px-2 py-1 bg-slate-100 rounded-md border border-slate-200 text-slate-600">
                          [{det.bounding_box.x_min}, {det.bounding_box.y_min}, {det.bounding_box.x_max}, {det.bounding_box.y_max}]
                        </span>
                      ) : (
                        <span className="text-slate-400">N/A</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DetectionHistoryPage;
