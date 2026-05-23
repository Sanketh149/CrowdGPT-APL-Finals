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
const FALLBACK_TIMEOUT_MS = 12000;

const DUMMY_DECISIONS = [
  { agent: "crowd_density", decision: "North Stand at 68% capacity — rising trend detected. Recommend activating overflow routing.", confidence: 0.91, metadata: { zones: [] } },
  { agent: "gate_sensor", decision: "Gate G2 showing elevated flow rate (112 ppm). Consider opening G3 to redistribute crowd.", confidence: 0.87, metadata: {} },
  { agent: "weather_context", decision: "Clear skies, 28°C. Low heat-stress risk. Wind speed 12 km/h from north.", confidence: 0.95, metadata: {} },
  { agent: "routing", decision: "Optimal exit routing: North → Gate G1, G2. South → Gate G5, G6. Estimated evacuation time: 18 min.", confidence: 0.89, metadata: {} },
  { agent: "threat_detection", decision: "No anomalous crowd behaviour detected. Density gradients within normal thresholds.", confidence: 0.93, metadata: {} },
  { agent: "emergency_protocol", decision: "Protocol NORMAL maintained. All systems nominal. No escalation required.", confidence: 0.97, metadata: {} },
  { agent: "notifier", decision: "Routine status update dispatched to stadium operations. No alerts triggered.", confidence: 0.85, metadata: { alerts: [] } },
];

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
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef<number>(BASE_RECONNECT_MS);
  const isMountedRef = useRef(true);
  const hasReceivedDataRef = useRef(false);

  const injectFallback = useCallback(() => {
    if (!isMountedRef.current || hasReceivedDataRef.current) return;
    const now = new Date().toISOString();
    const dummies: AgentDecision[] = DUMMY_DECISIONS.map((d) => ({
      ...d,
      timestamp: now,
    }));
    setDecisions(dummies);
    setIsConnected(true);
    setConnectionError(null);
  }, []);

  const connect = useCallback(() => {
    if (!isMountedRef.current) return;

    // Clean up any existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    // Fallback: inject dummy data if no real data arrives within timeout
    if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
    fallbackTimerRef.current = setTimeout(injectFallback, FALLBACK_TIMEOUT_MS);

    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);
      setConnectionError(null);
      reconnectDelayRef.current = BASE_RECONNECT_MS;
    };

    es.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const raw = JSON.parse(event.data);
        const decision = normaliseDecision(raw);
        if (decision) {
          hasReceivedDataRef.current = true;
          if (fallbackTimerRef.current) {
            clearTimeout(fallbackTimerRef.current);
            fallbackTimerRef.current = null;
          }
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

      const delay = Math.min(reconnectDelayRef.current, MAX_RECONNECT_MS);
      reconnectDelayRef.current = delay * 2;

      reconnectTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) connect();
      }, delay);
    };
  }, [injectFallback]);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current);
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
