import React, { useEffect, useRef, useState } from "react";
import type { Zone } from "../types";
import { StadiumMap } from "./StadiumMap";

interface Props {
  zones: Zone[];
}

type View = "live" | "stadium" | "yolo";

// Replace with any YouTube video ID of IPL crowd footage
const YT_VIDEO_ID = "VV3mTfKGKYI";

// ── YOLO Canvas ────────────────────────────────────────────────────────────

interface Person {
  x: number; y: number;
  vx: number; vy: number;
  zone: string;
  size: number;
  wobble: number;
  wobbleSpeed: number;
}

const ZONE_LAYOUT: Record<string, { x: number; y: number; w: number; h: number }> = {
  north_stand:  { x: 148, y: 6,   w: 204, h: 56  },
  south_stand:  { x: 148, y: 258, w: 204, h: 56  },
  east_stand:   { x: 432, y: 74,  w: 76,  h: 152 },
  west_stand:   { x: 8,   y: 74,  w: 76,  h: 152 },
  vip_pavilion: { x: 90,  y: 102, w: 74,  h: 100 },
  media_center: { x: 346, y: 102, w: 74,  h: 100 },
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

  useEffect(() => {
    personsRef.current = buildPersons(zones);
  }, []); // eslint-disable-line

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

      // Background
      ctx.fillStyle = "#06101c";
      ctx.fillRect(0, 0, CW, CH);
      for (let y = 0; y < CH; y += 3) {
        ctx.fillStyle = "rgba(0,0,0,0.1)";
        ctx.fillRect(0, y, CW, 1);
      }

      // Zone heatmap
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
        // YOLO zone box
        ctx.strokeStyle = `rgba(${r},${g},${b},${0.5+pct*0.3})`;
        ctx.lineWidth = 0.8;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 4);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = `rgba(${r},${g},${b},0.95)`;
        ctx.font = `bold ${6.5}px monospace`;
        ctx.textAlign = "right";
        ctx.fillText(`${(pct*100).toFixed(0)}%`, x+w-3, y+h-3);
      });

      // Outfield
      ctx.fillStyle = "rgba(12,60,28,0.55)";
      ctx.beginPath();
      ctx.ellipse(258*sx, 160*sy, 82*sx, 62*sy, 0, 0, Math.PI*2);
      ctx.fill();
      ctx.strokeStyle = "rgba(22,163,74,0.25)";
      ctx.lineWidth = 0.7;
      ctx.setLineDash([5,4]);
      ctx.stroke();
      ctx.setLineDash([]);
      // Pitch
      ctx.fillStyle = "rgba(21,128,61,0.85)";
      ctx.beginPath();
      ctx.ellipse(258*sx, 160*sy, 42*sx, 30*sy, 0, 0, Math.PI*2);
      ctx.fill();
      ctx.strokeStyle = "rgba(34,197,94,0.35)";
      ctx.lineWidth = 0.6;
      ctx.stroke();

      // Persons + YOLO boxes
      const persons = personsRef.current;
      persons.forEach((p, idx) => {
        const l = ZONE_LAYOUT[p.zone];
        if (!l) return;
        p.wobble += p.wobbleSpeed;
        p.x += p.vx + Math.sin(p.wobble) * 0.03;
        p.y += p.vy + Math.cos(p.wobble * 0.7) * 0.025;
        if (p.x < l.x+2) { p.x = l.x+2; p.vx = Math.abs(p.vx); }
        if (p.x > l.x+l.w-2) { p.x = l.x+l.w-2; p.vx = -Math.abs(p.vx); }
        if (p.y < l.y+2) { p.y = l.y+2; p.vy = Math.abs(p.vy); }
        if (p.y > l.y+l.h-2) { p.y = l.y+l.h-2; p.vy = -Math.abs(p.vy); }
        const z = zoneMap[p.zone];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityRGB(pct);
        const px = p.x * sx, py = p.y * sy;
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI*2);
        ctx.fillStyle = `rgba(${r},${g},${b},0.9)`;
        ctx.fill();
        // Detection box cycling
        const slot1 = Math.floor((f*0.4 + idx*6.7) % persons.length);
        const slot2 = Math.floor((f*0.4 + idx*6.7 + 19) % persons.length);
        const slot3 = Math.floor((f*0.4 + idx*6.7 + 43) % persons.length);
        if (idx === slot1 || idx === slot2 || idx === slot3) {
          const bw = p.size * 6 * sx, bh = p.size * 9 * sy;
          ctx.strokeStyle = "rgba(34,211,238,0.82)";
          ctx.lineWidth = 0.7;
          ctx.strokeRect(px-bw/2, py-bh*0.6, bw, bh);
          const conf = 0.77 + Math.sin(f*0.03+idx) * 0.13;
          ctx.fillStyle = "rgba(34,211,238,0.9)";
          ctx.font = `5px monospace`;
          ctx.textAlign = "left";
          ctx.fillText(`${conf.toFixed(2)}`, px-bw/2+1, py-bh*0.6-1.5);
        }
      });

      // Corner brackets
      const bs = 10;
      ctx.strokeStyle = "rgba(34,211,238,0.4)";
      ctx.lineWidth = 1.2;
      [[0,0],[CW,0],[0,CH],[CW,CH]].forEach(([cx,cy], i) => {
        const dx = i%2===0?1:-1, dy = i<2?1:-1;
        ctx.beginPath();
        ctx.moveTo(cx+dx*bs, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy+dy*bs);
        ctx.stroke();
      });

      // Stats bar
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(0, CH-15, CW, 15);
      ctx.fillStyle = "rgba(34,211,238,0.7)";
      ctx.font = `5.8px monospace`;
      ctx.textAlign = "left";
      ctx.fillText(`YOLOv8n · ${persons.length} detections · ${(29.5+Math.sin(f*0.02)*0.5).toFixed(1)}fps`, 5, CH-5);

      // LIVE
      const pulse = Math.sin(f*0.07) > 0;
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(5, 5, 42, 13);
      ctx.beginPath();
      ctx.arc(11, 11, 3, 0, Math.PI*2);
      ctx.fillStyle = pulse ? "rgba(239,68,68,1)" : "rgba(239,68,68,0.35)";
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.font = `bold 6px sans-serif`;
      ctx.textAlign = "left";
      ctx.fillText("LIVE", 16, 14);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={900}
      height={560}
      className="w-full h-full"
      style={{ display: "block" }}
    />
  );
}

// ── Main LivePanel ─────────────────────────────────────────────────────────

const VIEW_BUTTONS: { id: View; label: string; icon: string }[] = [
  { id: "live",    label: "Live Feed",   icon: "📹" },
  { id: "stadium", label: "Stadium Map", icon: "🏟️" },
  { id: "yolo",    label: "YOLO View",   icon: "🤖" },
];

export function LivePanel({ zones }: Props) {
  const [view, setView] = useState<View>("stadium");

  return (
    <div className="rounded-xl border border-gray-700 flex flex-col h-full overflow-hidden"
      style={{ background: "#0d1420" }}>

      {/* Header with toggle buttons */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700/60 shrink-0">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${view === "live" || view === "yolo" ? "bg-red-500 animate-pulse" : "bg-blue-500"}`} />
          <h2 className="text-sm font-semibold text-white">
            {view === "live" ? "Live Camera Feed" : view === "stadium" ? "Stadium Capacity Map" : "YOLO Detection"}
          </h2>
        </div>

        {/* Toggle buttons */}
        <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-0.5">
          {VIEW_BUTTONS.map((btn) => (
            <button
              key={btn.id}
              onClick={() => setView(btn.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                view === btn.id
                  ? "bg-blue-600 text-white shadow"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <span>{btn.icon}</span>
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {view === "live" && (
          <div className="w-full h-full bg-black relative">
            <iframe
              src={`https://www.youtube.com/embed/${YT_VIDEO_ID}?autoplay=1&mute=1&loop=1&playlist=${YT_VIDEO_ID}&controls=0&modestbranding=1&rel=0`}
              className="w-full h-full"
              allow="autoplay; encrypted-media"
              allowFullScreen
              title="Live Camera Feed"
              style={{ border: "none" }}
            />
            {/* Overlay badge */}
            <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/60 px-2 py-1 rounded">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-white text-[10px] font-bold tracking-wider">LIVE · CAM-01</span>
            </div>
          </div>
        )}

        {view === "stadium" && (
          <div className="w-full h-full overflow-auto p-2">
            <StadiumMap zones={zones} />
          </div>
        )}

        {view === "yolo" && (
          <div className="w-full h-full bg-black">
            <YoloCanvas zones={zones} />
          </div>
        )}
      </div>
    </div>
  );
}
