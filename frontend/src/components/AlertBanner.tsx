import React from 'react';
import { Flame, Wind, AlertTriangle, X } from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';

export const AlertBanner: React.FC = () => {
  const { activeFireCount, activeSmokeCount, lastEvent } = useWebSocket();
  const [dismissed, setDismissed] = React.useState<boolean>(false);

  // Show emergency banner if fire/smoke active or recent event
  const isFire = activeFireCount > 0 || lastEvent?.event === 'fire_detected';
  const isSmoke = activeSmokeCount > 0 || lastEvent?.event === 'smoke_detected';

  if (dismissed || (!isFire && !isSmoke)) return null;

  return (
    <div className={`w-full py-2.5 px-6 text-white flex items-center justify-between shadow-md transition-all z-50 ${
      isFire ? 'bg-gradient-to-r from-rose-600 via-rose-500 to-rose-700 animate-pulse border-b border-rose-700' : 'bg-gradient-to-r from-amber-600 via-amber-500 to-amber-700 border-b border-amber-700'
    }`}>
      <div className="flex items-center gap-3">
        <div className="p-1.5 bg-black/15 rounded-lg">
          {isFire ? <Flame className="w-5 h-5 text-yellow-300 animate-bounce" /> : <Wind className="w-5 h-5 text-yellow-200" />}
        </div>
        <div>
          <h4 className="font-bold text-xs tracking-wide uppercase flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            INCIDENT NOTIFICATION: {isFire ? `${activeFireCount || 1} ACTIVE FIRE THREAT(S)` : `${activeSmokeCount || 1} ACTIVE SMOKE THREAT(S)`}
          </h4>
          <p className="text-[11px] text-white/90">
            {lastEvent?.data?.camera_name ? `Camera: ${lastEvent.data.camera_name} | Confidence: ${Math.round((lastEvent.data.confidence || 0.95) * 100)}%` : 'AI Detection Pipeline Dispatching Notifications...'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
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
