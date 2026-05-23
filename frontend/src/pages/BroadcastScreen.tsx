import React, { useEffect, useState } from "react";
import { useBroadcast } from "../hooks/useBroadcast";

const PROTOCOL_CONFIG = {
  EVACUATE: { bg: "bg-red-700",    border: "border-red-400",    label: "EVACUATE", emoji: "🚨" },
  LOCKDOWN: { bg: "bg-red-900",    border: "border-red-300",    label: "LOCKDOWN", emoji: "🔒" },
  CAUTION:  { bg: "bg-yellow-700", border: "border-yellow-400", label: "CAUTION",  emoji: "⚠️" },
  NORMAL:   { bg: "bg-gray-900",   border: "border-gray-700",   label: "ALL CLEAR",emoji: "✅" },
};

export default function BroadcastScreen() {
  const { event, connected } = useBroadcast();
  const [flash, setFlash] = useState(false);

  const isEmergency =
    event?.type === "emergency" &&
    (event.protocol === "EVACUATE" || event.protocol === "LOCKDOWN");

  const config =
    PROTOCOL_CONFIG[event?.protocol as keyof typeof PROTOCOL_CONFIG] ??
    PROTOCOL_CONFIG.NORMAL;

  useEffect(() => {
    if (!isEmergency) { setFlash(false); return; }
    const id = setInterval(() => setFlash((f) => !f), 800);
    return () => clearInterval(id);
  }, [isEmergency]);

  return (
    <div
      className={`min-h-screen flex flex-col items-center justify-center transition-colors duration-500 ${config.bg}`}
    >
      {/* Live indicator */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full animate-pulse ${connected ? "bg-green-400" : "bg-red-400"}`} />
        <span className="text-white text-xs opacity-50">{connected ? "Live" : "Reconnecting..."}</span>
      </div>

      {/* CrowdGPT branding top-left */}
      <div className="absolute top-4 left-4">
        <span className="text-white text-sm font-bold opacity-40">CrowdGPT</span>
      </div>

      {/* Normal / Caution state */}
      {!isEmergency && (
        <div className="text-center">
          <div className="text-8xl mb-6">{config.emoji}</div>
          <h1 className="text-white text-5xl font-bold tracking-widest mb-3">{config.label}</h1>
          <p className="text-white text-xl opacity-60">
            Agentic Intelligence for Predictive Crowd Safety · Monitoring Active
          </p>
          {event?.timestamp && (
            <p className="text-white text-sm opacity-30 mt-4">
              Last update: {new Date(event.timestamp).toLocaleTimeString()}
            </p>
          )}
        </div>
      )}

      {/* Emergency state — full screen */}
      {isEmergency && (
        <div
          className={`text-center px-8 max-w-4xl transition-opacity duration-300 ${
            flash ? "opacity-100" : "opacity-90"
          }`}
        >
          <div className="text-9xl mb-6 animate-bounce">{config.emoji}</div>
          <h1 className="text-white text-6xl font-black tracking-widest mb-6 uppercase">
            {config.label}
          </h1>

          {event?.message && (
            <div
              className={`border-2 ${config.border} rounded-2xl p-6 mb-6 bg-black bg-opacity-30`}
            >
              <p className="text-white text-2xl font-medium leading-relaxed">{event.message}</p>
            </div>
          )}

          {event?.open_gates && event.open_gates.length > 0 && (
            <div className="flex flex-wrap justify-center gap-3 mb-6">
              {event.open_gates.map((gate) => (
                <div
                  key={gate}
                  className="bg-green-600 border border-green-400 rounded-lg px-5 py-2 text-white text-lg font-semibold"
                >
                  ✓ {gate.replace(/_/g, " ").toUpperCase()} — OPEN
                </div>
              ))}
            </div>
          )}

          <p className="text-white text-sm opacity-50">
            CrowdGPT · Follow staff instructions · Stay calm
          </p>
        </div>
      )}
    </div>
  );
}
