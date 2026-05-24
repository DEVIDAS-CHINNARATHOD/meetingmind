import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format, parseISO } from "date-fns";

// ── Tailwind class merger ─────────────────────────────────────

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Duration formatting ────────────────────────────────────────

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "—";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

export function formatHours(seconds: number | null | undefined): string {
  if (!seconds) return "0h";
  const h = seconds / 3600;
  return h >= 1 ? `${h.toFixed(1)}h` : `${Math.round(seconds / 60)}m`;
}

// ── Date formatting ────────────────────────────────────────────

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return format(parseISO(iso), "MMM d, yyyy");
  } catch {
    return iso;
  }
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return format(parseISO(iso), "MMM d, yyyy · h:mm a");
  } catch {
    return iso;
  }
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}

export function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ── File size formatting ───────────────────────────────────────

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

// ── Number formatting ──────────────────────────────────────────

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("en-IN").format(n);
}

// ── Status helpers ─────────────────────────────────────────────

export type StatusColor = "violet" | "green" | "amber" | "red" | "blue" | "muted";

export function getMeetingStatusColor(status: string): StatusColor {
  const map: Record<string, StatusColor> = {
    completed:   "green",
    processing:  "amber",
    transcribing:"amber",
    summarizing: "amber",
    pending:     "muted",
    uploading:   "blue",
    failed:      "red",
  };
  return map[status] ?? "muted";
}

export function getMeetingStatusLabel(status: string): string {
  const map: Record<string, string> = {
    completed:   "Processed",
    processing:  "Processing",
    transcribing:"Transcribing",
    summarizing: "Summarizing",
    pending:     "Pending",
    uploading:   "Uploading",
    failed:      "Failed",
  };
  return map[status] ?? status;
}

// ── Source helpers ─────────────────────────────────────────────

export function getMeetingSourceLabel(source: string): string {
  const map: Record<string, string> = {
    upload:      "Upload",
    zoom:        "Zoom",
    google_meet: "Google Meet",
    teams:       "MS Teams",
  };
  return map[source] ?? source;
}

// ── Priority helpers ───────────────────────────────────────────

export function getPriorityColor(priority: string | null): StatusColor {
  if (priority === "high")   return "red";
  if (priority === "medium") return "amber";
  if (priority === "low")    return "green";
  return "muted";
}

// ── Slug generator ─────────────────────────────────────────────

export function toSlug(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

// ── Truncate ───────────────────────────────────────────────────

export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "…";
}

// ── Speaker colour cycling ─────────────────────────────────────

const SPEAKER_COLORS = [
  { bg: "rgba(124,58,237,0.15)", text: "#c4b5fd", border: "rgba(124,58,237,0.25)" },
  { bg: "rgba(59,130,246,0.12)", text: "#93c5fd", border: "rgba(59,130,246,0.20)" },
  { bg: "rgba(16,185,129,0.12)", text: "#6ee7b7", border: "rgba(16,185,129,0.20)" },
  { bg: "rgba(245,158,11,0.12)", text: "#fcd34d", border: "rgba(245,158,11,0.20)" },
  { bg: "rgba(239,68,68,0.12)",  text: "#fca5a5", border: "rgba(239,68,68,0.20)"  },
  { bg: "rgba(236,72,153,0.12)", text: "#f9a8d4", border: "rgba(236,72,153,0.20)" },
];

export function getSpeakerColor(index: number) {
  return SPEAKER_COLORS[index % SPEAKER_COLORS.length];
}

export function getSpeakerIndex(label: string | null): number {
  if (!label) return 0;
  const match = label.match(/\d+/);
  return match ? parseInt(match[0]) : 0;
}
