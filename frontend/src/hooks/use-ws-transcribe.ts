"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const WS_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    .replace(/^http/, "ws");

export type WsSegment = {
  text: string;
  start: number;
  end: number;
  is_final: boolean;
  meeting_id: string;
};

export type WsStatus = "idle" | "connecting" | "connected" | "transcribing" | "stopped" | "error";

interface UseWsTranscribeOptions {
  meetingId: string;
  token: string;
  onSegment?: (seg: WsSegment) => void;
}

/**
 * Manages a WebSocket connection to /ws/transcribe.
 * Exposes:
 *   - status       current connection state
 *   - segments     all received transcript segments
 *   - connect()    open the WebSocket
 *   - sendAudio()  push raw PCM bytes (Int16Array)
 *   - stop()       send stop signal and close
 */
export function useWsTranscribe({ meetingId, token, onSegment }: UseWsTranscribeOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WsStatus>("idle");
  const [segments, setSegments] = useState<WsSegment[]>([]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setStatus("connecting");

    const url = `${WS_BASE}/ws/transcribe?meeting_id=${meetingId}&token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        if (msg.type === "status") {
          setStatus(msg.status as WsStatus);
        } else if (msg.type === "segment") {
          const seg = msg as WsSegment;
          setSegments((prev) => [...prev, seg]);
          onSegment?.(seg);
        } else if (msg.type === "error") {
          console.error("[WS] Server error:", msg.message);
          setStatus("error");
        }
      } catch {
        // binary frame or malformed JSON — ignore
      }
    };

    ws.onerror = () => setStatus("error");
    ws.onclose = () => setStatus("stopped");
  }, [meetingId, token, onSegment]);

  const sendAudio = useCallback((pcmInt16: Int16Array) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(pcmInt16.buffer);
    }
  }, []);

  const stop = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }
    wsRef.current?.close();
    setStatus("stopped");
  }, []);

  const clearSegments = useCallback(() => setSegments([]), []);

  // cleanup on unmount
  useEffect(() => () => { wsRef.current?.close(); }, []);

  return { status, segments, connect, sendAudio, stop, clearSegments };
}
