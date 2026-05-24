// ── Auth ────────────────────────────────────────────────────

export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "manager" | "viewer";
  is_active: boolean;
  is_verified: boolean;
  avatar_url: string | null;
  workspace_id: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ── Meetings ─────────────────────────────────────────────────

export type MeetingStatus =
  | "pending"
  | "uploading"
  | "processing"
  | "transcribing"
  | "summarizing"
  | "completed"
  | "failed";

export type MeetingSource = "upload" | "zoom" | "google_meet" | "teams";

export interface Meeting {
  id: string;
  title: string;
  status: MeetingStatus;
  source: MeetingSource;
  original_filename: string | null;
  file_size_bytes: number | null;
  duration_seconds: number | null;
  language: string | null;
  word_count: number | null;
  summary: string | null;
  mom: string | null;
  key_decisions: string[] | null;
  topics: string[] | null;
  processing_error: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface MeetingDetail extends Meeting {
  transcript: string | null;
  participants: Participant[];
  action_items: ActionItem[];
  transcript_segments: TranscriptSegment[];
}

export interface MeetingListResponse {
  items: Meeting[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ProcessingStatus {
  meeting_id: string;
  status: MeetingStatus;
  progress_percent: number | null;
  current_step: string | null;
  error: string | null;
}

// ── Participants & Transcript ────────────────────────────────

export interface Participant {
  id: string;
  name: string;
  speaker_label: string | null;
  talk_time_seconds: number | null;
  word_count: number | null;
}

export interface TranscriptSegment {
  id: string;
  speaker_label: string | null;
  speaker_name: string | null;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number | null;
  segment_index: number;
}

export interface ActionItem {
  id: string;
  task: string;
  assigned_to: string | null;
  deadline: string | null;
  is_completed: boolean;
  priority: "low" | "medium" | "high" | null;
  created_at: string;
}

// ── AI ───────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  model?: string;
  timestamp: string;
  isStreaming?: boolean;
}

export interface ChatSource {
  meeting_id: string;
  meeting_title: string;
  speaker: string | null;
  timestamp_seconds: number | null;
  excerpt: string;
  relevance: number;
}

export interface ChatRequest {
  question: string;
  meeting_ids?: string[];
  top_k?: number;
}

// ── Analytics ────────────────────────────────────────────────

export interface WorkspaceOverview {
  period_days: number;
  total_meetings: number;
  meetings_in_period: number;
  total_hours_recorded: number;
  total_words_transcribed: number;
  avg_meeting_minutes: number;
  open_action_items: number;
  completed_action_items: number;
  action_completion_rate_pct: number;
}

export interface SpeakerStat {
  name: string;
  total_talk_time_seconds: number;
  total_talk_time_minutes: number;
  total_words: number;
  meetings_attended: number;
  participation_pct: number;
}

export interface FrequencyPoint {
  date: string;
  meetings: number;
}

// ── Reports ──────────────────────────────────────────────────

export interface Report {
  id: string;
  meeting_id: string;
  report_type: "mom" | "transcript" | "analytics" | "summary";
  format: "pdf" | "docx" | "txt" | "md";
  file_size_bytes: number | null;
  download_count: number;
  created_at: string;
}

// ── Team ─────────────────────────────────────────────────────

export interface TeamMember extends User {
  workspace_id: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: "free" | "pro" | "enterprise";
  monthly_meeting_limit: number;
  storage_limit_gb: number;
  member_count: number;
  created_at: string;
}

// ── Identities ───────────────────────────────────────────────

export interface Identity {
  id: string;
  name: string;
  email: string | null;
  photo_url: string | null;
  workspace_id: string;
}

// ── Integrations ─────────────────────────────────────────────

export interface BotSession {
  meeting_id: string;
  platform: "zoom" | "google_meet";
  title: string;
  status: string;
  celery_task_id: string | null;
  created_at: string;
}

// ── Search ───────────────────────────────────────────────────

export interface SearchResult {
  meeting_id: string;
  title: string;
  created_at: string | null;
  match_type: "text" | "semantic" | "hybrid";
  snippet: string;
  speaker?: string | null;
  timestamp_seconds?: number | null;
  score: number | null;
}

export interface SearchResponse {
  query: string;
  mode: string;
  count: number;
  results: SearchResult[];
}

// ── Pagination ───────────────────────────────────────────────

export interface PaginationParams {
  page?: number;
  page_size?: number;
}

// ── API error ────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status: number;
}
