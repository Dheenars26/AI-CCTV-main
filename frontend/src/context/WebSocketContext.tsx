import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient, useQuery } from '@tanstack/react-query';
import { useAuth } from './AuthContext';
import { authApi } from '../api/auth';
import { systemApi } from '../api/system';
import { WSEventEnvelope } from '../types/api';
import { getWebSocketUrl } from '../config/apiConfig';

interface WebSocketContextType {
  isConnected: boolean;
  lastEvent: WSEventEnvelope | null;
  activeFireCount: number;
  activeSmokeCount: number;
  recentEvents: WSEventEnvelope[];
  clearRecentEvents: () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastEvent, setLastEvent] = useState<WSEventEnvelope | null>(null);
  const [recentEvents, setRecentEvents] = useState<WSEventEnvelope[]>([]);
  const [activeFireCount, setActiveFireCount] = useState<number>(0);
  const [activeSmokeCount, setActiveSmokeCount] = useState<number>(0);

  const { data: statsRes } = useQuery({
    queryKey: ['system-stats'],
    queryFn: () => systemApi.getStats(),
    refetchInterval: 3000,
    enabled: isAuthenticated,
  });

  const stats = statsRes?.data;

  useEffect(() => {
    if (stats) {
      setActiveFireCount(stats.active_fire_alerts ?? 0);
      setActiveSmokeCount(stats.active_smoke_alerts ?? 0);
    }
  }, [stats]);

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const isReconnectingRef = useRef<boolean>(false);
  const isConnectingRef = useRef<boolean>(false);
  const processedSeqSet = useRef<Set<string>>(new Set());
  const reconnectAttemptRef = useRef<number>(0);
  const lastActivityTimeRef = useRef<number>(Date.now());

  const connect = useCallback(async () => {
    if (!isAuthenticated) return;

    // Prevent duplicate connection attempts if already open, connecting, or in-flight
    if (isConnectingRef.current) return;
    if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    isConnectingRef.current = true;

    try {
      // 1. Obtain short-lived single-use WebSocket Ticket with graceful token fallback
      let ticket: string | null = null;
      try {
        ticket = await authApi.getWSTicket();
      } catch (err: any) {
        console.warn('[WebSocket] WS ticket retrieval delayed, attempting access token fallback:', err?.message);
      }

      const token = localStorage.getItem('access_token');
      const ticketOrToken = ticket || token;
      if (!ticketOrToken) {
        isConnectingRef.current = false;
        return;
      }

      // 2. Construct WS URL using Ticket or Token fallback
      const wsUrl = getWebSocketUrl(ticketOrToken);

      // Pass single-use ticket in Subprotocol header if available, otherwise standard query
      const ws = ticket
        ? new WebSocket(wsUrl, [`cctv-auth-${ticket}`])
        : new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnectingRef.current = false;
        setIsConnected(true);
        reconnectAttemptRef.current = 0;
        lastActivityTimeRef.current = Date.now();

        // If this was a reconnect after disconnection, resynchronize REST state!
        if (isReconnectingRef.current) {
          console.log('[WebSocket] Reconnected! Resynchronizing REST server state via TanStack Query...');
          queryClient.invalidateQueries();
          isReconnectingRef.current = false;
        }

        // Active Keep-Alive ping every 10s + Watchdog check (force close zombie connections if silent > 25s)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            // Check for zombie connection
            if (Date.now() - lastActivityTimeRef.current > 25000) {
              console.warn('[WebSocket] Connection silent for >25s (zombie socket). Force closing for clean reconnect...');
              ws.close();
              return;
            }
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 10000);
      };

      ws.onmessage = (event) => {
        lastActivityTimeRef.current = Date.now();
        try {
          const envelope: WSEventEnvelope = JSON.parse(event.data);

          // Skip deduplication check if pong/ack
          if (envelope.event === 'connected' || (envelope as any).type === 'pong') return;

          // Event ID & Sequence deduplication
          const dedupeKey = envelope.event_id || `${envelope.event}_${envelope.seq}_${envelope.timestamp}`;
          if (processedSeqSet.current.has(dedupeKey)) return;
          processedSeqSet.current.add(dedupeKey);
          if (processedSeqSet.current.size > 200) {
            const firstItem = Array.from(processedSeqSet.current)[0];
            processedSeqSet.current.delete(firstItem);
          }

          setLastEvent(envelope);
          setRecentEvents((prev) => [envelope, ...prev].slice(0, 50));

          // Handle real-time alert counters & REST invalidation
          const dataPayload = envelope.data || envelope.payload || envelope;
          const evtLower = (envelope.event || '').toLowerCase();
          const labelStr = (dataPayload.class_name || dataPayload.label || dataPayload.event_type || '').toLowerCase();
          const stateStr = (dataPayload.state || '').toUpperCase();

          const isClearedOrResolved =
            evtLower.includes('clear') ||
            evtLower.includes('resolve') ||
            stateStr === 'CLEARED' ||
            stateStr === 'RESOLVED';

          if (isClearedOrResolved) {
            const isFireCleared = evtLower.includes('fire') || labelStr.includes('fire');
            const isSmokeCleared = evtLower.includes('smoke') || labelStr.includes('smoke');
            if (isFireCleared) {
              setActiveFireCount((prev) => Math.max(0, prev - 1));
            }
            if (isSmokeCleared) {
              setActiveSmokeCount((prev) => Math.max(0, prev - 1));
            }
            if (!isFireCleared && !isSmokeCleared) {
              setActiveFireCount(0);
              setActiveSmokeCount(0);
            }
            queryClient.invalidateQueries({ queryKey: ['alerts'] });
            queryClient.invalidateQueries({ queryKey: ['system-stats'] });
          } else {
            // Only increment threat counters on VERIFIED incidents (with alert_id or verified state)
            const hasIncidentId = Boolean(dataPayload.alert_id || dataPayload.id || dataPayload.event_id);
            const isVerifiedState = stateStr === 'ALERT_SENT' || stateStr === 'ACTIVE' || stateStr === 'CONFIRMED';
            const isVerifiedIncident =
              evtLower.startsWith('verified_') ||
              evtLower.includes('incident') ||
              (hasIncidentId && (evtLower.includes('fire') || evtLower.includes('smoke') || evtLower.includes('alert') || isVerifiedState));

            if (isVerifiedIncident) {
              const isFire = evtLower.includes('fire') || labelStr.includes('fire');
              const isSmoke = evtLower.includes('smoke') || labelStr.includes('smoke');

              if (isFire) {
                setActiveFireCount((prev) => Math.max(1, prev + 1));
              }
              if (isSmoke) {
                setActiveSmokeCount((prev) => Math.max(1, prev + 1));
              }
              queryClient.invalidateQueries({ queryKey: ['alerts'] });
              queryClient.invalidateQueries({ queryKey: ['system-stats'] });
            }
          }

          if (evtLower.includes('camera') || evtLower.includes('system') || evtLower.includes('dvr')) {
            queryClient.invalidateQueries({ queryKey: ['cameras'] });
            queryClient.invalidateQueries({ queryKey: ['system-status'] });
            queryClient.invalidateQueries({ queryKey: ['system-stats'] });
          }
        } catch {
          // Ignore malformed text frames
        }
      };

      ws.onclose = (event) => {
        isConnectingRef.current = false;
        setIsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        isReconnectingRef.current = true;

        // Schedule auto-reconnect with fast backoff (max 3s) if user is authenticated
        if (isAuthenticated) {
          reconnectAttemptRef.current += 1;
          const delayMs = Math.min(3000, 500 * Math.pow(1.3, reconnectAttemptRef.current - 1));
          console.log(`[WebSocket] Disconnected (code: ${event.code}). Reconnecting attempt #${reconnectAttemptRef.current} in ${Math.round(delayMs)}ms...`);
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delayMs);
        }
      };

      ws.onerror = (e) => {
        isConnectingRef.current = false;
        console.warn('[WebSocket] Connection error event:', e);
        try {
          ws.close();
        } catch (_) {}
      };
    } catch (err: any) {
      isConnectingRef.current = false;
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        console.warn('[WebSocket] Token refresh or authorization required, retrying in 3s...');
      } else {
        const errMsg = err?.message || String(err);
        console.warn('[WebSocket] Connection setup delayed:', errMsg);
      }
      if (isAuthenticated) {
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      }
    }
  }, [isAuthenticated, queryClient]);

  useEffect(() => {
    if (isAuthenticated) {
      connect();

      // Trigger immediate reconnect check on browser focus or network online event
      const handleNetworkResume = () => {
        if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          connect();
        }
      };

      window.addEventListener('online', handleNetworkResume);
      window.addEventListener('focus', handleNetworkResume);

      return () => {
        window.removeEventListener('online', handleNetworkResume);
        window.removeEventListener('focus', handleNetworkResume);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        if (wsRef.current) wsRef.current.close();
      };
    } else {
      if (wsRef.current) wsRef.current.close();
      setIsConnected(false);
    }
  }, [isAuthenticated, connect]);

  const clearRecentEvents = () => setRecentEvents([]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        lastEvent,
        activeFireCount,
        activeSmokeCount,
        recentEvents,
        clearRecentEvents
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
