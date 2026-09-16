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
  const processedSeqSet = useRef<Set<string>>(new Set());
  const reconnectAttemptRef = useRef<number>(0);
  const lastActivityTimeRef = useRef<number>(Date.now());

  const connect = useCallback(async () => {
    if (!isAuthenticated) return;

    // Prevent duplicate connection attempts if already open or connecting
    if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      // 1. Obtain short-lived single-use WebSocket Ticket
      const ticket = await authApi.getWSTicket();
      if (!ticket) return;

      // 2. Construct WS URL using Ticket (No raw JWT token!)
      const wsUrl = getWebSocketUrl(ticket);

      // Pass single-use ticket in Subprotocol header: cctv-auth-wst_... AND in query parameter
      const ws = new WebSocket(wsUrl, [`cctv-auth-${ticket}`]);
      wsRef.current = ws;

      ws.onopen = () => {
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

      ws.onclose = () => {
        setIsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        isReconnectingRef.current = true;

        // Schedule auto-reconnect with fast backoff (max 2.5s) if user is authenticated
        if (isAuthenticated) {
          reconnectAttemptRef.current += 1;
          const delayMs = Math.min(2500, 500 * Math.pow(1.5, reconnectAttemptRef.current - 1));
          console.log(`[WebSocket] Disconnected. Reconnecting attempt #${reconnectAttemptRef.current} in ${Math.round(delayMs)}ms...`);
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect();
          }, delayMs);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err: any) {
      // If unauthorized (401/403), user session is not valid. Stop retrying.
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        setIsConnected(false);
        return;
      }
      const errMsg = err?.message || String(err);
      console.warn('[WebSocket] Ticket retrieval temporarily delayed:', errMsg);
      if (isAuthenticated) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 5000);
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
