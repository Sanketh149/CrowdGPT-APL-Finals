/**
 * CrowdGuard Command — API Client
 * Typed fetch functions for all backend endpoints.
 */

import type {
  AgentRunResult,
  Alert,
  Gate,
  GateOverrideRequest,
  MatchPhase,
  RunOrchestratorRequest,
  SystemStatus,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── Generic fetch helper ──────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Orchestrator endpoints ────────────────────────────────────────────────────

/**
 * Trigger a full orchestrator run for the given match/phase.
 */
export async function runOrchestrator(
  req: RunOrchestratorRequest
): Promise<AgentRunResult> {
  return apiFetch<AgentRunResult>("/run", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/**
 * Get current system-wide status (phase, risk level, active protocol).
 */
export async function getSystemStatus(): Promise<SystemStatus> {
  return apiFetch<SystemStatus>("/status");
}

/**
 * Health check endpoint.
 */
export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health");
}

// ── Gate control endpoints ────────────────────────────────────────────────────

/**
 * Get status for all gates, or a specific gate by ID.
 */
export async function getGates(gateId = "ALL"): Promise<{ gates: Gate[] }> {
  return apiFetch<{ gates: Gate[] }>(`/gates?gate_id=${gateId}`);
}

/**
 * Manual gate override — open or close a specific gate.
 */
export async function overrideGate(
  req: GateOverrideRequest
): Promise<{ gate_id: string; action: string; timestamp: string }> {
  return apiFetch(`/gate/${req.gate_id}/override?action=${req.action}`, {
    method: "POST",
  });
}

// ── Alert endpoints ───────────────────────────────────────────────────────────

/**
 * Get all currently active (unacknowledged) alerts.
 */
export async function getActiveAlerts(severity?: string): Promise<{ alerts: Alert[]; count: number }> {
  const qs = severity ? `?severity_filter=${severity}` : "";
  return apiFetch<{ alerts: Alert[]; count: number }>(`/alerts/active${qs}`);
}

/**
 * Acknowledge a specific alert.
 */
export async function acknowledgeAlert(
  alertId: string,
  acknowledgedBy = "operator"
): Promise<{ alert_id: string; success: boolean }> {
  return apiFetch(`/alerts/${alertId}/acknowledge?acknowledged_by=${acknowledgedBy}`, {
    method: "POST",
  });
}

// ── SSE streaming ─────────────────────────────────────────────────────────────

/**
 * Open an SSE connection to receive real-time agent decision events.
 * Returns the EventSource instance — caller is responsible for closing it.
 */
export function openAgentStream(
  onEvent: (decision: unknown) => void,
  onError?: (err: Event) => void
): EventSource {
  const es = new EventSource(`${API_BASE}/stream`);
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as unknown;
      onEvent(data);
    } catch {
      // Ignore malformed SSE frames
    }
  };
  if (onError) {
    es.onerror = onError;
  }
  return es;
}
