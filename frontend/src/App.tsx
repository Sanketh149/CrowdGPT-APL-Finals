/**
 * CrowdGPT — Agentic Intelligence for Predictive Crowd Safety
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import BroadcastScreen from "./pages/BroadcastScreen";
import { StatusBar } from "./components/StatusBar";
import { AgentFeed } from "./components/AgentFeed";
import { GateControls } from "./components/GateControls";
import { AlertPanel } from "./components/AlertPanel";
import { useAgentStream } from "./hooks/useAgentStream";
import { LivePanel } from "./components/LivePanel";
import {
  getSystemStatus,
  runOrchestrator,
  getActiveAlerts,
  getGates,
} from "./api";
import type {
  Alert,
  Gate,
  MatchPhase,
  SystemStatus,
  Zone,
} from "./types";

// Default zone data (populated from backend on first load)
const DEFAULT_ZONES: Zone[] = [
  { zone_id: "north_stand",  label: "North Stand",  capacity: 35000, current_count: 12000, capacity_pct: 0.34, density_estimate: 0.34, trend: "rising",  is_hotspot: false, congestion_level: "low",   svgX: 150, svgY: 10,  svgWidth: 300, svgHeight: 90  },
  { zone_id: "south_stand",  label: "South Stand",  capacity: 35000, current_count: 10500, capacity_pct: 0.30, density_estimate: 0.30, trend: "stable",  is_hotspot: false, congestion_level: "low",   svgX: 150, svgY: 340, svgWidth: 300, svgHeight: 90  },
  { zone_id: "east_stand",   label: "East Stand",   capacity: 20000, current_count: 8000,  capacity_pct: 0.40, density_estimate: 0.40, trend: "rising",  is_hotspot: false, congestion_level: "medium", svgX: 470, svgY: 120, svgWidth: 120, svgHeight: 200 },
  { zone_id: "west_stand",   label: "West Stand",   capacity: 22000, current_count: 5500,  capacity_pct: 0.25, density_estimate: 0.25, trend: "stable",  is_hotspot: false, congestion_level: "low",   svgX: 10,  svgY: 120, svgWidth: 120, svgHeight: 200 },
  { zone_id: "vip_pavilion", label: "VIP Pavilion", capacity: 10000, current_count: 5000,  capacity_pct: 0.50, density_estimate: 0.50, trend: "stable",  is_hotspot: false, congestion_level: "medium", svgX: 200, svgY: 155, svgWidth: 200, svgHeight: 130 },
  { zone_id: "media_center", label: "Media Center", capacity: 10000, current_count: 6000,  capacity_pct: 0.60, density_estimate: 0.60, trend: "stable",  is_hotspot: false, congestion_level: "medium", svgX: 230, svgY: 100, svgWidth: 140, svgHeight: 50  },
];

const PHASES: MatchPhase[] = ["pre_match", "match_start", "mid_match", "match_end", "post_match"];

function PhaseSelector({
  currentPhase,
  onChange,
}: {
  currentPhase: MatchPhase;
  onChange: (p: MatchPhase) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-gray-500 mr-1">Match Phase:</span>
      {PHASES.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`text-[10px] px-2 py-1 rounded font-medium transition-colors ${
            p === currentPhase
              ? "bg-blue-700 text-white"
              : "bg-gray-700 text-gray-400 hover:bg-gray-600"
          }`}
        >
          {p.replace(/_/g, " ")}
        </button>
      ))}
    </div>
  );
}

function Dashboard() {
  const [zones, setZones] = useState<Zone[]>(DEFAULT_ZONES);
  const [gates, setGates] = useState<Gate[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [phase, setPhase] = useState<MatchPhase>("pre_match");
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { decisions, isConnected, clearDecisions } = useAgentStream();

  // Poll system status and gate data every 10 seconds
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusData, gatesData] = await Promise.allSettled([
          getSystemStatus(),
          getGates("ALL"),
        ]);
        if (statusData.status === "fulfilled") setStatus(statusData.value);
        if (gatesData.status === "fulfilled") setGates(gatesData.value.gates ?? []);
      } catch {
        // Silently ignore polling errors
      }
    };

    fetchData();
    pollRef.current = setInterval(fetchData, 10000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Update zones from incoming agent decisions (crowd_density agent)
  useEffect(() => {
    const latestDensity = decisions.find((d) => d.agent === "crowd_density");
    if (!latestDensity) return;

    const meta = latestDensity.metadata as Record<string, unknown>;
    const zoneData = meta.zones as Array<Record<string, unknown>> | undefined;
    if (!zoneData) return;

    setZones((prev) =>
      prev.map((z) => {
        const updated = zoneData.find((d) => d.zone_id === z.zone_id);
        if (!updated) return z;
        return {
          ...z,
          current_count: (updated.current_count as number) ?? z.current_count,
          capacity_pct: (updated.capacity_pct as number) ?? z.capacity_pct,
          density_estimate: (updated.capacity_pct as number) ?? z.density_estimate,
          trend: (updated.trend as Zone["trend"]) ?? z.trend,
          is_hotspot: ((meta.hotspots as string[]) ?? []).includes(z.zone_id),
          congestion_level: (updated.capacity_pct as number) > 0.9
            ? "critical"
            : (updated.capacity_pct as number) > 0.75
            ? "high"
            : (updated.capacity_pct as number) > 0.5
            ? "medium"
            : "low",
        };
      })
    );
  }, [decisions]);

  // Update alerts from notifier decisions
  useEffect(() => {
    const notifierDecision = decisions.find((d) => d.agent === "notifier");
    if (!notifierDecision) return;
    const meta = notifierDecision.metadata as Record<string, unknown>;
    const newAlerts = meta.alerts as Alert[] | undefined;
    if (newAlerts && newAlerts.length > 0) {
      setAlerts((prev) => {
        const existingIds = new Set(prev.map((a) => a.alert_id));
        const fresh = newAlerts.filter((a) => !existingIds.has(a.alert_id));
        return [...fresh, ...prev].slice(0, 50);
      });
    }
  }, [decisions]);

  const handleRunOrchestrator = useCallback(async () => {
    setIsRunning(true);
    setRunError(null);
    try {
      const result = await runOrchestrator({
        match_id: "IPL_2026_FINAL",
        stadium_id: "narendra_modi_stadium",
        phase,
        trigger: "manual",
      });
      // Update alerts from result
      if (result.alerts.length > 0) {
        setAlerts((prev) => {
          const existingIds = new Set(prev.map((a) => a.alert_id));
          const fresh = result.alerts.filter((a) => !existingIds.has(a.alert_id));
          return [...fresh, ...prev].slice(0, 50);
        });
      }
      // Update status from result
      setStatus((prev) => ({
        ...(prev ?? {
          phase,
          overall_risk: 0,
          active_protocol: "NORMAL",
          active_agents: [],
          last_updated: "",
        }),
        active_protocol: result.protocol,
        last_updated: result.timestamp,
      }));
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Orchestrator run failed");
    } finally {
      setIsRunning(false);
    }
  }, [phase]);

  const handleAcknowledge = useCallback((alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) => (a.alert_id === alertId ? { ...a, acknowledged: true } : a))
    );
  }, []);

  const handleGateChange = useCallback((gateId: string, newStatus: Gate["status"]) => {
    setGates((prev) =>
      prev.map((g) => (g.gate_id === gateId ? { ...g, status: newStatus } : g))
    );
  }, []);

  return (
    <div className="min-h-screen text-white flex flex-col" style={{ background: "#080e1a" }}>
      {/* Top status bar */}
      <StatusBar status={status} isConnected={isConnected} />

      {/* Control bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800/60"
        style={{ background: "rgba(15,23,42,0.95)" }}>
        <PhaseSelector currentPhase={phase} onChange={setPhase} />
        <div className="flex items-center gap-3">
          {runError && (
            <span className="text-xs text-red-400">{runError}</span>
          )}
          <button
            onClick={handleRunOrchestrator}
            disabled={isRunning}
            className={`text-xs px-5 py-1.5 rounded-lg font-semibold transition-all shadow ${
              isRunning
                ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/30"
            }`}
          >
            {isRunning ? (
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                Running...
              </span>
            ) : "▶ Run Agent Cycle"}
          </button>
        </div>
      </div>

      {/* Main content grid */}
      <main className="flex-1 grid grid-cols-12 gap-2.5 p-2.5" style={{ gridAutoRows: "700px" }}>
        {/* Left column: Live Panel (Live Feed / Stadium Map / YOLO toggle) */}
        <section className="col-span-12 lg:col-span-5 xl:col-span-5">
          <LivePanel zones={zones} />
        </section>

        {/* Middle column: Agent Feed */}
        <section className="col-span-12 lg:col-span-4 xl:col-span-4">
          <AgentFeed
            decisions={decisions}
            isConnected={isConnected}
            onClear={clearDecisions}
          />
        </section>

        {/* Right column: Gate Controls + Alerts */}
        <section className="col-span-12 lg:col-span-3 xl:col-span-3 flex flex-col gap-2.5">
          <div className="flex-1 min-h-0">
            <GateControls gates={gates} onGateChange={handleGateChange} />
          </div>
          <div className="flex-1 min-h-0">
            <AlertPanel alerts={alerts} onAcknowledge={handleAcknowledge} />
          </div>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/screen" element={<BroadcastScreen />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
