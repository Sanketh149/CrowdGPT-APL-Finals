import React from "react";
import { useSearchParams } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: "Your Google account is not authorised to access CrowdGPT. Contact your system administrator.",
  auth_failed: "Authentication failed. Please try again.",
  oauth_denied: "Sign-in was cancelled. Please try again.",
};

const FEATURES = [
  {
    color: "#22d3ee", bg: "rgba(34,211,238,0.08)", border: "rgba(34,211,238,0.2)",
    title: "Live Stadium Heatmap",
    desc: "SVG zone map with density colour coding, hotspot pulsing, and per-zone occupancy counters.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
  },
  {
    color: "#818cf8", bg: "rgba(129,140,248,0.08)", border: "rgba(129,140,248,0.2)",
    title: "YOLOv8 + LSTM Detection",
    desc: "Spatial crowd detection (YOLO) combined with temporal anomaly detection (LSTM) on a live canvas.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M3 8h12a2 2 0 012 2v4a2 2 0 01-2 2H3a2 2 0 01-2-2v-4a2 2 0 012-2z" />
      </svg>
    ),
  },
  {
    color: "#34d399", bg: "rgba(52,211,153,0.08)", border: "rgba(52,211,153,0.2)",
    title: "Real-time Agent Feed",
    desc: "Live SSE stream of every Gemini agent decision with confidence scores as they happen.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    color: "#fb923c", bg: "rgba(251,146,60,0.08)", border: "rgba(251,146,60,0.2)",
    title: "Threat Detection & Routing",
    desc: "Risk scoring 0–100, anomaly detection, and dynamic gate open/close recommendations.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
  {
    color: "#f472b6", bg: "rgba(244,114,182,0.08)", border: "rgba(244,114,182,0.2)",
    title: "Intelligent Email Alerts",
    desc: "Gemini-written HTML emails with zone tables, anomaly lists, gate actions via SendGrid.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    color: "#f87171", bg: "rgba(248,113,113,0.08)", border: "rgba(248,113,113,0.2)",
    title: "Emergency Broadcast",
    desc: "EVACUATE / LOCKDOWN SSE broadcast to all stadium screens with gate redirect instructions.",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
];

const MONITORING_AGENTS = [
  { abbr: "CD", color: "#22d3ee", label: "Crowd Density" },
  { abbr: "GS", color: "#a78bfa", label: "Gate Sensor" },
  { abbr: "WX", color: "#38bdf8", label: "Weather" },
];

const RESPONSE_AGENTS = [
  { abbr: "RT", color: "#86efac", label: "Routing" },
  { abbr: "TD", color: "#fb923c", label: "Threat" },
  { abbr: "EP", color: "#f87171", label: "Emergency" },
  { abbr: "NT", color: "#fbbf24", label: "Notifier" },
];

export default function LoginPage() {
  const [params] = useSearchParams();
  const error = params.get("error");

  return (
    <div className="min-h-screen flex overflow-hidden" style={{ background: "#060c18" }}>

      {/* ── Left panel ───────────────────────────────────────────────── */}
      <div className="hidden lg:flex flex-col w-[58%] relative overflow-hidden"
        style={{ background: "linear-gradient(160deg,#07111f 0%,#0c1e38 50%,#060f1e 100%)" }}>

        {/* Ambient glow blobs */}
        <div className="absolute top-[-80px] left-[-60px] w-[380px] h-[380px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle,rgba(37,99,235,0.18) 0%,transparent 70%)" }} />
        <div className="absolute bottom-[-60px] right-[-80px] w-[320px] h-[320px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle,rgba(6,182,212,0.12) 0%,transparent 70%)" }} />
        <div className="absolute top-[45%] right-[10%] w-[200px] h-[200px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle,rgba(129,140,248,0.1) 0%,transparent 70%)" }} />

        {/* Subtle dot grid */}
        <div className="absolute inset-0 pointer-events-none" style={{
          backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }} />

        <div className="relative flex flex-col h-full px-12 py-10">

          {/* Logo */}
          <div className="flex items-center gap-3 mb-10">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg"
              style={{ background: "linear-gradient(135deg,#2563eb,#06b6d4)", boxShadow: "0 0 20px rgba(37,99,235,0.4)" }}>
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <span className="text-white font-bold text-base tracking-tight">CrowdGPT</span>
            <span className="text-[9px] text-cyan-400 border border-cyan-800 rounded px-1.5 py-0.5 font-semibold tracking-widest uppercase"
              style={{ background: "rgba(6,182,212,0.08)" }}>APL 2026</span>
          </div>

          {/* Hero text */}
          <div className="mb-8">
            <p className="text-[10px] font-bold tracking-[3px] uppercase mb-3"
              style={{ color: "#38bdf8" }}>
              Google ADK · Gemini 2.5 Flash · Cloud Run
            </p>
            <h1 className="text-[2.4rem] font-extrabold leading-[1.15] text-white mb-4">
              Agentic Intelligence<br />
              <span style={{
                background: "linear-gradient(90deg,#38bdf8 0%,#818cf8 50%,#c084fc 100%)",
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
              }}>
                for Predictive<br />Crowd Safety
              </span>
            </h1>
            <p className="text-sm leading-relaxed max-w-md" style={{ color: "#94a3b8" }}>
              A real-time multi-agent AI platform that monitors crowd density, detects threats,
              activates emergency protocols, and dispatches intelligent alerts — all within a
              single Gemini-powered agent cycle.
            </p>
          </div>

          {/* Feature grid — 2 col, colored borders */}
          <div className="grid grid-cols-2 gap-2.5 mb-8">
            {FEATURES.map((f) => (
              <div key={f.title}
                className="flex gap-3 p-3.5 rounded-xl transition-all"
                style={{ background: f.bg, border: `1px solid ${f.border}` }}>
                <div className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5"
                  style={{ background: f.color + "20", color: f.color, border: `1px solid ${f.color}30` }}>
                  {f.icon}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-[11px] font-semibold leading-tight mb-0.5">{f.title}</p>
                  <p className="text-[10px] leading-snug" style={{ color: "#64748b" }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Agent pipeline — two groups */}
          <div className="mt-auto">
            <p className="text-[9px] font-bold tracking-[2px] uppercase mb-3" style={{ color: "#334155" }}>
              Agent Pipeline
            </p>
            <div className="flex items-center gap-3">
              {/* Monitoring group */}
              <div className="flex flex-col gap-1.5 p-2.5 rounded-xl"
                style={{ background: "rgba(37,99,235,0.08)", border: "1px solid rgba(37,99,235,0.15)" }}>
                <p className="text-[8px] text-blue-500 font-bold tracking-wider uppercase">Parallel · Monitoring</p>
                <div className="flex gap-1.5">
                  {MONITORING_AGENTS.map((a) => (
                    <div key={a.abbr} className="flex flex-col items-center gap-1 px-2 py-1.5 rounded-lg"
                      style={{ background: a.color + "15", border: `1px solid ${a.color}30` }}>
                      <span className="text-[11px] font-bold font-mono" style={{ color: a.color }}>{a.abbr}</span>
                      <span className="text-[8px] text-gray-500 whitespace-nowrap">{a.label}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Arrow */}
              <div className="flex flex-col items-center gap-1">
                <span className="text-[8px] text-gray-700">breach</span>
                <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </div>

              {/* Response group */}
              <div className="flex flex-col gap-1.5 p-2.5 rounded-xl flex-1"
                style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}>
                <p className="text-[8px] text-red-400 font-bold tracking-wider uppercase">Sequential · Response</p>
                <div className="flex gap-1.5">
                  {RESPONSE_AGENTS.map((a, i) => (
                    <div key={a.abbr} className="flex items-center gap-1">
                      <div className="flex flex-col items-center gap-1 px-2 py-1.5 rounded-lg"
                        style={{ background: a.color + "15", border: `1px solid ${a.color}30` }}>
                        <span className="text-[11px] font-bold font-mono" style={{ color: a.color }}>{a.abbr}</span>
                        <span className="text-[8px] text-gray-500">{a.label}</span>
                      </div>
                      {i < RESPONSE_AGENTS.length - 1 && (
                        <svg className="w-2.5 h-2.5 shrink-0" style={{ color: "#1e293b" }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <p className="text-[9px] mt-4" style={{ color: "#1e293b" }}>
              M. Chinnaswamy Stadium · Bangalore · IPL 2026 Final
            </p>
          </div>
        </div>
      </div>

      {/* ── Right panel — sign in ─────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 py-12 relative"
        style={{ background: "#080e1a", borderLeft: "1px solid rgba(255,255,255,0.04)" }}>

        {/* Faint glow behind card */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle,rgba(37,99,235,0.08) 0%,transparent 70%)" }} />

        {/* Mobile logo */}
        <div className="flex lg:hidden items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "linear-gradient(135deg,#2563eb,#06b6d4)" }}>
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <span className="text-white font-bold">CrowdGPT</span>
        </div>

        <div className="relative w-full max-w-[340px]">

          {/* Card */}
          <div className="rounded-2xl p-8"
            style={{ background: "rgba(13,20,32,0.9)", border: "1px solid rgba(255,255,255,0.07)", boxShadow: "0 25px 60px rgba(0,0,0,0.5)" }}>

            <div className="mb-7">
              <h2 className="text-xl font-bold text-white mb-1">Command Access</h2>
              <p className="text-xs" style={{ color: "#475569" }}>
                Restricted to authorised stadium personnel.
              </p>
            </div>

            {/* Error */}
            {error && (
              <div className="mb-5 px-4 py-3 rounded-xl text-sm" style={{ background: "rgba(127,29,29,0.3)", border: "1px solid rgba(239,68,68,0.3)", color: "#fca5a5" }}>
                {ERROR_MESSAGES[error] ?? "An unexpected error occurred."}
              </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2 mb-7">
              {[
                { value: "8", label: "AI Agents" },
                { value: "6", label: "Zones" },
                { value: "4", label: "Protocols" },
              ].map(({ value, label }) => (
                <div key={label} className="text-center py-3 rounded-xl"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <p className="font-bold text-lg leading-none mb-1"
                    style={{ background: "linear-gradient(135deg,#38bdf8,#818cf8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                    {value}
                  </p>
                  <p className="text-[9px]" style={{ color: "#334155" }}>{label}</p>
                </div>
              ))}
            </div>

            {/* Sign in */}
            <button
              type="button"
              onClick={() => { window.location.href = `${API_URL}/auth/login`; }}
              className="w-full flex items-center justify-center gap-3 font-semibold py-3 px-4 rounded-xl transition-all mb-3"
              style={{ background: "white", color: "#111827" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "white")}
            >
              <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Sign in with Google
            </button>

            <p className="text-center text-[10px]" style={{ color: "#1e293b" }}>
              Only pre-approved admin emails can access this system.
            </p>
          </div>

          {/* Tech badges below card */}
          <div className="flex flex-wrap justify-center gap-1.5 mt-5">
            {["Google ADK", "Gemini 2.5 Flash", "Cloud Run", "FastAPI", "YOLOv8 + LSTM"].map((t) => (
              <span key={t} className="text-[9px] rounded-full px-2.5 py-1"
                style={{ color: "#334155", border: "1px solid #1e293b", background: "rgba(255,255,255,0.02)" }}>
                {t}
              </span>
            ))}
          </div>

          <p className="text-center text-[9px] mt-4" style={{ color: "#1e293b" }}>
            Google Cloud Agentic Premier League 2026
          </p>
        </div>
      </div>
    </div>
  );
}
