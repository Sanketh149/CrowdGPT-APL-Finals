import { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface BroadcastEvent {
  type: "emergency" | "status";
  protocol: string;
  timestamp: string;
  message: string | null;
  open_gates?: string[];
  run_id?: string;
}

export function useBroadcast() {
  const [event, setEvent] = useState<BroadcastEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const connect = () => {
      const es = new EventSource(`${API_URL}/broadcast/stream`);
      esRef.current = es;
      es.onopen = () => setConnected(true);
      es.onmessage = (e) => {
        try {
          setEvent(JSON.parse(e.data) as BroadcastEvent);
        } catch {}
      };
      es.onerror = () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 3000);
      };
    };
    connect();
    return () => esRef.current?.close();
  }, []);

  return { event, connected };
}
