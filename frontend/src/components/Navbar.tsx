import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Flame, Wind, Radio, LogOut, Bell, ShieldAlert, CheckCircle, Trash2, Menu } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useWebSocket } from '../context/WebSocketContext';
import { alertsApi } from '../api/alerts';
import { getSafeTimestamp, formatSafeTime } from '../utils/dateUtils';
import synterionLogo from '../assets/synterionx_icon.png';

interface NavbarProps {
  onToggleMobileNav?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onToggleMobileNav }) => {
  const { user, logout } = useAuth();
  const queryClient = useQueryClient();
  const { isConnected, activeFireCount, activeSmokeCount } = useWebSocket();
  const [showNotifications, setShowNotifications] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [isClearing, setIsClearing] = useState(false);
  const [clearedAt, setClearedAt] = useState<number>(() => {
    const saved = localStorage.getItem('cctv_notif_cleared_at');
    return saved ? parseInt(saved, 10) : 0;
  });
  const [clearedIds, setClearedIds] = useState<Set<string>>(new Set());

  // Close dropdown when clicking anywhere outside of it or pressing Escape
  useEffect(() => {
    if (!showNotifications) return;

    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowNotifications(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showNotifications]);

  const { data: alertsRes } = useQuery({
    queryKey: ['navbar-notifications'],
    queryFn: () => alertsApi.list({ limit: 30 }),
    refetchInterval: 3500,
  });

  const rawNotifications = alertsRes?.data || [];

  // Strictly filter out any resolved or cleared notifications from the bell icon tab.
  // Order chronologically (newest at the very top).
  const displayList = useMemo(() => {
    return rawNotifications
      .filter((notif: any) => {
        if (clearedIds.has(String(notif.id))) return false;

        const stateUpper = (notif.state || notif.status || '').toUpperCase();
        if (stateUpper === 'RESOLVED' || stateUpper === 'CLEARED' || notif.resolved === true) {
          return false;
        }

        const notifTime = getSafeTimestamp(notif);
        if (clearedAt > 0 && notifTime <= clearedAt) {
          return false;
        }
        return true;
      })
      .sort((a: any, b: any) => getSafeTimestamp(b) - getSafeTimestamp(a));
  }, [rawNotifications, clearedIds, clearedAt]);

  const unreadCount = displayList.length;

  const handleDismissNotification = (id: string | number, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    setClearedIds(prev => new Set(prev).add(String(id)));
  };

  const handleClearAll = async (e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    // 1. Instant optimistic clear
    const now = Date.now();
    setClearedAt(now);
    localStorage.setItem('cctv_notif_cleared_at', String(now));
    const allIds = new Set(rawNotifications.map((n: any) => String(n.id)));
    setClearedIds(allIds);

    // 2. Background async resolve-all
    try {
      setIsClearing(true);
      await alertsApi.resolveAll();
    } catch (err) {
      console.warn('Resolve-all background error, UI stays cleared:', err);
    } finally {
      setIsClearing(false);
      queryClient.invalidateQueries({ queryKey: ['navbar-notifications'] });
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['system-stats'] });
    }
  };

  return (
    <header className="h-16 bg-white/95 border-b border-slate-200/80 px-3 sm:px-6 flex items-center justify-between sticky top-0 z-40 backdrop-blur-md shadow-sm">
      {/* Brand Title & Mobile Menu Button */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleMobileNav}
          className="lg:hidden p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200/80 shrink-0"
          aria-label="Open navigation menu"
        >
          <Menu className="w-4 h-4" />
        </button>
        <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br from-blue-50 via-white to-indigo-50/50 flex items-center justify-center shadow-sm border border-slate-200/80 overflow-hidden p-1 shrink-0">
          <img src={synterionLogo} alt="SynterionX Logo" className="w-full h-full object-contain" />
        </div>
        <div className="min-w-0">
          <h1 className="font-extrabold text-sm sm:text-base tracking-tight text-slate-900 truncate">
            SYNTERION X
          </h1>
          <p className="hidden md:block text-[11px] text-slate-500 font-medium truncate">Smart AI Surveillance & Safety Platform</p>
        </div>
      </div>

      {/* Status Badges & Live Metrics */}
      <div className="flex items-center gap-2 sm:gap-4 shrink-0">
        {/* Real-time Threat Indicators */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className={`items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
            activeFireCount > 0 ? 'flex bg-rose-50 text-rose-700 border-rose-300 shadow-sm animate-pulse' : 'hidden sm:flex bg-slate-100 text-slate-600 border-slate-200'
          }`}>
            <Flame className={`w-3.5 h-3.5 ${activeFireCount > 0 ? 'text-rose-600 animate-bounce' : 'text-slate-400'}`} />
            <span>Fire: {activeFireCount}</span>
          </div>

          <div className={`items-center gap-1.5 px-2.5 sm:px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
            activeSmokeCount > 0 ? 'flex bg-amber-50 text-amber-800 border-amber-300 shadow-sm' : 'hidden sm:flex bg-slate-100 text-slate-600 border-slate-200'
          }`}>
            <Wind className={`w-3.5 h-3.5 ${activeSmokeCount > 0 ? 'text-amber-600' : 'text-slate-400'}`} />
            <span>Smoke: {activeSmokeCount}</span>
          </div>
        </div>

        {/* WebSocket Connectivity Status */}
        <div className={`flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 rounded-full text-xs font-medium border ${
          isConnected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'
        }`}>
          <Radio className={`w-3.5 h-3.5 ${isConnected ? 'text-emerald-600 animate-pulse' : 'text-rose-600'}`} />
          <span className="hidden sm:inline">{isConnected ? 'System Live' : 'Reconnecting'}</span>
        </div>

        {/* Quick-Access Notification Bell Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className={`relative p-2 rounded-xl border transition-all ${
              showNotifications
                ? 'bg-blue-50 text-blue-600 border-blue-200'
                : 'bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200'
            }`}
            title="Incident Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-rose-600 text-white text-[10px] font-extrabold rounded-full flex items-center justify-center px-1 shadow-sm animate-pulse">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 sm:w-96 max-w-[calc(100vw-1.5rem)] max-h-[calc(100vh-5rem)] flex flex-col bg-white rounded-2xl shadow-xl border border-slate-200/90 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
              <div className="p-3.5 bg-slate-50 border-b border-slate-200/80 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-blue-600" />
                  <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">Incident Notifications</span>
                  {unreadCount > 0 && (
                    <span className="bg-rose-100 text-rose-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full border border-rose-200">
                      {unreadCount} Active
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2.5">
                  <Link
                    to="/notifications"
                    onClick={() => setShowNotifications(false)}
                    className="text-[11px] font-semibold text-blue-600 hover:text-blue-700 hover:underline"
                  >
                    View All
                  </Link>
                </div>
              </div>

              <div className="max-h-80 sm:max-h-96 overflow-y-auto divide-y divide-slate-100 flex-1">
                {displayList.length === 0 ? (
                  <div className="p-7 text-center text-slate-400 text-xs space-y-1.5">
                    <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto" />
                    <p className="font-bold text-slate-700">No active notifications</p>
                    <p className="text-[11px] text-slate-400">All notifications resolved. Streams safe and nominal.</p>
                  </div>
                ) : (
                  displayList.map((notif) => {
                    const isFire = (notif.class_name || '').toLowerCase() === 'fire';
                    const isSmoke = (notif.class_name || '').toLowerCase() === 'smoke';
                    const isResolved = notif.state === 'RESOLVED' || notif.status === 'RESOLVED' || notif.state === 'CLEARED';

                    return (
                      <Link
                        key={notif.id}
                        to={`/notifications/${notif.id}`}
                        onClick={() => setShowNotifications(false)}
                        className="p-3 flex items-start gap-3 hover:bg-slate-50/90 transition-colors group block"
                      >
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border ${
                          isFire
                            ? 'bg-rose-50 text-rose-600 border-rose-200'
                            : isSmoke
                            ? 'bg-amber-50 text-amber-600 border-amber-200'
                            : 'bg-blue-50 text-blue-600 border-blue-200'
                        }`}>
                          {isFire ? <Flame className="w-4 h-4" /> : isSmoke ? <Wind className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-bold text-xs text-slate-900 capitalize truncate">
                              {notif.class_name || 'Incident'} Detected
                            </span>
                            <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                              isResolved ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                            }`}>
                              {isResolved ? 'RESOLVED' : notif.state || 'NEW'}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                            <span className="truncate">{notif.camera_name || `Camera #${notif.camera_id}`}</span>
                            <span>•</span>
                            <span className="font-mono text-[10px]">
                              {formatSafeTime(notif.triggered_at || notif.start_time || (notif as any).created_at)}
                            </span>
                          </div>

                          <p className="text-[10px] text-blue-600 font-medium mt-1 flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                            <span>Inspect Evidence & Remedy</span>
                            <span>→</span>
                          </p>
                        </div>
                      </Link>
                    );
                  })
                )}
              </div>

              <div className="p-2.5 bg-slate-50 border-t border-slate-200/80">
                <button
                  onClick={handleClearAll}
                  disabled={isClearing || displayList.length === 0}
                  className="w-full py-2 bg-rose-50 hover:bg-rose-100 active:bg-rose-200 text-rose-700 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-bold rounded-xl border border-rose-200 flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer"
                  title="Clear all incident notifications"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span>{isClearing ? 'Clearing Notifications...' : 'Clear All Notifications'}</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Profile & Logout */}
        {user && (
          <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
            <div className="text-right hidden sm:block">
              <p className="text-xs font-semibold text-slate-800">{user.full_name || user.username}</p>
              <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 uppercase">{user.role}</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs border border-blue-200 shadow-sm">
              {user.username.slice(0, 2).toUpperCase()}
            </div>
            <button
              onClick={() => logout()}
              className="p-2 hover:bg-rose-50 text-slate-400 hover:text-rose-600 rounded-xl transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
