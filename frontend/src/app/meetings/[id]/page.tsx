"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowLeft, Download, MessageSquare, Mic2, Clock, FileText,
  CheckSquare, Users, Brain, Pencil, Check, X, AlertTriangle,
  RotateCcw, ChevronRight,
} from "lucide-react";
import {
  meetingService, aiService, reportService, speakerService, actionItemService,
} from "@/services";
import {
  Card, CardHeader, CardTitle, Badge, Button, Skeleton,
  Progress, EmptyState,
} from "@/components/ui/primitives";
import {
  cn, formatDate, formatDuration, formatTimestamp, timeAgo,
  getMeetingStatusColor, getMeetingStatusLabel, getSpeakerColor, getSpeakerIndex,
} from "@/lib/utils";
import type { ActionItem, TranscriptSegment } from "@/types";

type Tab = "transcript" | "summary" | "actions" | "speakers";

// ── Action item row ───────────────────────────────────────────

function ActionRow({ item }: { item: ActionItem }) {
  const qc = useQueryClient();
  const toggle = useMutation({
    mutationFn: () => actionItemService.update(item.id, { is_completed: !item.is_completed }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["meeting"] }),
  });

  return (
    <div className={cn(
      "flex items-start gap-3 py-2.5 border-b border-border/50 last:border-0",
      item.is_completed && "opacity-60"
    )}>
      <button
        onClick={() => toggle.mutate()}
        className={cn(
          "w-5 h-5 rounded-md border flex items-center justify-center shrink-0 mt-0.5 transition-all",
          item.is_completed
            ? "bg-emerald-500 border-emerald-500"
            : "border-border hover:border-violet-500"
        )}
      >
        {item.is_completed && <Check className="w-3 h-3 text-white" />}
      </button>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm text-foreground", item.is_completed && "line-through")}>
          {item.task}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          {item.assigned_to && (
            <span className="text-[11px] text-violet-400">→ {item.assigned_to}</span>
          )}
          {item.deadline && (
            <span className="text-[11px] text-muted-foreground">· {item.deadline}</span>
          )}
        </div>
      </div>
      {item.priority && (
        <Badge variant={item.priority === "high" ? "red" : item.priority === "medium" ? "amber" : "green"}>
          {item.priority}
        </Badge>
      )}
    </div>
  );
}

// ── Transcript segment ────────────────────────────────────────

function SegmentRow({ seg, index }: { seg: TranscriptSegment; index: number }) {
  const color = getSpeakerColor(getSpeakerIndex(seg.speaker_label));
  const displayName = seg.speaker_name || seg.speaker_label;
  return (
    <div className="flex gap-3 py-2.5 border-b border-border/40 last:border-0 group">
      <span className="text-[11px] text-muted-foreground w-10 shrink-0 pt-0.5 font-mono">
        {formatTimestamp(seg.start_time)}
      </span>
      {displayName && (
        <span
          className="text-[11px] font-semibold px-2 py-0.5 rounded-full h-fit shrink-0 whitespace-nowrap"
          style={{ background: color.bg, color: color.text, border: `1px solid ${color.border}` }}
        >
          {displayName}
        </span>
      )}
      <p className="text-sm text-foreground leading-relaxed flex-1">{seg.text}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function MeetingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("summary");
  const [searchTerm, setSearchTerm] = useState("");
  const [downloadingFmt, setDownloadingFmt] = useState<string | null>(null);

  const { data: meeting, isLoading } = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => meetingService.get(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && !["completed", "failed"].includes(status)) return 5000;
      return false;
    },
  });

  const regenSummary = useMutation({
    mutationFn: () => aiService.summarize(id, true),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["meeting", id] }); toast.success("Summary regenerated"); },
    onError: () => toast.error("Regeneration failed"),
  });

  const handleDownload = async (fmt: "pdf" | "docx" | "txt") => {
    setDownloadingFmt(fmt);
    try {
      await reportService.download(id, fmt);
      toast.success(`${fmt.toUpperCase()} downloaded`);
    } catch {
      toast.error("Download failed");
    } finally {
      setDownloadingFmt(null);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-5">
        <Skeleton className="h-6 w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!meeting) {
    return (
      <div className="p-6">
        <EmptyState icon={Mic2} title="Meeting not found" description="This meeting may have been deleted." />
      </div>
    );
  }

  const isProcessing = !["completed","failed"].includes(meeting.status);
  const filteredSegments = meeting.transcript_segments?.filter(s =>
    !searchTerm || s.text.toLowerCase().includes(searchTerm.toLowerCase())
  ) ?? [];

  const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "summary",    label: "Summary",    icon: Brain },
    { id: "transcript", label: "Transcript", icon: FileText },
    { id: "actions",    label: `Actions (${meeting.action_items?.length ?? 0})`, icon: CheckSquare },
    { id: "speakers",   label: "Speakers",   icon: Users },
  ];

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h2 className="font-display font-bold text-xl text-foreground leading-tight">
              {meeting.title}
            </h2>
            <div className="flex items-center flex-wrap gap-2 mt-1.5">
              <Badge variant={getMeetingStatusColor(meeting.status) as any}>
                {getMeetingStatusLabel(meeting.status)}
              </Badge>
              <span className="text-xs text-muted-foreground">{formatDate(meeting.created_at)}</span>
              {meeting.duration_seconds && (
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Clock className="w-3 h-3" />{formatDuration(meeting.duration_seconds)}
                </span>
              )}
              {meeting.language && (
                <span className="text-xs text-muted-foreground uppercase">{meeting.language}</span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="secondary" size="sm" onClick={() => router.push("/chat")}>
            <MessageSquare className="w-3.5 h-3.5" /> Ask AI
          </Button>
          {meeting.status === "completed" && (
            <div className="flex gap-1.5">
              {(["pdf", "docx", "txt"] as const).map((fmt) => (
                <Button
                  key={fmt}
                  variant="secondary"
                  size="sm"
                  loading={downloadingFmt === fmt}
                  onClick={() => handleDownload(fmt)}
                >
                  <Download className="w-3.5 h-3.5" />
                  {fmt.toUpperCase()}
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Processing state */}
      {isProcessing && (
        <Card className="border-amber-500/25 bg-amber-500/5">
          <div className="flex items-center gap-3 mb-3">
            <div className="dot-amber animate-pulse" />
            <p className="text-sm font-medium text-amber-400">
              {getMeetingStatusLabel(meeting.status)}…
            </p>
          </div>
          <Progress value={50} />
          <p className="text-xs text-muted-foreground mt-2">
            This may take a few minutes depending on recording length.
          </p>
        </Card>
      )}

      {/* Failed */}
      {meeting.status === "failed" && (
        <Card className="border-red-500/25 bg-red-500/5">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="w-4 h-4" />
            <p className="text-sm font-medium">Processing failed</p>
          </div>
          {meeting.processing_error && (
            <p className="text-xs text-muted-foreground mt-1.5 font-mono">{meeting.processing_error}</p>
          )}
        </Card>
      )}

      {/* Topics / decisions */}
      {meeting.topics && meeting.topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {meeting.topics.map((t) => <Badge key={t} variant="violet">{t}</Badge>)}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Duration",     value: formatDuration(meeting.duration_seconds) },
          { label: "Words",        value: meeting.word_count?.toLocaleString() ?? "—" },
          { label: "Speakers",     value: meeting.participants?.length ?? "—" },
          { label: "Action Items", value: meeting.action_items?.length ?? "—" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-secondary border border-border rounded-lg px-4 py-3">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{label}</p>
            <p className="font-display font-bold text-lg text-foreground">{value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border pb-0.5">
        {TABS.map(({ id: tid, label, icon: Icon }) => (
          <button
            key={tid}
            onClick={() => setTab(tid)}
            className={cn(
              "flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-t-lg transition-all -mb-px border-b-2",
              tab === tid
                ? "text-violet-300 border-violet-500 bg-violet-500/8"
                : "text-muted-foreground border-transparent hover:text-foreground"
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <motion.div key={tab} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>

        {/* Summary tab */}
        {tab === "summary" && (
          <div className="space-y-4">
            {meeting.summary ? (
              <Card>
                <CardHeader>
                  <CardTitle>AI Summary</CardTitle>
                  <Button variant="ghost" size="icon-sm" onClick={() => regenSummary.mutate()} loading={regenSummary.isPending} title="Regenerate">
                    <RotateCcw className="w-3.5 h-3.5" />
                  </Button>
                </CardHeader>
                <p className="text-sm text-muted-foreground leading-relaxed">{meeting.summary}</p>

                {meeting.key_decisions && meeting.key_decisions.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-border">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2.5">
                      Key Decisions
                    </p>
                    <div className="space-y-1.5">
                      {meeting.key_decisions.map((d, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm text-foreground">
                          <ChevronRight className="w-3.5 h-3.5 text-violet-400 mt-0.5 shrink-0" />
                          {d}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            ) : (
              <EmptyState icon={Brain} title="No summary yet"
                description={isProcessing ? "Summary will appear after processing completes." : "Trigger regeneration to generate a summary."}
                action={!isProcessing && (
                  <Button variant="primary" size="sm" onClick={() => regenSummary.mutate()} loading={regenSummary.isPending}>
                    Generate Summary
                  </Button>
                )}
              />
            )}
          </div>
        )}

        {/* Transcript tab */}
        {tab === "transcript" && (
          <Card>
            <div className="flex items-center gap-3 mb-4">
              <CardTitle>Full Transcript</CardTitle>
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search transcript…"
                className="ml-auto h-7 px-2.5 bg-secondary border border-border rounded-lg text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500/50 w-48 transition-all"
              />
            </div>
            {filteredSegments.length === 0 ? (
              <EmptyState icon={FileText} title="No transcript" description={isProcessing ? "Transcript will appear after processing." : "No transcript available."} />
            ) : (
              <div className="max-h-[520px] overflow-y-auto -mx-5 px-5">
                {filteredSegments.map((seg, i) => (
                  <SegmentRow key={seg.id} seg={seg} index={i} />
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Actions tab */}
        {tab === "actions" && (
          <Card>
            <CardTitle className="mb-4">Action Items</CardTitle>
            {meeting.action_items?.length === 0 ? (
              <EmptyState icon={CheckSquare} title="No action items" description="No action items were extracted from this meeting." />
            ) : (
              <div>
                {meeting.action_items?.map((item) => (
                  <ActionRow key={item.id} item={item} />
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Speakers tab */}
        {tab === "speakers" && (
          <Card>
            <CardTitle className="mb-4">Speaker Analysis</CardTitle>
            {meeting.participants?.length === 0 ? (
              <EmptyState icon={Users} title="No speakers identified"
                description="Speaker diarization requires HUGGINGFACE_TOKEN to be configured." />
            ) : (
              <div className="space-y-3">
                {meeting.participants?.map((p, i) => {
                  const color = getSpeakerColor(getSpeakerIndex(p.speaker_label));
                  const total = meeting.participants!.reduce((sum, pp) => sum + (pp.talk_time_seconds ?? 0), 0);
                  const pct = total > 0 ? ((p.talk_time_seconds ?? 0) / total) * 100 : 0;
                  return (
                    <div key={p.id}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                            style={{ background: color.bg, color: color.text, border: `1px solid ${color.border}` }}>
                            {p.name || p.speaker_label}
                          </span>
                          {p.word_count && (
                            <span className="text-[11px] text-muted-foreground">{p.word_count.toLocaleString()} words</span>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatDuration(p.talk_time_seconds)} · {pct.toFixed(0)}%
                        </span>
                      </div>
                      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                        <motion.div className="h-full rounded-full"
                          style={{ background: `linear-gradient(90deg, ${color.text}, ${color.bg})` }}
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.8, delay: i * 0.1 }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        )}
      </motion.div>
    </div>
  );
}
