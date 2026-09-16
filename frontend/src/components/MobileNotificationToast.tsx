import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Flame, Wind, ShieldAlert, X, ChevronRight, Bell } from 'lucide-react';
import { useWebSocket } from '../context/WebSocketContext';
import synterionLogo from '../assets/synterionx_icon.png';

export interface MobileNotificationItem {
  id: string;
  class_name: string;
  camera_name?: string;
  location?: string;
  confidence?: number;
  timestamp: string;
}

export const playNotificationChime = () => {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;

    // First tone (D5)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.12, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.25);

    // Second chime tone (A5)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(880.0, now + 0.1);
    gain2.gain.setValueAtTime(0.15, now + 0.1);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.1);
    osc2.stop(now + 0.45);
  } catch {
    // Audio autoplay might be restricted before user gesture
  }
};

export const MobileNotificationToast: React.FC = () => {
  const navigate = useNavigate();
  const { lastEvent } = useWebSocket();
  const [activeNotification, setActiveNotification] = useState<MobileNotificationItem | null>(null);
  const [progress, setProgress] = useState<number>(100);
  const seenEventsRef = useRef<Set<string>>(new Set());
  const timerRef = useRef<number | null>(null);
  const progressIntervalRef = useRef<number | null>(null);

  const showNotification = (item: MobileNotificationItem) => {
    setActiveNotification(item);
    setProgress(100);
    playNotificationChime();

    if (timerRef.current) clearTimeout(timerRef.current);
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);

    const duration = 6500; // 6.5 seconds display
    const intervalTime = 50;
    const step = (intervalTime / duration) * 100;

    progressIntervalRef.current = window.setInterval(() => {
      setProgress((prev) => {
        if (prev <= step) {
          if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
          return 0;
        }
        return prev - step;
      });
    }, intervalTime);

    timerRef.current = window.setTimeout(() => {
      setActiveNotification(null);
    }, duration);
  };

  // Listen to WebSocket events for real-time threat dispatch
  useEffect(() => {
    if (!lastEvent) return;

    const evtLower = (lastEvent.event || '').toLowerCase();
    const payload = lastEvent.data || (lastEvent as any).payload || {};
    const labelStr = (payload.class_name || payload.label || payload.event_type || '').toLowerCase();

    const isResolved =
      evtLower.includes('clear') ||
      evtLower.includes('resolve') ||
      (payload.state || '').toUpperCase() === 'RESOLVED' ||
      (payload.state || '').toUpperCase() === 'CLEARED' ||
      (payload.status || '').toUpperCase() === 'RESOLVED';

    if (isResolved) return;

    // Resolve alert ID from all potential keys
    const alertId = payload.alert_id || payload.id || payload.event_id || payload.evidence_id || '';

    // Ignore continuous raw frame detections that do not have an associated verified incident ID
    if (evtLower === 'detection_alert' && !alertId) {
      return;
    }

    const isThreat =
      evtLower.includes('fire') ||
      evtLower.includes('smoke') ||
      evtLower.includes('alert') ||
      evtLower.includes('violation') ||
      labelStr.includes('fire') ||
      labelStr.includes('smoke') ||
      labelStr.includes('ppe') ||
      labelStr.includes('violation');

    if (!isThreat) return;

    const eventKey = lastEvent.event_id || `${lastEvent.event}_${alertId || 'incident'}_${lastEvent.timestamp || Date.now()}`;
    if (seenEventsRef.current.has(eventKey)) return;
    seenEventsRef.current.add(eventKey);

    const className = payload.class_name || payload.label || (evtLower.includes('fire') ? 'fire' : evtLower.includes('smoke') ? 'smoke' : 'Incident');

    showNotification({
      id: alertId || 'latest',
      class_name: className,
      camera_name: payload.camera_name || `Camera #${payload.camera_id || 1}`,
      location: payload.camera_location || payload.location || 'Facility Zone',
      confidence: payload.confidence || payload.max_confidence || 0.95,
      timestamp: new Date().toLocaleTimeString(),
    });
  }, [lastEvent]);

  // Support manual custom event dispatch: window.dispatchEvent(new CustomEvent('show-mobile-notification', { detail: {...} }))
  useEffect(() => {
    const handleCustomToast = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail && detail.id) {
        showNotification(detail);
      }
    };

    window.addEventListener('show-mobile-notification', handleCustomToast);
    return () => {
      window.removeEventListener('show-mobile-notification', handleCustomToast);
      if (timerRef.current) clearTimeout(timerRef.current);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, []);

  if (!activeNotification) return null;

  const isFire = (activeNotification.class_name || '').toLowerCase().includes('fire');
  const isSmoke = (activeNotification.class_name || '').toLowerCase().includes('smoke');

  const handleClick = () => {
    const targetId = activeNotification?.id;
    setActiveNotification(null);
    if (targetId && targetId !== 'latest' && !targetId.startsWith('temp_')) {
      navigate(`/notifications/${targetId}`);
    } else {
      navigate('/notifications');
    }
  };

  return (
    <div className="fixed top-4 right-3 sm:right-6 z-[60] w-full max-w-[calc(100vw-1.5rem)] sm:max-w-md animate-in slide-in-from-top-4 fade-in duration-300">
      <div
        onClick={handleClick}
        className={`group relative overflow-hidden rounded-2xl shadow-2xl border cursor-pointer backdrop-blur-xl transition-all hover:scale-[1.02] active:scale-[0.99] ${
          isFire
            ? 'bg-gradient-to-br from-slate-900 via-rose-950/90 to-slate-900 border-rose-500/40 text-white shadow-rose-950/40'
            : isSmoke
            ? 'bg-gradient-to-br from-slate-900 via-amber-950/90 to-slate-900 border-amber-500/40 text-white shadow-amber-950/40'
            : 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-blue-500/40 text-white shadow-blue-950/40'
        }`}
      >
        {/* Mobile Header: App Identity & Time */}
        <div className="px-4 pt-3 pb-1.5 flex items-center justify-between border-b border-white/10 text-[11px]">
          <div className="flex items-center gap-2">
            <img src={synterionLogo} alt="SynterionX" className="w-4 h-4 rounded object-contain" />
            <span className="font-bold tracking-wider text-slate-300 uppercase text-[10px]">
              SYNTERION X SAFETY
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-mono text-[10px]">Now</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveNotification(null);
              }}
              className="p-1 rounded-full hover:bg-white/15 text-slate-400 hover:text-white transition-colors"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Mobile Notification Body */}
        <div className="p-4 flex items-start gap-3.5">
          <div
            className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 shadow-inner border ${
              isFire
                ? 'bg-rose-600/20 text-rose-400 border-rose-500/40 animate-pulse'
                : isSmoke
                ? 'bg-amber-600/20 text-amber-400 border-amber-500/40'
                : 'bg-blue-600/20 text-blue-400 border-blue-500/40'
            }`}
          >
            {isFire ? (
              <Flame className="w-6 h-6 animate-bounce text-rose-400" />
            ) : isSmoke ? (
              <Wind className="w-6 h-6 text-amber-400" />
            ) : (
              <ShieldAlert className="w-6 h-6 text-blue-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h4 className="font-extrabold text-sm tracking-tight text-white capitalize flex items-center gap-1.5">
                <span>{activeNotification.class_name} Detected!</span>
                <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping inline-block" />
              </h4>
            </div>

            <p className="text-xs text-slate-300 mt-0.5 truncate font-medium">
              {activeNotification.camera_name}
              {activeNotification.location && ` • ${activeNotification.location}`}
            </p>

            <div className="mt-2.5 flex items-center justify-between text-[11px] text-blue-400 font-semibold group-hover:text-blue-300 transition-colors">
              <span className="flex items-center gap-1">
                <span>Tap to view evidence & remedy</span>
                <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
              </span>
              {activeNotification.confidence && (
                <span className="font-mono text-[10px] text-slate-400 bg-white/10 px-2 py-0.5 rounded-full border border-white/10">
                  {Math.round(activeNotification.confidence * 100)}% Conf.
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Dynamic Shrinking Progress Bar */}
        <div className="h-1 w-full bg-white/10 overflow-hidden">
          <div
            className={`h-full transition-all duration-75 ${
              isFire ? 'bg-rose-500' : isSmoke ? 'bg-amber-500' : 'bg-blue-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
};
