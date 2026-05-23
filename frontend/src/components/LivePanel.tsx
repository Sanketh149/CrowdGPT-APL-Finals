import React, { useEffect, useRef, useState } from "react";
import type { Zone } from "../types";
import { StadiumMap } from "./StadiumMap";

interface Props {
  zones: Zone[];
}

type View = "split" | "stadium" | "internal" | "passthrough" | "gates" | "yolo";

const GCS = "https://storage.googleapis.com/crowdgpt-media-2026/videos";

const VIDEOS = {
  internal:     `${GCS}/passthrough.mp4`,         // internal stadium tracking
  passthrough:  `${GCS}/gate_1.mp4`,              // people walking on steps
  gate_1:       `${GCS}/internal_stadium_1.mp4`,  // outside gate 1
  gate_2:       `${GCS}/internal_stadium_2.mp4`,  // outside gate 2
};

// ── YOLO Canvas ────────────────────────────────────────────────────────────

interface Person {
  x: number; y: number;
  vx: number; vy: number;
  zone: string; size: number;
  wobble: number; wobbleSpeed: number;
}

const ZONE_LAYOUT: Record<string, { x: number; y: number; w: number; h: number; label: string }> = {
  north_stand:  { x: 148, y: 6,   w: 204, h: 56,  label: "North Stand"  },
  south_stand:  { x: 148, y: 258, w: 204, h: 56,  label: "South Stand"  },
  east_stand:   { x: 432, y: 74,  w: 76,  h: 152, label: "East Stand"   },
  west_stand:   { x: 8,   y: 74,  w: 76,  h: 152, label: "West Stand"   },
  vip_pavilion: { x: 90,  y: 102, w: 74,  h: 100, label: "VIP"          },
  media_center: { x: 346, y: 102, w: 74,  h: 100, label: "Media"        },
};

function densityRGB(pct: number): [number, number, number] {
  if (pct > 0.90) return [239, 68, 68];
  if (pct > 0.75) return [249, 115, 22];
  if (pct > 0.60) return [234, 179, 8];
  if (pct > 0.40) return [132, 204, 22];
  return [34, 197, 94];
}

function buildPersons(zones: Zone[]): Person[] {
  const out: Person[] = [];
  zones.forEach((zone) => {
    const l = ZONE_LAYOUT[zone.zone_id];
    if (!l) return;
    const count = Math.max(10, Math.floor(zone.capacity_pct * 140));
    for (let i = 0; i < count; i++) {
      out.push({
        x: l.x + 3 + Math.random() * (l.w - 6),
        y: l.y + 3 + Math.random() * (l.h - 6),
        vx: (Math.random() - 0.5) * 0.07,
        vy: (Math.random() - 0.5) * 0.07,
        zone: zone.zone_id,
        size: 1.2 + Math.random() * 1.6,
        wobble: Math.random() * Math.PI * 2,
        wobbleSpeed: 0.004 + Math.random() * 0.008,
      });
    }
  });
  return out;
}

function YoloCanvas({ zones }: { zones: Zone[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personsRef = useRef<Person[]>([]);
  const frameRef = useRef(0);
  const animRef = useRef(0);
  const zonesRef = useRef(zones);

  useEffect(() => { zonesRef.current = zones; }, [zones]);
  useEffect(() => { personsRef.current = buildPersons(zones); }, []); // eslint-disable-line

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const CW = canvas.width, CH = canvas.height;
    const sx = CW / 516, sy = CH / 320;

    const render = () => {
      const f = frameRef.current++;
      const zoneMap = Object.fromEntries(zonesRef.current.map((z) => [z.zone_id, z]));

      ctx.fillStyle = "#06101c";
      ctx.fillRect(0, 0, CW, CH);
      for (let y = 0; y < CH; y += 3) {
        ctx.fillStyle = "rgba(0,0,0,0.1)";
        ctx.fillRect(0, y, CW, 1);
      }

      Object.entries(ZONE_LAYOUT).forEach(([zoneId, l]) => {
        const z = zoneMap[zoneId];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityRGB(pct);
        const x = l.x * sx, y = l.y * sy, w = l.w * sx, h = l.h * sy;
        const grad = ctx.createRadialGradient(x+w/2, y+h/2, 0, x+w/2, y+h/2, Math.max(w,h)*0.65);
        grad.addColorStop(0, `rgba(${r},${g},${b},${0.14+pct*0.2})`);
        grad.addColorStop(1, `rgba(${r},${g},${b},0.01)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 4);
        ctx.fill();
        ctx.strokeStyle = `rgba(${r},${g},${b},${0.5+pct*0.3})`;
        ctx.lineWidth = 0.8;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 4);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = `rgba(${r},${g},${b},0.95)`;
        ctx.font = `bold 6.5px monospace`;
        ctx.textAlign = "right";
        ctx.fillText(`${(pct*100).toFixed(0)}%`, x+w-3, y+h-3);
        // Zone label
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.font = `5.5px monospace`;
        ctx.textAlign = "center";
        ctx.fillText(l.label, x+w/2, y+10);
      });

      // Outfield + pitch
      ctx.fillStyle = "rgba(12,60,28,0.55)";
      ctx.beginPath();
      ctx.ellipse(258*sx, 160*sy, 82*sx, 62*sy, 0, 0, Math.PI*2);
      ctx.fill();
      ctx.strokeStyle = "rgba(22,163,74,0.25)";
      ctx.lineWidth = 0.7; ctx.setLineDash([5,4]); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "rgba(21,128,61,0.85)";
      ctx.beginPath();
      ctx.ellipse(258*sx, 160*sy, 42*sx, 30*sy, 0, 0, Math.PI*2);
      ctx.fill();

      // Persons
      const persons = personsRef.current;
      persons.forEach((p, idx) => {
        const l = ZONE_LAYOUT[p.zone];
        if (!l) return;
        p.wobble += p.wobbleSpeed;
        p.x += p.vx + Math.sin(p.wobble) * 0.03;
        p.y += p.vy + Math.cos(p.wobble * 0.7) * 0.025;
        if (p.x < l.x+2) { p.x=l.x+2; p.vx=Math.abs(p.vx); }
        if (p.x > l.x+l.w-2) { p.x=l.x+l.w-2; p.vx=-Math.abs(p.vx); }
        if (p.y < l.y+2) { p.y=l.y+2; p.vy=Math.abs(p.vy); }
        if (p.y > l.y+l.h-2) { p.y=l.y+l.h-2; p.vy=-Math.abs(p.vy); }
        const z = zoneMap[p.zone];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityRGB(pct);
        const px = p.x*sx, py = p.y*sy;
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI*2);
        ctx.fillStyle = `rgba(${r},${g},${b},0.9)`;
        ctx.fill();
        const s1 = Math.floor((f*0.4+idx*6.7)%persons.length);
        const s2 = Math.floor((f*0.4+idx*6.7+19)%persons.length);
        const s3 = Math.floor((f*0.4+idx*6.7+43)%persons.length);
        if (idx===s1||idx===s2||idx===s3) {
          const bw=p.size*6*sx, bh=p.size*9*sy;
          ctx.strokeStyle="rgba(34,211,238,0.82)"; ctx.lineWidth=0.7;
          ctx.strokeRect(px-bw/2, py-bh*0.6, bw, bh);
          const conf = 0.77+Math.sin(f*0.03+idx)*0.13;
          ctx.fillStyle="rgba(34,211,238,0.9)"; ctx.font="5px monospace"; ctx.textAlign="left";
          ctx.fillText(`${conf.toFixed(2)}`, px-bw/2+1, py-bh*0.6-1.5);
        }
      });

      // Corner brackets
      ctx.strokeStyle="rgba(34,211,238,0.4)"; ctx.lineWidth=1.2;
      [[0,0],[CW,0],[0,CH],[CW,CH]].forEach(([cx,cy],i) => {
        const dx=i%2===0?1:-1, dy=i<2?1:-1;
        ctx.beginPath(); ctx.moveTo(cx+dx*10,cy); ctx.lineTo(cx,cy); ctx.lineTo(cx,cy+dy*10); ctx.stroke();
      });

      // Bottom stats
      ctx.fillStyle="rgba(0,0,0,0.65)"; ctx.fillRect(0,CH-15,CW,15);
      ctx.fillStyle="rgba(34,211,238,0.7)"; ctx.font="5.8px monospace"; ctx.textAlign="left";
      ctx.fillText(`YOLOv8n + LSTM · ${persons.length} detections · ${(29.5+Math.sin(f*0.02)*0.5).toFixed(1)}fps`, 5, CH-5);

      // LIVE
      const pulse = Math.sin(f*0.07)>0;
      ctx.fillStyle="rgba(0,0,0,0.55)"; ctx.fillRect(5,5,42,13);
      ctx.beginPath(); ctx.arc(11,11,3,0,Math.PI*2);
      ctx.fillStyle=pulse?"rgba(239,68,68,1)":"rgba(239,68,68,0.35)"; ctx.fill();
      ctx.fillStyle="rgba(255,255,255,0.85)"; ctx.font="bold 6px sans-serif"; ctx.textAlign="left";
      ctx.fillText("LIVE", 16, 14);

      animRef.current = requestAnimationFrame(render);
    };
    animRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  return (
    <canvas ref={canvasRef} width={900} height={560} className="w-full h-full" style={{ display: "block" }} />
  );
}

// ── Video Player ────────────────────────────────────────────────────────────

function VideoPlayer({ src, label, camId }: { src: string; label: string; camId: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  return (
    <div className="relative w-full h-full bg-black">
      <video
        ref={videoRef}
        src={src}
        autoPlay
        muted
        loop
        playsInline
        className="w-full h-full object-cover"
      />
      <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 px-2 py-1 rounded">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
        <span className="text-white text-[10px] font-bold tracking-wider">LIVE · {camId}</span>
      </div>
      <div className="absolute bottom-2 left-2 bg-black/50 px-2 py-0.5 rounded">
        <span className="text-gray-300 text-[10px]">{label}</span>
      </div>
    </div>
  );
}

// ── Split Gate View ─────────────────────────────────────────────────────────

function GateView() {
  return (
    <div className="w-full h-full flex gap-0.5 bg-black">
      <div className="flex-1 relative">
        <VideoPlayer src={VIDEOS.gate_1} label="Gate 1 — North Entry" camId="GATE-01" />
      </div>
      <div className="flex-1 relative">
        <VideoPlayer src={VIDEOS.gate_2} label="Gate 2 — South Entry" camId="GATE-02" />
      </div>
    </div>
  );
}

// ── View Config ─────────────────────────────────────────────────────────────

const VIEW_BUTTONS: { id: View; icon: string; label: string }[] = [
  { id: "split",       icon: "⚡", label: "Stadium + YOLO/LSTM Split" },
  { id: "stadium",     icon: "🏟️", label: "Stadium Map"               },
  { id: "internal",    icon: "📷", label: "Internal"                   },
  { id: "passthrough", icon: "🚶", label: "Passthrough"                },
  { id: "gates",       icon: "🚪", label: "Gates"                      },
  { id: "yolo",        icon: "🤖", label: "YOLO + LSTM Detection"      },
];

// ── Main Component ──────────────────────────────────────────────────────────

export function LivePanel({ zones }: Props) {
  const [view, setView] = useState<View>("split");

  const headerLabel: Record<View, string> = {
    split:       "Stadium Map + YOLO/LSTM Detection",
    stadium:     "Stadium Capacity Map",
    internal:    "Internal Stadium — Live Camera",
    passthrough: "Passthrough — Ticket Verification",
    gates:       "Gate Cameras — Entry Points",
    yolo:        "YOLOv8 + LSTM Anomaly Detection",
  };

  const isLive = view !== "stadium" && view !== "split";

  return (
    <div className="rounded-xl border border-gray-700 flex flex-col overflow-hidden" style={{ background: "#0d1420", height: "680px" }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-700/60 shrink-0 min-w-0">
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`w-2 h-2 rounded-full ${isLive ? "bg-red-500 animate-pulse" : "bg-blue-500"}`} />
          <h2 className="text-xs font-semibold text-white whitespace-nowrap">{headerLabel[view]}</h2>
        </div>
        {/* Toggle tabs — pushed to right, scrollable if needed */}
        <div className="flex items-center gap-0.5 bg-gray-800/80 rounded-lg p-0.5 ml-auto overflow-x-auto scrollbar-hide">
          {VIEW_BUTTONS.map((btn) => (
            <button
              key={btn.id}
              onClick={() => setView(btn.id)}
              title={btn.label}
              className={`flex items-center justify-center w-7 h-7 rounded-md text-base transition-all shrink-0 ${
                view === btn.id
                  ? "bg-blue-600 shadow"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-700/50"
              }`}
            >
              {btn.icon}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {view === "split" && (
          <div className="w-full h-full flex gap-0.5">
            <div className="flex-1 flex flex-col p-1.5 min-w-0">
              <p className="text-[9px] text-gray-500 uppercase tracking-wider px-1 mb-1 shrink-0">Capacity Heatmap</p>
              <div className="flex-1 min-h-0">
                <StadiumMap zones={zones} fillHeight />
              </div>
            </div>
            <div className="w-px bg-gray-700/60 shrink-0" />
            <div className="flex-1 flex flex-col min-w-0">
              <p className="text-[9px] text-cyan-500 uppercase tracking-wider px-2 pt-1.5 mb-1 shrink-0">YOLOv8 + LSTM Detection</p>
              <div className="flex-1 min-h-0 bg-black">
                <YoloCanvas zones={zones} />
              </div>
            </div>
          </div>
        )}
        {view === "stadium" && (
          <div className="w-full h-full flex flex-col p-2">
            <StadiumMap zones={zones} fillHeight />
          </div>
        )}
        {view === "internal" && (
          <VideoPlayer src={VIDEOS.internal} label="Internal Stadium — Crowd Tracking" camId="INT-01" />
        )}
        {view === "passthrough" && (
          <VideoPlayer src={VIDEOS.passthrough} label="Passthrough — Viewers Entering Stadium" camId="PASS-01" />
        )}
        {view === "gates" && <GateView />}
        {view === "yolo" && (
          <div className="w-full h-full bg-black">
            <YoloCanvas zones={zones} />
          </div>
        )}
      </div>
    </div>
  );
}
