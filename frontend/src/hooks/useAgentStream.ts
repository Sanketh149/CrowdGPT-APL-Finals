/**
 * useAgentStream — React hook for SSE-based real-time agent decision feed
 *
 * Connects to the backend /stream endpoint and returns an auto-updating
 * list of agent decisions. Handles reconnection on error with exponential backoff.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentDecision } from "../types";

const SSE_URL = `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/stream`;
const MAX_BUFFER = 100;
const BASE_RECONNECT_MS = 2000;
const MAX_RECONNECT_MS = 30000;

interface UseAgentStreamResult {
  decisions: AgentDecision[];
  isConnected: boolean;
  connectionError: string | null;
  clearDecisions: () => void;
}

export function useAgentStream(): UseAgentStreamResult {
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef<number>(BASE_RECONNECT_MS);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Clean up any existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);
      setConnectionError(null);
      reconnectDelayRef.current = BASE_RECONNECT_MS; // Reset backoff on success
    };

    es.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const raw = JSON.parse(event.data);
        const decision = normaliseDecision(raw);
        if (decision) {
          setDecisions((prev) => {
            const next = [decision, ...prev];
            return next.slice(0, MAX_BUFFER);
          });
        }
      } catch {
        // Ignore malformed frames
      }
    };

    es.onerror = () => {
      if (!isMountedRef.current) return;
      es.close();
      esRef.current = null;
      setIsConnected(false);
      setConnectionError("Disconnected from agent stream — reconnecting...");

      // Exponential backoff reconnect
      const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_MS);
      reconnectDelayRef.current = delay * 2;

      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) connect();
      }, delay);
    };
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect]);

  const clearDecisions = useCallback(() => {
    setDecisions([]);
  }, []);

  return { decisions, isConnected, connectionError, clearDecisions };
}

// ── Normalise incoming SSE data into AgentDecision shape ─────────────────────

function normaliseDecision(raw: unknown): AgentDecision | null {
  if (!raw || typeof raw !== "object") return null;
  const d = raw as Record<string, unknown>;

  if (!d.agent || !d.timestamp || !d.decision) return null;

  return {
    agent: String(d.agent),
    timestamp: String(d.timestamp),
    decision: String(d.decision),
    confidence: typeof d.confidence === "number" ? d.confidence : 0,
    metadata: (d.metadata as Record<string, unknown>) ?? {},
  };
}
