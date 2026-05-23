/**
 * AlertPanel — Active alerts with severity colour coding.
 * Alerts are colour-coded: INFO (blue) / WARNING (yellow) / CRITICAL (red).
 * Operators can acknowledge alerts from this panel.
 */

import React, { useState } from "react";
import type { Alert, AlertSeverity } from "../types";
import { acknowledgeAlert } from "../api";

interface Props {
  alerts: Alert[];
  onAcknowledge?: (alertId: string) => void;
}

const SEVERITY_CONFIG: Record<
  AlertSeverity,
  { bg: string; border: string; badge: string; icon: string; label: string }
> = {
  INFO:     { bg: "bg-blue-900/20",   border: "border-blue-700/50",   badge: "bg-blue-700 text-blue-100",   icon: "ℹ️",  label: "INFO"     },
  WARNING:  { bg: "bg-yellow-900/20", border: "border-yellow-700/50", badge: "bg-yellow-700 text-yellow-100", icon: "⚠️", label: "WARNING"  },
  CRITICAL: { bg: "bg-red-900/20",    border: "border-red-700/50",    badge: "bg-red-700 text-red-100",     icon: "🚨", label: "CRITICAL" },
};

const CHANNEL_LABELS: Record<string, string> = {
  operator:    "Operator",
  field_staff: "Field Staff",
  public_pa:   "Public PA",
};

function AlertItem({
  alert,
  onAck,
  isAcking,
}: {
  alert: Alert;
  onAck: (id: string) => void;
  isAcking: boolean;
}) {
  const cfg = SEVERITY_CONFIG[alert.severity] ?? SEVERITY_CONFIG.INFO;
  const time = new Date(alert.timestamp).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <li
      className={`rounded-lg border p-3 ${cfg.bg} ${cfg.border} ${
        alert.severity === "CRITICAL" ? "animate-pulse-once" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${cfg.badge}`}>
            {cfg.icon} {cfg.label}
          </span>
          <span className="text-[9px] text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded">
            {CHANNEL_LABELS[alert.channel] ?? alert.channel}
          </span>
          {alert.zone_id && (
            <span className="text-[9px] text-gray-400">
              Zone: {alert.zone_id.replace(/_/g, " ")}
            </span>
          )}
        </div>
        <span className="text-[9px] text-gray-500 font-mono shrink-0">{time}</span>
      </div>

      <p className="text-xs text-gray-300 mt-1.5 leading-relaxed">{alert.message}</p>

      {alert.actions_required.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {alert.actions_required.map((action, idx) => (
            <li key={idx} className="flex items-start gap-1 text-[10px] text-gray-400">
              <span className="text-gray-600 mt-0.5">→</span>
              {action}
            </li>
          ))}
        </ul>
      )}

      {!alert.acknowledged && (
        <div className="mt-2 flex justify-end">
          <button
            onClick={() => onAck(alert.alert_id)}
            disabled={isAcking}
            className={`text-[10px] px-2 py-1 rounded font-semibold transition-colors ${
              isAcking
                ? "bg-gray-700 text-gray-500 cursor-not-allowed"
                : "bg-gray-700 hover:bg-gray-600 text-gray-300"
            }`}
          >
            {isAcking ? "Acknowledging..." : "Acknowledge"}
          </button>
        </div>
      )}
    </li>
  );
}

export function AlertPanel({ alerts, onAcknowledge }: Props) {
  const [ackingIds, setAckingIds] = useState<Set<string>>(new Set());
  const [ackError, setAckError] = useState<string | null>(null);

  const activeAlerts = alerts.filter((a) => !a.acknowledged);
  const criticalCount = activeAlerts.filter((a) => a.severity === "CRITICAL").length;

  const handleAcknowledge = async (alertId: string) => {
    setAckingIds((prev) => new Set(prev).add(alertId));
    setAckError(null);
    try {
      await acknowledgeAlert(alertId, "operator");
      onAcknowledge?.(alertId);
    } catch (err) {
      setAckError(err instanceof Error ? err.message : "Acknowledge failed");
    } finally {
      setAckingIds((prev) => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }
  };

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-white">Alerts</h2>
          {activeAlerts.length > 0 && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                criticalCount > 0
                  ? "bg-red-700 text-red-100"
                  : "bg-yellow-700 text-yellow-100"
              }`}
            >
              {activeAlerts.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[9px]">
          <span className="text-red-400">{criticalCount} critical</span>
          <span className="text-gray-500">{activeAlerts.length - criticalCount} other</span>
        </div>
      </div>

      {/* Error */}
      {ackError && (
        <div className="mx-2 mt-2 px-2 py-1 bg-red-900/30 border border-red-700 rounded text-[10px] text-red-400">
          {ackError}
        </div>
      )}

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto p-2">
        {activeAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2 py-8">
            <span className="text-3xl">✅</span>
            <p className="text-xs text-gray-500">No active alerts</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {/* Show CRITICAL first */}
            {[...activeAlerts]
              .sort((a, b) => {
                const order: Record<AlertSeverity, number> = { CRITICAL: 0, WARNING: 1, INFO: 2 };
                return order[a.severity] - order[b.severity];
              })
              .map((alert) => (
                <AlertItem
                  key={alert.alert_id}
                  alert={alert}
                  onAck={handleAcknowledge}
                  isAcking={ackingIds.has(alert.alert_id)}
                />
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}
