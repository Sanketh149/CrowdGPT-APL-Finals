import React from "react";
import type { MatchPhase, ProtocolLevel, SystemStatus } from "../types";

interface Props {
  status: SystemStatus | null;
  isConnected: boolean;
}

const PHASE_LABELS: Record<MatchPhase, string> = {
  pre_match:   "Pre-Match",
  match_start: "Match Start",
  mid_match:   "Mid-Match",
  match_end:   "Match End",
  post_match:  "Post-Match",
};

const PROTOCOL_CONFIG: Record<ProtocolLevel, { bg: string; text: string; ring: string; glow: string; label: string }> = {
  NORMAL:   { bg: "bg-emerald-500",  text: "text-emerald-50",  ring: "ring-emerald-400",  glow: "shadow-emerald-500/30",  label: "NORMAL"   },
  CAUTION:  { bg: "bg-yellow-500",   text: "text-yellow-50",   ring: "ring-yellow-400",   glow: "shadow-yellow-500/30",   label: "CAUTION"  },
  EVACUATE: { bg: "bg-orange-500",   text: "text-orange-50",   ring: "ring-orange-400",   glow: "shadow-orange-500/30",   label: "EVACUATE" },
  LOCKDOWN: { bg: "bg-red-600",      text: "text-red-50",      ring: "ring-red-500",      glow: "shadow-red-500/40",      label: "LOCKDOWN" },
};

function RiskGauge({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  const color =
    pct > 75 ? "bg-red-500" : pct > 50 ? "bg-orange-500" : pct > 25 ? "bg-yellow-400" : "bg-emerald-500";

  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <span className="text-[10px] text-gray-500 uppercase tracking-wide shrink-0">Risk</span>
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-bold w-7 text-right ${
        pct > 75 ? "text-red-400" : pct > 50 ? "text-orange-400" : pct > 25 ? "text-yellow-400" : "text-emerald-400"
      }`}>
        {pct}
      </span>
    </div>
  );
}

export function StatusBar({ status, isConnected }: Props) {
  const protocol = (status?.active_protocol ?? "NORMAL") as ProtocolLevel;
  const cfg = PROTOCOL_CONFIG[protocol];
  const phase = (status?.phase ?? "pre_match") as MatchPhase;

  return (
    <header
      className="w-full border-b border-gray-800 px-4 py-0 flex items-stretch"
      style={{ background: "linear-gradient(135deg, #0f172a 0%, #111827 60%, #0f172a 100%)" }}
    >
      {/* Left: Branding */}
      <div className="flex items-center gap-3 py-2.5 pr-5 border-r border-gray-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
            <span className="text-base" aria-hidden="true">🏟️</span>
          </div>
          <div>
            <p className="text-white font-bold text-sm leading-tight tracking-tight">CrowdGPT</p>
            <p className="text-gray-500 text-[9px] tracking-wider uppercase">M. Chinnaswamy Stadium · IPL 2026</p>
          </div>
        </div>
      </div>

      {/* Centre: stats */}
      <div className="flex items-center gap-6 flex-1 px-6">
        {/* Phase */}
        <div className="flex flex-col justify-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Phase</p>
          <p className="text-white text-xs font-semibold">{PHASE_LABELS[phase]}</p>
        </div>

        <div className="w-px h-6 bg-gray-800" />

        {/* Risk */}
        <RiskGauge value={status?.overall_risk ?? 0} />

        <div className="w-px h-6 bg-gray-800" />

        {/* Agents */}
        <div className="flex flex-col justify-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Agents</p>
          <p className="text-white text-xs font-semibold">{status?.active_agents?.length ?? 7} active</p>
        </div>

        <div className="w-px h-6 bg-gray-800" />

        {/* Last updated */}
        <div className="flex flex-col justify-center">
          <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-0.5">Updated</p>
          <p className="text-gray-400 text-[10px] font-mono">
            {status?.last_updated ? new Date(status.last_updated).toLocaleTimeString() : "--:--:--"}
          </p>
        </div>
      </div>

      {/* Right: Protocol + connection + user */}
      <div className="flex items-center gap-4 py-2.5 pl-5 border-l border-gray-800">
        {/* Protocol badge */}
        <div
          className={`px-3 py-1 rounded-full font-bold text-[11px] tracking-widest ring-1 shadow-md ${cfg.bg} ${cfg.text} ${cfg.ring} ${cfg.glow}`}
          role="status"
        >
          {cfg.label}
        </div>

        {/* Connection */}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
          <span className={`text-[10px] ${isConnected ? "text-emerald-400" : "text-red-400"}`}>
            {isConnected ? "Live" : "Offline"}
          </span>
        </div>

        <div className="flex items-center gap-2 pl-3 border-l border-gray-800">
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-950 text-blue-400 border border-blue-800 font-bold tracking-wide">
            OPERATOR
          </span>
        </div>
      </div>
    </header>
  );
}
