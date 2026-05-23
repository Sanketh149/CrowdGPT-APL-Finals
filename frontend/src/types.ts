/**
 * CrowdGuard Command — TypeScript Type Definitions
 */

// ── Match / Phase ────────────────────────────────────────────────────────────

export type MatchPhase =
  | "pre_match"
  | "match_start"
  | "mid_match"
  | "match_end"
  | "post_match";

export type ProtocolLevel = "NORMAL" | "CAUTION" | "EVACUATE" | "LOCKDOWN";

// ── Stadium Zones ─────────────────────────────────────────────────────────────

export interface Zone {
  zone_id: string;
  label: string;
  capacity: number;
  current_count: number;
  capacity_pct: number;
  density_estimate: number;
  trend: "rising" | "stable" | "falling";
  is_hotspot: boolean;
  congestion_level: "low" | "medium" | "high" | "critical";
  flow_direction?: string;
  flow_magnitude?: number;
  // SVG layout
  svgX: number;
  svgY: number;
  svgWidth: number;
  svgHeight: number;
}

// ── Gates ─────────────────────────────────────────────────────────────────────

export type GateStatus = "open" | "closed" | "partial";

export interface Gate {
  gate_id: string;
  status: GateStatus;
  flow_rate_ppm: number;
  queue_length: number;
  utilisation_pct: number;
  bottleneck: boolean;
  is_emergency_gate: boolean;
}

export interface GateAction {
  gate_id: string;
  action: "open" | "close";
  reason: string;
  priority: "high" | "medium" | "low";
}

// ── Alerts ───────────────────────────────────────────────────────────────────

export type AlertSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface Alert {
  alert_id: string;
  severity: AlertSeverity;
  channel: "operator" | "field_staff" | "public_pa";
  message: string;
  zone_id?: string;
  timestamp: string;
  acknowledged: boolean;
  actions_required: string[];
}

// ── Agent Decisions ───────────────────────────────────────────────────────────

export interface AgentDecision {
  agent: string;
  timestamp: string;
  decision: string;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface AgentRunResult {
  status: string;
  run_id: string;
  match_id: string;
  timestamp: string;
  decisions: AgentDecision[];
  protocol: ProtocolLevel;
  alerts: Alert[];
}

// ── Crowd Stats ───────────────────────────────────────────────────────────────

export interface FlowVector {
  zone_id: string;
  direction: string;
  magnitude: number;
  speed_estimate_mps?: number;
}

export interface CrowdStats {
  zone_id: string;
  camera_id: string;
  timestamp: string;
  phase: MatchPhase;
  person_count: number;
  density_estimate: number;
  flow: {
    average_magnitude: number;
    dominant_direction_deg: number;
    dominant_direction_label: string;
    is_surge_detected: boolean;
  };
  is_hotspot: boolean;
  risk_contribution: number;
  congestion_level: "low" | "medium" | "high" | "critical";
}

// ── System Status ─────────────────────────────────────────────────────────────

export interface SystemStatus {
  phase: MatchPhase;
  overall_risk: number;
  active_protocol: ProtocolLevel;
  active_agents: string[];
  last_updated: string;
}

export interface ThreatMetadata {
  risk_score: number;
  risk_level: string;
  anomalies: Array<{
    type: string;
    zone: string;
    score: number;
    description: string;
  }>;
  top_risk_factors: Array<{
    factor: string;
    weight: number;
    score: number;
  }>;
  threat_summary: string;
}

// ── API Request / Response ────────────────────────────────────────────────────

export interface RunOrchestratorRequest {
  match_id: string;
  stadium_id: string;
  phase: MatchPhase;
  trigger: string;
}

export interface GateOverrideRequest {
  gate_id: string;
  action: "open" | "close";
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export type AdminRole = "SUPER_ADMIN" | "OPERATOR";

export interface User {
  email: string;
  name: string;
  picture: string;
  role: AdminRole;
}

export interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}
