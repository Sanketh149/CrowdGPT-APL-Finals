/**
 * StadiumMap — SVG-based stadium zone map with live crowd density heatmap.
 * Each zone is colour-coded green → yellow → orange → red by occupancy %.
 */

import React from "react";
import type { Zone } from "../types";

interface Props {
  zones: Zone[];
  onZoneClick?: (zone: Zone) => void;
}

// SVG viewport dimensions
const SVG_W = 600;
const SVG_H = 440;

// Pre-defined zone SVG rectangles that approximate a cricket oval stadium
// Layout: North/South/East/West stands around the perimeter,
// VIP Pavilion on the west inner-lower, Media Center top-inner strip
const ZONE_LAYOUT: Record<
  string,
  { x: number; y: number; w: number; h: number; label: string }
> = {
  north_stand:  { x: 150, y: 8,   w: 300, h: 80,  label: "North Stand"  },
  south_stand:  { x: 150, y: 352, w: 300, h: 80,  label: "South Stand"  },
  east_stand:   { x: 478, y: 110, w: 112, h: 220, label: "East Stand"   },
  west_stand:   { x: 10,  y: 110, w: 112, h: 220, label: "West Stand"   },
  vip_pavilion: { x: 130, y: 148, w: 110, h: 144, label: "VIP Pavilion" },
  media_center: { x: 360, y: 148, w: 110, h: 144, label: "Media Center" },
};

// Centre pitch ellipse — sits in the middle with clear space around it
const PITCH = { cx: 300, cy: 220, rx: 52, ry: 38 };

// Density colour mapping
function densityColor(pct: number): string {
  if (pct > 0.90) return "#ef4444"; // red-500
  if (pct > 0.75) return "#f97316"; // orange-500
  if (pct > 0.60) return "#eab308"; // yellow-500
  if (pct > 0.40) return "#84cc16"; // lime-500
  return "#22c55e";                 // green-500
}

function densityOpacity(pct: number): number {
  return 0.3 + pct * 0.5; // 0.3 – 0.8 opacity range
}

function ZoneCell({
  zone,
  layout,
  onClick,
}: {
  zone: Zone | undefined;
  layout: (typeof ZONE_LAYOUT)[string];
  onClick?: () => void;
}) {
  const pct = zone?.capacity_pct ?? 0;
  const fill = densityColor(pct);
  const opacity = densityOpacity(pct);
  const isHotspot = zone?.is_hotspot ?? false;

  return (
    <g
      className="cursor-pointer"
      onClick={onClick}
      role="button"
      aria-label={`${layout.label}: ${(pct * 100).toFixed(0)}% capacity`}
    >
      <rect
        x={layout.x}
        y={layout.y}
        width={layout.w}
        height={layout.h}
        rx={8}
        ry={8}
        fill={fill}
        fillOpacity={opacity}
        stroke={isHotspot ? "#fbbf24" : "#374151"}
        strokeWidth={isHotspot ? 2.5 : 1}
        className="transition-all duration-500"
      />
      {/* Hotspot pulse ring */}
      {isHotspot && (
        <rect
          x={layout.x - 3}
          y={layout.y - 3}
          width={layout.w + 6}
          height={layout.h + 6}
          rx={11}
          ry={11}
          fill="none"
          stroke="#fbbf24"
          strokeWidth={1.5}
          opacity={0.5}
          className="animate-ping"
        />
      )}
      {/* Zone label */}
      <text
        x={layout.x + layout.w / 2}
        y={layout.y + layout.h / 2 - 6}
        textAnchor="middle"
        fill="white"
        fontSize={10}
        fontWeight="600"
        className="select-none"
      >
        {layout.label}
      </text>
      {/* Density percentage */}
      <text
        x={layout.x + layout.w / 2}
        y={layout.y + layout.h / 2 + 10}
        textAnchor="middle"
        fill="white"
        fontSize={13}
        fontWeight="700"
        className="select-none"
      >
        {(pct * 100).toFixed(0)}%
      </text>
      {/* Person count */}
      {zone && (
        <text
          x={layout.x + layout.w / 2}
          y={layout.y + layout.h / 2 + 24}
          textAnchor="middle"
          fill="rgba(255,255,255,0.7)"
          fontSize={9}
          className="select-none"
        >
          {zone.current_count.toLocaleString()} / {zone.capacity.toLocaleString()}
        </text>
      )}
    </g>
  );
}

export function StadiumMap({ zones, onZoneClick }: Props) {
  const zoneMap = Object.fromEntries(zones.map((z) => [z.zone_id, z]));

  return (
    <div className="bg-gray-800 rounded-xl p-3 border border-gray-700">
      <div className="flex items-center justify-between mb-2 px-1">
        <h2 className="text-sm font-semibold text-white">Live Stadium Map</h2>
        {/* Legend */}
        <div className="flex items-center gap-3 text-[10px] text-gray-400">
          {[
            { color: "#22c55e", label: "< 40%" },
            { color: "#eab308", label: "60-75%" },
            { color: "#f97316", label: "75-90%" },
            { color: "#ef4444", label: "> 90%" },
          ].map(({ color, label }) => (
            <span key={label} className="flex items-center gap-1">
              <span
                className="inline-block w-2.5 h-2.5 rounded-sm"
                style={{ backgroundColor: color }}
              />
              {label}
            </span>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        width="100%"
        className="max-h-[380px]"
        aria-label="Stadium crowd density map"
      >
        {/* Background */}
        <rect width={SVG_W} height={SVG_H} fill="#111827" rx={12} />

        {/* Outfield (large green oval) */}
        <ellipse
          cx={PITCH.cx}
          cy={PITCH.cy}
          rx={108}
          ry={88}
          fill="#14532d"
          opacity={0.5}
        />
        {/* Boundary circle */}
        <ellipse
          cx={PITCH.cx}
          cy={PITCH.cy}
          rx={108}
          ry={88}
          fill="none"
          stroke="#16a34a"
          strokeWidth={1}
          strokeDasharray="6 4"
          opacity={0.4}
        />
        {/* Inner pitch */}
        <ellipse
          cx={PITCH.cx}
          cy={PITCH.cy}
          rx={PITCH.rx}
          ry={PITCH.ry}
          fill="#15803d"
          stroke="#22c55e"
          strokeWidth={1}
          opacity={0.9}
        />
        <text
          x={PITCH.cx}
          y={PITCH.cy + 4}
          textAnchor="middle"
          fill="rgba(255,255,255,0.5)"
          fontSize={9}
          fontWeight="500"
        >
          PITCH
        </text>

        {/* Zone cells */}
        {Object.entries(ZONE_LAYOUT).map(([zoneId, layout]) => (
          <ZoneCell
            key={zoneId}
            zone={zoneMap[zoneId]}
            layout={layout}
            onClick={() => onZoneClick?.(zoneMap[zoneId])}
          />
        ))}

        {/* Gate markers around the perimeter */}
        {[
          { id: "G1",  cx: 220, cy: 20  },
          { id: "G2",  cx: 300, cy: 20  },
          { id: "G3",  cx: 380, cy: 20  },
          { id: "G4",  cx: 508, cy: 168 },
          { id: "G5",  cx: 508, cy: 272 },
          { id: "G6",  cx: 380, cy: 420 },
          { id: "G7",  cx: 300, cy: 420 },
          { id: "G8",  cx: 220, cy: 420 },
          { id: "G9",  cx: 92,  cy: 272 },
          { id: "G10", cx: 92,  cy: 168 },
          { id: "E1",  cx: 148, cy: 110 },
          { id: "E2",  cx: 452, cy: 110 },
        ].map(({ id, cx, cy }) => (
          <g key={id}>
            <circle
              cx={cx}
              cy={cy}
              r={11}
              fill={id.startsWith("E") ? "#7c3aed" : "#1d4ed8"}
              stroke="#60a5fa"
              strokeWidth={1}
            />
            <text
              x={cx}
              y={cy + 4}
              textAnchor="middle"
              fill="white"
              fontSize={7}
              fontWeight="700"
            >
              {id}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
