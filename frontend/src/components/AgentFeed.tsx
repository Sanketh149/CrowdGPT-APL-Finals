/**
 * AgentFeed — Real-time scrolling log of agent decisions.
 * New decisions appear at the top. Each item shows agent name,
 * decision text, confidence score, and timestamp.
 */

import React, { useRef, useEffect } from "react";
import type { AgentDecision } from "../types";

interface Props {
  decisions: AgentDecision[];
  isConnected: boolean;
  isRunning?: boolean;
  onClear?: () => void;
}

// Colour and icon per agent type
const AGENT_CONFIG: Record<
  string,
  { color: string; bg: string; abbr: string }
> = {
  crowd_density:       { color: "text-cyan-400",    bg: "bg-cyan-900/40",    abbr: "CD" },
  gate_sensor:         { color: "text-violet-400",  bg: "bg-violet-900/40",  abbr: "GS" },
  weather_context:     { color: "text-sky-400",     bg: "bg-sky-900/40",     abbr: "WX" },
  routing:             { color: "text-lime-400",    bg: "bg-lime-900/40",    abbr: "RT" },
  threat_detection:    { color: "text-orange-400",  bg: "bg-orange-900/40",  abbr: "TD" },
  emergency_protocol:  { color: "text-red-400",     bg: "bg-red-900/40",     abbr: "EP" },
  notifier:            { color: "text-yellow-400",  bg: "bg-yellow-900/40",  abbr: "NT" },
  orchestrator:        { color: "text-emerald-400", bg: "bg-emerald-900/40", abbr: "OR" },
};

function confidenceBar(score: number) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "bg-emerald-500" : pct >= 60 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-1 mt-1">
      <div className="w-20 h-1 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[9px] text-gray-500 font-mono">{pct}%</span>
    </div>
  );
}

function DecisionItem({ decision }: { decision: AgentDecision }) {
  const cfg = AGENT_CONFIG[decision.agent] ?? {
    color: "text-gray-400",
    bg: "bg-gray-800",
    abbr: "??",
  };

  const time = new Date(decision.timestamp).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <li
      className={`flex gap-2.5 px-3 py-2.5 rounded-lg border border-gray-700/50 ${cfg.bg} animate-fade-in`}
    >
      {/* Agent badge */}
      <div
        className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center font-bold text-[10px] ${cfg.color} border border-current/30`}
      >
        {cfg.abbr}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <span className={`text-xs font-semibold ${cfg.color} capitalize`}>
            {decision.agent.replace(/_/g, " ")}
          </span>
          <span className="text-[10px] text-gray-500 font-mono shrink-0">{time}</span>
        </div>
        <p className="text-xs text-gray-300 mt-0.5 leading-relaxed line-clamp-2">
          {decision.decision}
        </p>
        {confidenceBar(decision.confidence)}
      </div>
    </li>
  );
}

function SkeletonCard({ abbr, color, bg }: { abbr: string; color: string; bg: string }) {
  return (
    <li className={`flex gap-2.5 px-3 py-2.5 rounded-lg border border-gray-700/50 ${bg} animate-pulse`}>
      <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center font-bold text-[10px] ${color} border border-current/30`}>
        {abbr}
      </div>
      <div className="flex-1 min-w-0 space-y-1.5 py-0.5">
        <div className="h-2.5 bg-gray-600/60 rounded w-24" />
        <div className="h-2 bg-gray-700/60 rounded w-full" />
        <div className="h-2 bg-gray-700/60 rounded w-3/4" />
      </div>
    </li>
  );
}

const AGENT_ORDER = ["crowd_density","gate_sensor","weather_context","routing","threat_detection","emergency_protocol","notifier"];

export function AgentFeed({ decisions, isConnected, isRunning, onClear }: Props) {
  const listRef = useRef<HTMLUListElement>(null);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              isRunning ? "bg-blue-400 animate-pulse" : isConnected ? "bg-emerald-400 animate-pulse" : "bg-gray-500"
            }`}
          />
          <h2 className="text-sm font-semibold text-white">Agent Feed</h2>
          <span className="text-[10px] text-gray-500 bg-gray-700 rounded px-1.5 py-0.5">
            {isRunning ? "..." : decisions.length}
          </span>
        </div>
        {decisions.length > 0 && !isRunning && onClear && (
          <button
            onClick={onClear}
            className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Feed list */}
      <div className="flex-1 overflow-y-auto p-2">
        {isRunning && decisions.length === 0 ? (
          <ul className="flex flex-col gap-1.5">
            {AGENT_ORDER.map((a) => {
              const cfg = AGENT_CONFIG[a] ?? { color: "text-gray-400", bg: "bg-gray-800/40", abbr: "??" };
              return <SkeletonCard key={a} abbr={cfg.abbr} color={cfg.color} bg={cfg.bg} />;
            })}
          </ul>
        ) : decisions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 py-8">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
              <span className="text-gray-500 text-lg">🤖</span>
            </div>
            <p className="text-xs text-gray-500">
              {isConnected ? "Waiting for agent decisions..." : "Not connected"}
            </p>
          </div>
        ) : (
          <ul ref={listRef} className="flex flex-col gap-1.5">
            {decisions.map((d, idx) => (
              <DecisionItem key={`${d.timestamp}-${d.agent}-${idx}`} decision={d} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
