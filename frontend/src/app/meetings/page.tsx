"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Mic2, Search, Filter, Upload, Trash2, Eye, MoreHorizontal,
  Clock, FileText, Users, RefreshCw, ChevronLeft, ChevronRight,
} from "lucide-react";
import { meetingService } from "@/services";
import {
  Card, Button, Badge, Skeleton, EmptyState,
} from "@/components/ui/primitives";
import {
  cn, formatDate, formatDuration, formatBytes,
  getMeetingStatusColor, getMeetingStatusLabel, getMeetingSourceLabel,
} from "@/lib/utils";
import type { MeetingStatus } from "@/types";

const STATUS_FILTERS: { label: string; value: string }[] = [
  { label: "All",          value: "" },
  { label: "Completed",    value: "completed" },
  { label: "Processing",   value: "processing" },
  { label: "Failed",       value: "failed" },
];

export default function MeetingsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["meetings", { page, status: statusFilter }],
    queryFn: () =>
      meetingService.list({ page, page_size: 15, status: statusFilter || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: meetingService.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] });
      toast.success("Meeting deleted");
    },
    onError: () => toast.error("Delete failed"),
  });

  const filtered = data?.items.filter((m) =>
    search ? m.title.toLowerCase().includes(search.toLowerCase()) : true
  ) ?? [];

  return (
    <div className="p-6 animate-fade-in space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-bold text-xl text-foreground">All Meetings</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {data?.total ?? 0} meetings in workspace
          </p>
        </div>
        <Button variant="primary" onClick={() => router.push("/meetings/upload")}>
          <Upload className="w-4 h-4" /> Upload
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search meetings…"
            className="w-full h-9 pl-8 pr-3 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500/50 transition-all"
          />
        </div>

        {/* Status filter pills */}
        <div className="flex gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => { setStatusFilter(f.value); setPage(1); }}
              className={cn(
                "h-9 px-3.5 text-xs font-medium rounded-lg transition-all border",
                statusFilter === f.value
                  ? "bg-violet-600/20 border-violet-500/40 text-violet-300"
                  : "bg-secondary border-border text-muted-foreground hover:border-violet-500/30 hover:text-foreground"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => qc.invalidateQueries({ queryKey: ["meetings"] })}
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Table */}
      <Card className="p-0 overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_120px_100px_80px_100px_44px] gap-3 px-5 py-3 bg-secondary/50 border-b border-border">
          {["Title", "Date", "Duration", "Words", "Status", ""].map((h) => (
            <p key={h} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              {h}
            </p>
          ))}
        </div>

        {isLoading ? (
          <div className="divide-y divide-border/50">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="grid grid-cols-[1fr_120px_100px_80px_100px_44px] gap-3 px-5 py-3.5">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-14" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Mic2}
            title="No meetings found"
            description={search ? "Try a different search term" : "Upload your first meeting to get started."}
            action={
              !search && (
                <Button variant="primary" size="sm" onClick={() => router.push("/meetings/upload")}>
                  Upload Meeting
                </Button>
              )
            }
          />
        ) : (
          <div className="divide-y divide-border/50">
            {filtered.map((meeting) => (
              <motion.div
                key={meeting.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="grid grid-cols-[1fr_120px_100px_80px_100px_44px] gap-3 items-center px-5 py-3.5 hover:bg-secondary/40 transition-colors group"
              >
                {/* Title */}
                <Link href={`/meetings/${meeting.id}`} className="min-w-0">
                  <div className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate group-hover:text-violet-300 transition-colors">
                        {meeting.title}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {getMeetingSourceLabel(meeting.source)}
                        {meeting.original_filename && ` · ${meeting.original_filename}`}
                      </p>
                    </div>
                  </div>
                </Link>

                {/* Date */}
                <p className="text-xs text-muted-foreground">{formatDate(meeting.created_at)}</p>

                {/* Duration */}
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  {formatDuration(meeting.duration_seconds)}
                </div>

                {/* Words */}
                <p className="text-xs text-muted-foreground">
                  {meeting.word_count ? `${(meeting.word_count / 1000).toFixed(1)}k` : "—"}
                </p>

                {/* Status */}
                <Badge variant={getMeetingStatusColor(meeting.status) as any}>
                  {getMeetingStatusLabel(meeting.status)}
                </Badge>

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Link href={`/meetings/${meeting.id}`}>
                    <Button variant="ghost" size="icon-sm" title="View">
                      <Eye className="w-3.5 h-3.5" />
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Delete"
                    onClick={() => {
                      if (confirm("Delete this meeting?")) {
                        deleteMutation.mutate(meeting.id);
                      }
                    }}
                    className="hover:text-red-400"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </Card>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Page {data.page} of {data.total_pages} · {data.total} total
          </p>
          <div className="flex gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page === data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
