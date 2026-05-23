/**
 * GateControls — List of stadium gates with open/close toggle buttons.
 * Calls the backend gate override endpoint on action.
 */

import React, { useState } from "react";
import type { Gate, GateStatus } from "../types";
import { overrideGate } from "../api";

interface Props {
  gates: Gate[];
  onGateChange?: (gateId: string, newStatus: GateStatus) => void;
}

const STATUS_CONFIG: Record<GateStatus, { dot: string; label: string; text: string }> = {
  open:    { dot: "bg-emerald-400", label: "Open",   text: "text-emerald-400" },
  closed:  { dot: "bg-red-500",     label: "Closed", text: "text-red-400"     },
  partial: { dot: "bg-yellow-400",  label: "Partial", text: "text-yellow-400" },
};

function UtilisationBar({ pct }: { pct: number }) {
  const color =
    pct > 0.85 ? "bg-red-500" : pct > 0.60 ? "bg-orange-500" : pct > 0.30 ? "bg-yellow-400" : "bg-emerald-500";
  return (
    <div className="w-full h-1 bg-gray-700 rounded-full overflow-hidden">
      <div className={`h-full ${color} transition-all`} style={{ width: `${pct * 100}%` }} />
    </div>
  );
}

function GateRow({
  gate,
  onToggle,
  loading,
}: {
  gate: Gate;
  onToggle: (gateId: string, action: "open" | "close") => void;
  loading: boolean;
}) {
  const statusCfg = STATUS_CONFIG[gate.status] ?? STATUS_CONFIG.closed;
  const isEmergency = gate.is_emergency_gate;
  const canOpen = gate.status === "closed";
  const canClose = gate.status === "open" && !isEmergency;

  return (
    <li
      className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border ${
        gate.bottleneck
          ? "border-orange-500/50 bg-orange-900/10"
          : "border-gray-700/50 bg-gray-750"
      }`}
    >
      {/* Gate ID */}
      <div
        className={`shrink-0 w-9 h-9 rounded-md flex items-center justify-center text-[11px] font-bold ${
          isEmergency
            ? "bg-violet-900 text-violet-300 border border-violet-700"
            : "bg-gray-700 text-gray-300"
        }`}
      >
        {gate.gate_id}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <span className={`text-[11px] font-medium ${statusCfg.text}`}>
            <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1 ${statusCfg.dot}`} />
            {statusCfg.label}
          </span>
          <span className="text-[10px] text-gray-500 font-mono">
            {gate.flow_rate_ppm} ppm
          </span>
        </div>
        <UtilisationBar pct={gate.utilisation_pct} />
        {gate.bottleneck && (
          <p className="text-[9px] text-orange-400 mt-0.5">
            Bottleneck — queue {gate.queue_length}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-1 shrink-0">
        <button
          onClick={() => onToggle(gate.gate_id, "open")}
          disabled={!canOpen || loading}
          className={`text-[10px] px-2 py-1 rounded font-semibold transition-colors ${
            canOpen && !loading
              ? "bg-emerald-700 hover:bg-emerald-600 text-white"
              : "bg-gray-700 text-gray-600 cursor-not-allowed"
          }`}
          title="Open gate"
        >
          Open
        </button>
        <button
          onClick={() => onToggle(gate.gate_id, "close")}
          disabled={!canClose || loading}
          className={`text-[10px] px-2 py-1 rounded font-semibold transition-colors ${
            canClose && !loading
              ? "bg-red-800 hover:bg-red-700 text-white"
              : "bg-gray-700 text-gray-600 cursor-not-allowed"
          }`}
          title={isEmergency ? "Emergency gates cannot be closed" : "Close gate"}
        >
          Close
        </button>
      </div>
    </li>
  );
}

export function GateControls({ gates, onGateChange }: Props) {
  const [loadingGates, setLoadingGates] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (gateId: string, action: "open" | "close") => {
    setLoadingGates((prev) => new Set(prev).add(gateId));
    setError(null);
    try {
      await overrideGate({ gate_id: gateId, action });
      onGateChange?.(gateId, action);
    } catch (err) {
      setError(`Failed to ${action} ${gateId}: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setLoadingGates((prev) => {
        const next = new Set(prev);
        next.delete(gateId);
        return next;
      });
    }
  };

  const openCount = gates.filter((g) => g.status === "open").length;
  const bottleneckCount = gates.filter((g) => g.bottleneck).length;

  // Split into regular and emergency gates
  const regularGates = gates.filter((g) => !g.is_emergency_gate);
  const emergencyGates = gates.filter((g) => g.is_emergency_gate);

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <h2 className="text-sm font-semibold text-white">Gate Controls</h2>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-emerald-400">{openCount} open</span>
          {bottleneckCount > 0 && (
            <span className="text-orange-400">{bottleneckCount} bottleneck{bottleneckCount > 1 ? "s" : ""}</span>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-2 mt-2 px-2 py-1.5 bg-red-900/30 border border-red-700 rounded text-[10px] text-red-400">
          {error}
        </div>
      )}

      {/* Gate list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {/* Regular gates */}
        <div>
          <p className="text-[9px] text-gray-500 uppercase tracking-wider px-1 mb-1">
            Entry / Exit Gates
          </p>
          <ul className="space-y-1">
            {regularGates.map((gate) => (
              <GateRow
                key={gate.gate_id}
                gate={gate}
                onToggle={handleToggle}
                loading={loadingGates.has(gate.gate_id)}
              />
            ))}
          </ul>
        </div>

        {/* Emergency gates */}
        {emergencyGates.length > 0 && (
          <div>
            <p className="text-[9px] text-violet-400 uppercase tracking-wider px-1 mb-1">
              Emergency Gates
            </p>
            <ul className="space-y-1">
              {emergencyGates.map((gate) => (
                <GateRow
                  key={gate.gate_id}
                  gate={gate}
                  onToggle={handleToggle}
                  loading={loadingGates.has(gate.gate_id)}
                />
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
