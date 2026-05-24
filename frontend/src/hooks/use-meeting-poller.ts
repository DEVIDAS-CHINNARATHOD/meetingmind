"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { meetingService } from "@/services";
import { useMeetingStore } from "@/stores/meeting-store";
import type { ProcessingStatus } from "@/types";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);
const POLL_INTERVAL_MS = 4000;

/**
 * Polls /meetings/:id/status every 4 seconds for a meeting that is
 * actively processing. Stops automatically on completion or failure.
 * Syncs result into both Zustand store and React Query cache.
 */
export function useMeetingStatusPoller(meetingId: string | null) {
  const qc = useQueryClient();
  const { setProcessingStatus } = useMeetingStore();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeRef = useRef(true);

  useEffect(() => {
    if (!meetingId) return;
    activeRef.current = true;

    async function poll() {
      if (!meetingId || !activeRef.current) return;
      try {
        const status: ProcessingStatus = await meetingService.getStatus(meetingId);
        setProcessingStatus(meetingId, status);

        // Invalidate the full meeting cache when completed so detail page refreshes
        if (status.status === "completed") {
          qc.invalidateQueries({ queryKey: ["meeting", meetingId] });
          qc.invalidateQueries({ queryKey: ["meetings"] });
        }

        if (TERMINAL_STATUSES.has(status.status)) {
          clearInterval(timerRef.current!);
          timerRef.current = null;
        }
      } catch {
        // silently ignore transient errors; keep polling
      }
    }

    poll(); // immediate first call
    timerRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      activeRef.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [meetingId, qc, setProcessingStatus]);
}
