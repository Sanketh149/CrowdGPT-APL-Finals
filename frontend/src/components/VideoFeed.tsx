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
  wobble: number;
  wobbleSpeed: number;
}

// Viewport: 600×320 internal canvas coords
const CVW = 600;
const CVH = 320;

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
    // More people: up to 120 dots at full capacity
    const count = Math.max(8, Math.floor(zone.capacity_pct * 120));
    for (let i = 0; i < count; i++) {
      out.push({
        x: l.x + 3 + Math.random() * (l.w - 6),
        y: l.y + 3 + Math.random() * (l.h - 6),
        vx: (Math.random() - 0.5) * 0.08,   // very slow
        vy: (Math.random() - 0.5) * 0.08,
        zone: zone.zone_id,
        size: 1.2 + Math.random() * 1.4,
        wobble: Math.random() * Math.PI * 2,
        wobbleSpeed: 0.005 + Math.random() * 0.01,
      });
    }
  });
  return out;
}

export function VideoFeed({ zones }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const personsRef = useRef<Person[]>([]);
  const frameRef = useRef(0);
  const animRef = useRef(0);
  const zonesRef = useRef(zones);

  useEffect(() => { zonesRef.current = zones; }, [zones]);

  useEffect(() => {
    personsRef.current = buildPersons(zones);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const CW = canvas.width;   // actual canvas px
    const CH = canvas.height;
    const sx = CW / CVW;
    const sy = CH / CVH;

    // half-width for split
    const HW = CW / 2;

    const drawBackground = (clipX: number, clipW: number) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipX, 0, clipW, CH);
      ctx.clip();

      // Dark bg
      ctx.fillStyle = "#06101c";
      ctx.fillRect(clipX, 0, clipW, CH);

      // Subtle grain
      for (let i = 0; i < 300; i++) {
        const gx = clipX + Math.random() * clipW;
        const gy = Math.random() * CH;
        ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.025})`;
        ctx.fillRect(gx, gy, 1, 1);
      }

      // Scanlines
      for (let y = 0; y < CH; y += 3) {
        ctx.fillStyle = "rgba(0,0,0,0.12)";
        ctx.fillRect(clipX, y, clipW, 1);
      }

      ctx.restore();
    };

    const drawZoneOverlays = (clipX: number, clipW: number, showBoxes: boolean) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipX, 0, clipW, CH);
      ctx.clip();

      const zoneMap = Object.fromEntries(zonesRef.current.map((z) => [z.zone_id, z]));

      Object.entries(ZONE_LAYOUT).forEach(([zoneId, l]) => {
        const z = zoneMap[zoneId];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityRGB(pct);
        const x = l.x * sx, y = l.y * sy, w = l.w * sx, h = l.h * sy;

        // Heatmap glow
        const grad = ctx.createRadialGradient(x + w / 2, y + h / 2, 0, x + w / 2, y + h / 2, Math.max(w, h) * 0.65);
        grad.addColorStop(0, `rgba(${r},${g},${b},${0.12 + pct * 0.18})`);
        grad.addColorStop(1, `rgba(${r},${g},${b},0.01)`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 5);
        ctx.fill();

        if (showBoxes) {
          // YOLO zone outline
          ctx.strokeStyle = `rgba(${r},${g},${b},${0.5 + pct * 0.3})`;
          ctx.lineWidth = 0.8;
          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          ctx.roundRect(x, y, w, h, 5);
          ctx.stroke();
          ctx.setLineDash([]);

          // Density label
          ctx.fillStyle = `rgba(${r},${g},${b},0.95)`;
          ctx.font = `bold ${6.5 * Math.min(sx, 1)}px monospace`;
          ctx.textAlign = "right";
          ctx.fillText(`${(pct * 100).toFixed(0)}%`, x + w - 3, y + h - 3);
        }
      });

      // Outfield
      ctx.fillStyle = "rgba(12,60,28,0.55)";
      ctx.beginPath();
      ctx.ellipse(250 * sx, 160 * sy, 95 * sx, 72 * sy, 0, 0, Math.PI * 2);
      ctx.fill();

      // Pitch
      const pg = ctx.createRadialGradient(250 * sx, 160 * sy, 0, 250 * sx, 160 * sy, 48 * sx);
      pg.addColorStop(0, "rgba(21,128,61,0.85)");
      pg.addColorStop(1, "rgba(12,60,28,0.5)");
      ctx.fillStyle = pg;
      ctx.beginPath();
      ctx.ellipse(250 * sx, 160 * sy, 48 * sx, 36 * sy, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(34,197,94,0.3)";
      ctx.lineWidth = 0.5;
      ctx.stroke();

      ctx.restore();
    };

    const drawPersons = (clipX: number, clipW: number, yolo: boolean, frame: number) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipX, 0, clipW, CH);
      ctx.clip();

      const zoneMap = Object.fromEntries(zonesRef.current.map((z) => [z.zone_id, z]));
      const persons = personsRef.current;

      persons.forEach((p, idx) => {
        const l = ZONE_LAYOUT[p.zone];
        if (!l) return;

        // Update position (only on left panel to avoid double-update)
        if (!yolo) {
          p.wobble += p.wobbleSpeed;
          p.x += p.vx + Math.sin(p.wobble) * 0.04;
          p.y += p.vy + Math.cos(p.wobble * 0.7) * 0.03;
          if (p.x < l.x + 2) { p.x = l.x + 2; p.vx = Math.abs(p.vx); }
          if (p.x > l.x + l.w - 2) { p.x = l.x + l.w - 2; p.vx = -Math.abs(p.vx); }
          if (p.y < l.y + 2) { p.y = l.y + 2; p.vy = Math.abs(p.vy); }
          if (p.y > l.y + l.h - 2) { p.y = l.y + l.h - 2; p.vy = -Math.abs(p.vy); }
        }

        const z = zoneMap[p.zone];
        const pct = z?.capacity_pct ?? 0;
        const [r, g, b] = densityRGB(pct);
        const px = p.x * sx;
        const py = p.y * sy;

        if (yolo) {
          // YOLO view: brighter dots
          ctx.beginPath();
          ctx.arc(px, py, p.size * 1.1, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${r},${g},${b},0.9)`;
          ctx.fill();

          // Detection box on ~every 10th person, cycling
          const slot = Math.floor((frame * 0.5 + idx * 7.3) % persons.length);
          if (idx === slot || idx === (slot + 17) % persons.length || idx === (slot + 41) % persons.length) {
            const bw = (p.size * 6) * sx;
            const bh = (p.size * 9) * sy;
            ctx.strokeStyle = "rgba(34,211,238,0.8)";
            ctx.lineWidth = 0.7;
            ctx.strokeRect(px - bw / 2, py - bh * 0.6, bw, bh);
            // Confidence label
            const conf = 0.78 + Math.sin(frame * 0.04 + idx) * 0.12;
            ctx.fillStyle = "rgba(34,211,238,0.9)";
            ctx.font = `${5 * Math.min(sx, 1)}px monospace`;
            ctx.textAlign = "left";
            ctx.fillText(`${conf.toFixed(2)}`, px - bw / 2 + 1, py - bh * 0.6 - 1.5);
          }
        } else {
          // Raw view: softer dots with slight blur
          const rg = ctx.createRadialGradient(px, py, 0, px, py, p.size * 2.5);
          rg.addColorStop(0, `rgba(${r},${g},${b},0.7)`);
          rg.addColorStop(1, `rgba(${r},${g},${b},0)`);
          ctx.fillStyle = rg;
          ctx.beginPath();
          ctx.arc(px, py, p.size * 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      ctx.restore();
    };

    const drawOverlayUI = (clipX: number, clipW: number, label: string, frame: number, yolo: boolean) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipX, 0, clipW, CH);
      ctx.clip();

      // Corner brackets
      const bs = 10;
      ctx.strokeStyle = yolo ? "rgba(34,211,238,0.5)" : "rgba(255,255,255,0.2)";
      ctx.lineWidth = 1.2;
      [[clipX + 4, 4], [clipX + clipW - 4, 4], [clipX + 4, CH - 4], [clipX + clipW - 4, CH - 4]].forEach(([cx, cy], i) => {
        const dx = i % 2 === 0 ? 1 : -1;
        const dy = i < 2 ? 1 : -1;
        ctx.beginPath();
        ctx.moveTo(cx + dx * bs, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * bs);
        ctx.stroke();
      });

      // Panel label top-left
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(clipX + 6, 5, 56, 13);
      ctx.fillStyle = yolo ? "rgba(34,211,238,0.95)" : "rgba(255,255,255,0.7)";
      ctx.font = `bold ${6.5 * Math.min(sx, 1)}px monospace`;
      ctx.textAlign = "left";
      ctx.fillText(label, clipX + 9, 14);

      // LIVE dot (left panel only)
      if (!yolo) {
        const pulse = Math.sin(frame * 0.07) > 0;
        ctx.beginPath();
        ctx.arc(clipX + 8, 25, 3, 0, Math.PI * 2);
        ctx.fillStyle = pulse ? "rgba(239,68,68,1)" : "rgba(239,68,68,0.35)";
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.8)";
        ctx.font = `bold ${6 * Math.min(sx, 1)}px sans-serif`;
        ctx.fillText("LIVE", clipX + 13, 28);
      }

      // Bottom stats bar
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(clipX, CH - 15, clipW, 15);
      ctx.fillStyle = yolo ? "rgba(34,211,238,0.7)" : "rgba(160,160,160,0.6)";
      ctx.font = `${5.8 * Math.min(sx, 1)}px monospace`;
      ctx.textAlign = "left";
      const totalPersons = personsRef.current.length;
      ctx.fillText(
        yolo ? `YOLOv8n · ${totalPersons} detections · ${(29.5 + Math.sin(frame * 0.02) * 0.5).toFixed(1)}fps` : `RAW · CAM-01 · Stadium Overview`,
        clipX + 5, CH - 5
      );

      ctx.restore();
    };

    const render = () => {
      const f = frameRef.current++;
      const CW2 = canvas.width;
      const CH2 = canvas.height;
      const HW2 = CW2 / 2;

      // Left: raw feed
      drawBackground(0, HW2);
      drawZoneOverlays(0, HW2, false);
      drawPersons(0, HW2, false, f);
      drawOverlayUI(0, HW2, "RAW FEED", f, false);

      // Right: YOLO
      drawBackground(HW2, HW2);
      drawZoneOverlays(HW2, HW2, true);
      drawPersons(HW2, HW2, true, f);
      drawOverlayUI(HW2, HW2, "YOLO DETECTION", f, true);

      // Divider line
      ctx.strokeStyle = "rgba(34,211,238,0.25)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(HW2, 0);
      ctx.lineTo(HW2, CH2);
      ctx.stroke();
      ctx.setLineDash([]);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden flex flex-col h-full min-h-[200px]">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <h2 className="text-sm font-semibold text-white">Live Camera Feed</h2>
          <span className="text-[10px] text-cyan-400 bg-cyan-950 border border-cyan-800 px-1.5 py-0.5 rounded font-medium">
            Raw · YOLO Split
          </span>
        </div>
        <span className="text-[10px] text-gray-500 font-mono">CAM-01 · Narendra Modi Stadium</span>
      </div>
      <div className="flex-1 relative bg-black">
        <canvas
          ref={canvasRef}
          width={900}
          height={340}
          className="w-full h-full"
          style={{ display: "block" }}
        />
      </div>
    </div>
  );
}
