import { api, get, post, patch, del } from "./api-client";
import type {
  Meeting, MeetingDetail, MeetingListResponse, ProcessingStatus,
  ActionItem, WorkspaceOverview, SpeakerStat, FrequencyPoint,
  ChatMessage, SearchResponse, Identity, BotSession, TeamMember,
  Workspace, Report, TokenResponse, User,
} from "@/types";

// ═══════════════════════════════════════════════════════════════
// Auth
// ═══════════════════════════════════════════════════════════════

export const authService = {
  login: (email: string, password: string) =>
    post<TokenResponse>("/auth/login", { email, password }),

  register: (data: {
    name: string;
    email: string;
    password: string;
    workspace: { name: string; slug: string };
  }) => post<TokenResponse>("/auth/register", data),

  logout: (refreshToken: string) =>
    post("/auth/logout", { refresh_token: refreshToken }),

  me: () => get<User>("/auth/me"),
};

// ═══════════════════════════════════════════════════════════════
// Meetings
// ═══════════════════════════════════════════════════════════════

export const meetingService = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    get<MeetingListResponse>("/meetings", { params }),

  get: (id: string) => get<MeetingDetail>(`/meetings/${id}`),

  upload: (formData: FormData, onProgress?: (pct: number) => void) =>
    api.post<Meeting>("/meetings/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    }).then((r) => r.data),

  getStatus: (id: string) => get<ProcessingStatus>(`/meetings/${id}/status`),

  update: (id: string, data: { title?: string }) =>
    patch<Meeting>(`/meetings/${id}`, data),

  delete: (id: string) => del(`/meetings/${id}`),
};

// ═══════════════════════════════════════════════════════════════
// Action Items
// ═══════════════════════════════════════════════════════════════

export const actionItemService = {
  list: (params?: { completed?: boolean; assigned_to?: string }) =>
    get<ActionItem[]>("/action-items", { params }),

  update: (id: string, data: Partial<ActionItem>) =>
    patch<ActionItem>(`/action-items/${id}`, data),

  delete: (id: string) => del(`/action-items/${id}`),
};

// ═══════════════════════════════════════════════════════════════
// AI
// ═══════════════════════════════════════════════════════════════

export const aiService = {
  /** Non-streaming chat (for fallback) */
  chat: (question: string, meetingIds?: string[]) =>
    post<{ answer: string; sources: ChatMessage["sources"]; model_used: string }>("/ai/chat", {
      question,
      meeting_ids: meetingIds,
      top_k: 5,
    }),

  /** Streaming chat — returns a ReadableStream of SSE events */
  streamChat: async (
    question: string,
    meetingIds: string[] | undefined,
    onToken: (token: string) => void,
    onDone: (sources: ChatMessage["sources"]) => void,
    onError: (msg: string) => void
  ) => {
    const accessToken =
      typeof window !== "undefined" ? localStorage.getItem("mm_access_token") : null;

    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/ai/chat/stream`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ question, meeting_ids: meetingIds, top_k: 5 }),
      }
    );

    if (!res.ok || !res.body) {
      onError("Stream request failed");
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "content") onToken(event.text ?? "");
          if (event.type === "done") onDone(event.sources ?? []);
          if (event.type === "error") onError(event.message ?? "Unknown error");
        } catch {
          // malformed line — skip
        }
      }
    }
  },

  summarize: (meetingId: string, regenerate = false) =>
    post("/ai/summarize", { meeting_id: meetingId, regenerate }),

  generateMom: (meetingId: string, regenerate = false) =>
    post<{ mom: string }>("/ai/generate-mom", { meeting_id: meetingId, regenerate }),
};

// ═══════════════════════════════════════════════════════════════
// Analytics
// ═══════════════════════════════════════════════════════════════

export const analyticsService = {
  overview: (days = 30) =>
    get<WorkspaceOverview>("/analytics/overview", { params: { days } }),

  meetingFrequency: (days = 30) =>
    get<{ data: FrequencyPoint[]; period_days: number }>(
      "/analytics/meeting-frequency",
      { params: { days } }
    ),

  speakers: (limit = 10) =>
    get<{ speakers: SpeakerStat[] }>("/analytics/speakers", { params: { limit } }),

  meetingSpeakers: (meetingId: string) =>
    get(`/analytics/meetings/${meetingId}/speakers`),
};

// ═══════════════════════════════════════════════════════════════
// Reports
// ═══════════════════════════════════════════════════════════════

export const reportService = {
  download: (
    meetingId: string,
    fmt: "pdf" | "docx" | "txt" | "md" = "pdf",
    reportType = "mom"
  ) => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("mm_access_token") : "";
    const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/reports/${meetingId}/download?fmt=${fmt}&report_type=${reportType}`;
    // Trigger browser download
    const a = document.createElement("a");
    a.href = url;
    a.download = `meeting_${reportType}.${fmt}`;
    // Must pass auth header → use fetch + blob for proper auth
    return fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.blob())
      .then((blob) => {
        const blobUrl = URL.createObjectURL(blob);
        a.href = blobUrl;
        a.click();
        URL.revokeObjectURL(blobUrl);
      });
  },
};

// ═══════════════════════════════════════════════════════════════
// Speakers
// ═══════════════════════════════════════════════════════════════

export const speakerService = {
  list: (meetingId: string) =>
    get<{ meeting_id: string; speakers: Array<{ id: string; speaker_label: string; name: string; talk_time_seconds: number; word_count: number; is_named: boolean }> }>(
      `/speakers/meetings/${meetingId}`
    ),

  rename: (meetingId: string, speakerLabel: string, newName: string) =>
    post(`/speakers/meetings/${meetingId}/rename`, {
      speaker_label: speakerLabel,
      new_name: newName,
    }),

  bulkRename: (meetingId: string, mappings: Record<string, string>) =>
    post(`/speakers/meetings/${meetingId}/bulk-rename`, { mappings }),
};

// ═══════════════════════════════════════════════════════════════
// Search
// ═══════════════════════════════════════════════════════════════

export const searchService = {
  search: (q: string, mode: "text" | "semantic" | "hybrid" = "hybrid") =>
    get<SearchResponse>("/search", { params: { q, mode } }),
};

// ═══════════════════════════════════════════════════════════════
// Team
// ═══════════════════════════════════════════════════════════════

export const teamService = {
  members: () => get<TeamMember[]>("/team/members"),

  invite: (data: { name: string; email: string; role: string }) =>
    post<{ message: string; invited_email: string; temp_access_token: string }>(
      "/team/invite",
      data
    ),

  updateRole: (userId: string, role: string) =>
    patch(`/team/members/${userId}/role`, { role }),

  remove: (userId: string) => del(`/team/members/${userId}`),

  workspace: () => get<Workspace>("/team/workspace"),
};

// ═══════════════════════════════════════════════════════════════
// Identities
// ═══════════════════════════════════════════════════════════════

export const identityService = {
  list: () => get<Identity[]>("/identities"),

  enroll: (formData: FormData) =>
    api
      .post<Identity>("/identities/enroll", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      .then((r) => r.data),

  delete: (id: string) => del(`/identities/${id}`),

  recognize: (meetingId: string) =>
    post<{ task_id: string }>(`/identities/meetings/${meetingId}/recognize`),
};

// ═══════════════════════════════════════════════════════════════
// Integrations
// ═══════════════════════════════════════════════════════════════

export const integrationService = {
  zoomJoin: (meetingNumber: string, password: string, title?: string) =>
    post<BotSession>("/integrations/zoom/join", {
      meeting_number: meetingNumber,
      password,
      title,
    }),

  meetJoin: (meetUrl: string, title?: string) =>
    post<BotSession>("/integrations/meet/join", { meet_url: meetUrl, title }),

  status: () => get<BotSession[]>("/integrations/status"),

  stop: (meetingId: string) =>
    post(`/integrations/${meetingId}/stop`),
};
