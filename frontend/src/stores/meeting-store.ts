import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";
import type { Meeting, ChatMessage, ProcessingStatus } from "@/types";

// ═══════════════════════════════════════════════════════════════
// Meeting store
// ═══════════════════════════════════════════════════════════════

interface MeetingStore {
  // List state
  meetings: Meeting[];
  setMeetings: (meetings: Meeting[]) => void;
  upsertMeeting: (meeting: Meeting) => void;
  removeMeeting: (id: string) => void;

  // Active meeting detail
  activeMeetingId: string | null;
  setActiveMeetingId: (id: string | null) => void;

  // Processing status
  processingStatuses: Record<string, ProcessingStatus>;
  setProcessingStatus: (id: string, status: ProcessingStatus) => void;
  processingCount: number;

  // Upload progress
  uploadProgress: Record<string, number>;
  setUploadProgress: (id: string, pct: number) => void;
  clearUploadProgress: (id: string) => void;
}

export const useMeetingStore = create<MeetingStore>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      meetings: [],
      setMeetings: (meetings) => set({ meetings }),
      upsertMeeting: (meeting) =>
        set((state) => {
          const idx = state.meetings.findIndex((m) => m.id === meeting.id);
          if (idx === -1) return { meetings: [meeting, ...state.meetings] };
          const updated = [...state.meetings];
          updated[idx] = meeting;
          return { meetings: updated };
        }),
      removeMeeting: (id) =>
        set((state) => ({
          meetings: state.meetings.filter((m) => m.id !== id),
        })),

      activeMeetingId: null,
      setActiveMeetingId: (id) => set({ activeMeetingId: id }),

      processingStatuses: {},
      setProcessingStatus: (id, status) =>
        set((state) => {
          const statuses = { ...state.processingStatuses, [id]: status };
          const processingCount = Object.values(statuses).filter(
            (s) =>
              s.status !== "completed" &&
              s.status !== "failed" &&
              s.status !== "pending"
          ).length;
          return { processingStatuses: statuses, processingCount };
        }),
      processingCount: 0,

      uploadProgress: {},
      setUploadProgress: (id, pct) =>
        set((state) => ({ uploadProgress: { ...state.uploadProgress, [id]: pct } })),
      clearUploadProgress: (id) =>
        set((state) => {
          const up = { ...state.uploadProgress };
          delete up[id];
          return { uploadProgress: up };
        }),
    })),
    { name: "meeting-store" }
  )
);

// ═══════════════════════════════════════════════════════════════
// Chat store
// ═══════════════════════════════════════════════════════════════

interface ChatStore {
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (patch: Partial<ChatMessage>) => void;
  clearMessages: () => void;
  isStreaming: boolean;
  setStreaming: (v: boolean) => void;
  contextMeetingIds: string[];
  setContextMeetingIds: (ids: string[]) => void;
}

export const useChatStore = create<ChatStore>()(
  devtools(
    (set) => ({
      messages: [
        {
          id: "welcome",
          role: "assistant",
          content:
            "Hi! I'm MeetingMind AI. Ask me anything about your meetings — decisions made, action items, who said what, and more.",
          timestamp: new Date().toISOString(),
        },
      ],
      addMessage: (msg) =>
        set((state) => ({ messages: [...state.messages, msg] })),
      updateLastAssistant: (patch) =>
        set((state) => {
          const msgs = [...state.messages];
          const lastIdx = msgs.length - 1;
          if (msgs[lastIdx]?.role === "assistant") {
            msgs[lastIdx] = { ...msgs[lastIdx], ...patch };
          }
          return { messages: msgs };
        }),
      clearMessages: () =>
        set({
          messages: [
            {
              id: "welcome",
              role: "assistant",
              content:
                "Hi! I'm MeetingMind AI. Ask me anything about your meetings.",
              timestamp: new Date().toISOString(),
            },
          ],
        }),
      isStreaming: false,
      setStreaming: (v) => set({ isStreaming: v }),
      contextMeetingIds: [],
      setContextMeetingIds: (ids) => set({ contextMeetingIds: ids }),
    }),
    { name: "chat-store" }
  )
);

// ═══════════════════════════════════════════════════════════════
// UI store  (sidebar collapse, command palette, etc.)
// ═══════════════════════════════════════════════════════════════

interface UIStore {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  commandOpen: boolean;
  setCommandOpen: (v: boolean) => void;
}

export const useUIStore = create<UIStore>()(
  devtools(
    (set) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      commandOpen: false,
      setCommandOpen: (v) => set({ commandOpen: v }),
    }),
    { name: "ui-store" }
  )
);
