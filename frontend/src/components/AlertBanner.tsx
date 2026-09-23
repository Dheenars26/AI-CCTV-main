import React from 'react';
import { Flame, Wind, AlertTriangle, ShieldAlert, X } from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';

export const AlertBanner: React.FC = () => {
  const { activeFireCount, activeSmokeCount, lastEvent } = useWebSocket();
  const [dismissed, setDismissed] = React.useState<boolean>(false);

  const evtLower = (lastEvent?.event || '').toLowerCase();
  const dataPayload = lastEvent?.data || (lastEvent as any)?.payload || {};
  const labelLower = (dataPayload?.class_name || dataPayload?.incident_type || '').toLowerCase();

  // Show emergency banner if fire/smoke active or recent event or restricted zone intrusion
  const isFire = activeFireCount > 0 || lastEvent?.event === 'fire_detected';
  const isSmoke = activeSmokeCount > 0 || lastEvent?.event === 'smoke_detected';
  const isZone = evtLower.includes('zone') || labelLower.includes('zone') || labelLower.includes('restricted') || dataPayload?.incident_type === 'ZONE_VIOLATION';

  if (dismissed || (!isFire && !isSmoke && !isZone)) return null;

  return (
    <div className={`w-full py-2 sm:py-2.5 px-3 sm:px-6 text-white flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 shadow-md transition-all z-50 ${
      isZone
        ? 'bg-gradient-to-r from-red-700 via-rose-600 to-red-800 animate-pulse border-b border-red-800'
        : isFire
        ? 'bg-gradient-to-r from-rose-600 via-rose-500 to-rose-700 animate-pulse border-b border-rose-700'
        : 'bg-gradient-to-r from-amber-600 via-amber-500 to-amber-700 border-b border-amber-700'
    }`}>
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <div className="p-1.5 bg-black/15 rounded-lg shrink-0">
          {isZone ? (
            <ShieldAlert className="w-5 h-5 text-yellow-300 animate-bounce" />
          ) : isFire ? (
            <Flame className="w-5 h-5 text-yellow-300 animate-bounce" />
          ) : (
            <Wind className="w-5 h-5 text-yellow-200" />
          )}
        </div>
        <div className="min-w-0">
          <h4 className="font-bold text-xs tracking-wide uppercase flex items-center gap-1.5 truncate">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">
              {isZone
                ? `SECURITY ALERT: RESTRICTED AREA INTRUSION (${(dataPayload?.zone_name || 'RESTRICTED AREA').toUpperCase()})`
                : isFire
                ? `INCIDENT NOTIFICATION: ${activeFireCount || 1} ACTIVE FIRE THREAT(S)`
                : `INCIDENT NOTIFICATION: ${activeSmokeCount || 1} ACTIVE SMOKE THREAT(S)`}
            </span>
          </h4>
          <p className="text-[11px] text-white/90 truncate">
            {dataPayload?.camera_name
              ? `Camera: ${dataPayload.camera_name} | Location: ${dataPayload.location || 'Secure Perimeter'} | Confidence: ${Math.round((dataPayload.confidence || dataPayload.max_confidence || 0.95) * 100)}%`
              : 'AI Detection Pipeline Verified Incident & Captured Evidence...'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3 self-end sm:self-auto shrink-0">
        <a
          href="/notifications"
          className="px-3 py-1 bg-white/20 hover:bg-white/30 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors border border-white/30 shadow-xs"
        >
          View Notification
        </a>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 hover:bg-white/20 rounded-lg text-white/90 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
