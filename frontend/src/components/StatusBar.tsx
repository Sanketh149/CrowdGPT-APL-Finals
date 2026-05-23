/**
 * StatusBar — Top bar showing match phase, risk level, active protocol, agent count.
 */

import React from "react";
import type { MatchPhase, ProtocolLevel, SystemStatus } from "../types";
import { useAuth } from "../context/AuthContext";

interface Props {
  status: SystemStatus | null;
  isConnected: boolean;
}

const PHASE_LABELS: Record<MatchPhase, string> = {
  pre_match: "Pre-Match",
  match_start: "Match Start",
  mid_match: "Mid-Match",
  match_end: "Match End",
  post_match: "Post-Match",
};

const PROTOCOL_CONFIG: Record<
  ProtocolLevel,
  { bg: string; text: string; ring: string; label: string }
> = {
  NORMAL:   { bg: "bg-emerald-500",  text: "text-emerald-50",  ring: "ring-emerald-400",  label: "NORMAL"   },
  CAUTION:  { bg: "bg-yellow-500",   text: "text-yellow-50",   ring: "ring-yellow-400",   label: "CAUTION"  },
  EVACUATE: { bg: "bg-orange-500",   text: "text-orange-50",   ring: "ring-orange-400",   label: "EVACUATE" },
  LOCKDOWN: { bg: "bg-red-600",      text: "text-red-50",      ring: "ring-red-500",      label: "LOCKDOWN" },
};

function RiskGauge({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  const color =
    pct > 75 ? "bg-red-500" : pct > 50 ? "bg-orange-500" : pct > 25 ? "bg-yellow-400" : "bg-emerald-500";

  return (
    <div className="flex items-center gap-2 min-w-[160px]">
      <span className="text-xs text-gray-400 w-16 shrink-0">Risk Score</span>
      <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono font-bold text-white w-8 text-right">{pct}</span>
    </div>
  );
}

function ConnectionDot({ connected }: { connected: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          connected ? "bg-emerald-400 animate-pulse" : "bg-red-500"
        }`}
      />
      <span className={connected ? "text-emerald-400" : "text-red-400"}>
        {connected ? "Live" : "Offline"}
      </span>
    </span>
  );
}

export function StatusBar({ status, isConnected }: Props) {
  const protocol = (status?.active_protocol ?? "NORMAL") as ProtocolLevel;
  const cfg = PROTOCOL_CONFIG[protocol];
  const phase = (status?.phase ?? "pre_match") as MatchPhase;
  const { user, logout } = useAuth();

  return (
    <header className="w-full bg-gray-900 border-b border-gray-700 px-4 py-2 flex items-center justify-between gap-4">
      {/* Left: Branding */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-2xl" aria-hidden="true">🏟️</span>
          <div>
            <p className="text-white font-bold text-sm leading-tight">CrowdGPT</p>
            <p className="text-gray-500 text-[10px]">Narendra Modi Stadium · IPL 2026</p>
          </div>
        </div>
      </div>

      {/* Centre: Phase + Risk */}
      <div className="flex items-center gap-6">
        <div className="text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Match Phase</p>
          <p className="text-white text-sm font-semibold">{PHASE_LABELS[phase]}</p>
        </div>

        <RiskGauge value={status?.overall_risk ?? 0} />

        <div className="text-center">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">Active Agents</p>
          <p className="text-white text-sm font-semibold">{status?.active_agents?.length ?? 7}</p>
        </div>
      </div>

      {/* Right: Protocol badge + connection */}
      <div className="flex items-center gap-4 shrink-0">
        <div
          className={`px-3 py-1 rounded-full font-bold text-xs tracking-widest ring-1 ${cfg.bg} ${cfg.text} ${cfg.ring}`}
          role="status"
          aria-label={`Emergency protocol: ${cfg.label}`}
        >
          {cfg.label}
        </div>

        <ConnectionDot connected={isConnected} />

        <div className="text-right">
          <p className="text-[10px] text-gray-500">Last Updated</p>
          <p className="text-gray-300 text-[10px] font-mono">
            {status?.last_updated
              ? new Date(status.last_updated).toLocaleTimeString()
              : "--:--:--"}
          </p>
        </div>

        {user && (
          <div className="flex items-center gap-2 pl-3 border-l border-gray-700">
            {user.picture && (
              <img
                src={user.picture}
                alt={user.name}
                className="w-6 h-6 rounded-full border border-gray-700"
              />
            )}
            <span className="text-xs text-gray-400">{user.name}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-900 text-blue-300 font-medium">
              {user.role}
            </span>
            <button
              onClick={logout}
              className="text-xs text-gray-600 hover:text-gray-400 transition-colors ml-1"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
