import React, { useEffect, useRef } from "react";
import type { Zone } from "../types";

interface Props {
  zones: Zone[];
}

interface Person {
  x: number;
  y: number;
  vx: number;
  vy: number;
  zone: string;
  size: number;
}

const CANVAS_ZONES: Record<string, { x: number; y: number; w: number; h: number }> = {
  north_stand:  { x: 150, y: 10,  w: 300, h: 90  },
  south_stand:  { x: 150, y: 340, w: 300, h: 90  },
  east_stand:   { x: 470, y: 120, w: 120, h: 200 },
  west_stand:   { x: 10,  y: 120, w: 120, h: 200 },
  vip_pavilion: { x: 200, y: 155, w: 200, h: 130 },
  media_center: { x: 230, y: 100, w: 140, h: 50  },
};

function densityColor(pct: number): [number, number, number] {
  if (pct > 0.90) return [239, 68, 68];
  if (pct > 0.75) return [249, 115, 22];
  if (pct > 0.60) return [234, 179, 8];
  if (pct > 0.40) return [132, 204, 22];
  return [34, 197, 94];
}

export function VideoFeed({ zones }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personsRef = useRef<Person[]>([]);
  const frameRef = useRef(0);
  const animRef = useRef(0);
  const zonesRef = useRef(zones);

  useEffect(() => { zonesRef.current = zones; }, [zones]);

  useEffect(() => {
    const persons: Person[] = [];
    zones.forEach((zone) => {
      const layout = CANVAS_ZONES[zone.zone_id];
      if (!layout) return;
      const count = Math.max(4, Math.floor(zone.capacity_pct * 50));
      for (let i = 0; i < count; i++) {
        persons.push({
          x: layout.x + 4 + Math.random() * (layout.w - 8),
          y: layout.y + 4 + Math.random() * (layout.h - 8),
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          zone: zone.zone_id,
          size: 1.5 + Math.random() * 1.5,
        });
      }
    });
    personsRef.current = persons;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const sx = W / 600;
    const sy = H / 440;

    const draw = () => {
      frameRef.current++;
      const f = frameRef.current;
      const zoneMap = Object.fromEntries(zonesRef.current.map((z) => [z.zone_id, z]));

      // Background
      ctx.fillStyle = "#060b14";
      ctx.fillRect(0, 0, W, H);

      // Scanlines
      for (let y = 0; y < H; y += 4) {
        ctx.fillStyle = "rgba(0,0,0,0.15)";
        ctx.fillRect(0, y, W, 1);
      }

      // Zone heatmap overlays
      Object.entries(CANVAS_ZONES).forEach(([zoneId, l]) => {
        const z = zoneMap[zoneId];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityColor(pct);
        const x = l.x * sx, y = l.y * sy, w = l.w * sx, h = l.h * sy;

        const grad = ctx.createRadialGradient(x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, Math.max(w, h) * 0.6);
        grad.addColorStop(0, `rgba(${r},${g},${b},${0.15 + pct * 0.2})`);
        grad.addColorStop(1, `rgba(${r},${g},${b},0.02)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        (ctx as any).roundRect?.(x, y, w, h, 6) ?? ctx.rect(x, y, w, h);
        ctx.fill();

        ctx.strokeStyle = `rgba(${r},${g},${b},${0.3 + pct * 0.3})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();

        // Zone label
        ctx.fillStyle = `rgba(${r},${g},${b},0.9)`;
        ctx.font = `bold ${7 * sx}px monospace`;
        ctx.textAlign = "center";
        ctx.fillText(`${(pct * 100).toFixed(0)}%`, (x + w / 2), y + h - 4 * sy);
      });

      // Outfield
      ctx.fillStyle = "rgba(16, 68, 36, 0.5)";
      ctx.beginPath();
      ctx.ellipse(300 * sx, 220 * sy, 115 * sx, 88 * sy, 0, 0, Math.PI * 2);
      ctx.fill();

      // Pitch
      const pitchGrad = ctx.createRadialGradient(300 * sx, 220 * sy, 0, 300 * sx, 220 * sy, 60 * sx);
      pitchGrad.addColorStop(0, "rgba(21,128,61,0.8)");
      pitchGrad.addColorStop(1, "rgba(16,68,36,0.6)");
      ctx.fillStyle = pitchGrad;
      ctx.beginPath();
      ctx.ellipse(300 * sx, 220 * sy, 60 * sx, 45 * sy, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(34,197,94,0.4)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Persons
      const persons = personsRef.current;
      persons.forEach((p) => {
        const l = CANVAS_ZONES[p.zone];
        if (!l) return;
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < l.x + 2 || p.x > l.x + l.w - 2) p.vx *= -1;
        if (p.y < l.y + 2 || p.y > l.y + l.h - 2) p.vy *= -1;

        const z = zoneMap[p.zone];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityColor(pct);

        ctx.beginPath();
        ctx.arc(p.x * sx, p.y * sy, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${b},0.85)`;
        ctx.fill();
      });

      // YOLO detection boxes — cycle through persons slowly
      const boxSlots = Math.min(8, Math.floor(persons.length / 6));
      ctx.font = `${5.5 * sx}px monospace`;
      for (let i = 0; i < boxSlots; i++) {
        const idx = Math.floor((f * 0.7 + i * 23) % persons.length);
        const p = persons[idx];
        if (!p) continue;
        const bx = (p.x - 5) * sx;
        const by = (p.y - 8) * sy;
        const bw = 10 * sx;
        const bh = 14 * sy;
        const conf = 0.82 + Math.sin(f * 0.03 + i) * 0.1;
        ctx.strokeStyle = "rgba(34,211,238,0.75)";
        ctx.lineWidth = 0.7;
        ctx.strokeRect(bx, by, bw, bh);
        ctx.fillStyle = "rgba(34,211,238,0.85)";
        ctx.textAlign = "left";
        ctx.fillText(`${(conf).toFixed(2)}`, bx, by - 1.5 * sy);
      }

      // Corner brackets (camera overlay style)
      const bracketSize = 12;
      ctx.strokeStyle = "rgba(34,211,238,0.4)";
      ctx.lineWidth = 1.5;
      const corners = [[0,0],[W,0],[0,H],[W,H]];
      corners.forEach(([cx, cy]) => {
        const dx = cx === 0 ? 1 : -1;
        const dy = cy === 0 ? 1 : -1;
        ctx.beginPath();
        ctx.moveTo(cx + dx * bracketSize, cy);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx, cy + dy * bracketSize);
        ctx.stroke();
      });

      // LIVE indicator
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(6, 5, 50, 14);
      const livePulse = Math.sin(f * 0.06) > 0;
      ctx.beginPath();
      ctx.arc(13, 12, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = livePulse ? "rgba(239,68,68,1)" : "rgba(239,68,68,0.4)";
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.font = `bold ${7 * sx}px sans-serif`;
      ctx.textAlign = "left";
      ctx.fillText("LIVE", 19, 14);

      // Stats bar bottom
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(0, H - 16, W, 16);
      ctx.fillStyle = "rgba(34,211,238,0.7)";
      ctx.font = `${6.5 * sx}px monospace`;
      ctx.textAlign = "left";
      ctx.fillText(`YOLOv8n · ${persons.length} persons · LSTM anomaly: OFF`, 6, H - 5);
      ctx.textAlign = "right";
      ctx.fillStyle = "rgba(255,255,255,0.4)";
      ctx.fillText(`${(29.8 + Math.sin(f * 0.02) * 0.4).toFixed(1)} fps`, W - 6, H - 5);

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden flex flex-col h-full min-h-[200px]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-white">Live Camera Feed</h2>
          <span className="text-[10px] text-cyan-400 bg-cyan-950 border border-cyan-800 px-1.5 py-0.5 rounded font-medium">
            YOLOv8 + Simulation
          </span>
        </div>
        <span className="text-[10px] text-gray-500 font-mono">CAM-01 · Overview</span>
      </div>
      <div className="flex-1 relative bg-black">
        <canvas
          ref={canvasRef}
          width={600}
          height={440}
          className="w-full h-full"
          style={{ display: "block" }}
        />
      </div>
    </div>
  );
}
