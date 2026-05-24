"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Clock, Users, CheckSquare, MessageSquare, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import {
  cn, formatDate, formatDuration,
  getMeetingStatusColor, getMeetingStatusLabel,
} from "@/lib/utils";
import type { Meeting } from "@/types";

interface MeetingCardProps {
  meeting: Meeting;
  index?: number;
  compact?: boolean;
}

export function MeetingCard({ meeting, index = 0, compact = false }: MeetingCardProps) {
  const statusColor = getMeetingStatusColor(meeting.status);
  const isProcessing = !["completed", "failed"].includes(meeting.status);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
    >
      <Link
        href={`/meetings/${meeting.id}`}
        className={cn(
          "group block bg-card border border-border rounded-xl transition-all duration-200",
          "hover:border-violet-500/40 hover:shadow-lg hover:shadow-violet-500/8 hover:-translate-y-0.5",
          compact ? "p-4" : "p-5"
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <div className={cn(
              "w-2 h-2 rounded-full shrink-0 mt-0.5",
              statusColor === "green"  && "bg-emerald-500",
              statusColor === "amber"  && "bg-amber-500 animate-pulse",
              statusColor === "red"    && "bg-red-500",
              statusColor === "violet" && "bg-violet-500",
              statusColor === "blue"   && "bg-blue-500 animate-pulse",
              statusColor === "muted"  && "bg-muted-foreground/40",
            )} />
            <h3 className={cn(
              "font-medium text-foreground truncate group-hover:text-violet-300 transition-colors",
              compact ? "text-sm" : "text-[15px]"
            )}>
              {meeting.title}
            </h3>
          </div>
          <Badge variant={statusColor as any} className="shrink-0">
            {getMeetingStatusLabel(meeting.status)}
          </Badge>
        </div>

        {/* Meta */}
        <div className={cn(
          "flex items-center flex-wrap gap-x-3 gap-y-1 text-muted-foreground",
          compact ? "text-[11px]" : "text-xs"
        )}>
          <span>{formatDate(meeting.created_at)}</span>
          {meeting.duration_seconds && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(meeting.duration_seconds)}
            </span>
          )}
          {meeting.word_count && (
            <span>{(meeting.word_count / 1000).toFixed(1)}k words</span>
          )}
        </div>

        {/* Topics */}
        {!compact && meeting.topics && meeting.topics.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {meeting.topics.slice(0, 3).map((t) => (
              <span key={t} className="text-[10px] px-2 py-0.5 bg-violet-500/10 border border-violet-500/20 text-violet-400 rounded-full">
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Summary snippet */}
        {!compact && meeting.summary && (
          <p className="text-xs text-muted-foreground mt-3 line-clamp-2 leading-relaxed">
            {meeting.summary}
          </p>
        )}

        {/* Footer */}
        {!compact && (
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/60">
            <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
              {meeting.participants && meeting.participants.length > 0 && (
                <span className="flex items-center gap-1">
                  <Users className="w-3 h-3" />
                  {meeting.participants.length}
                </span>
              )}
              {meeting.action_items && meeting.action_items.length > 0 && (
                <span className="flex items-center gap-1">
                  <CheckSquare className="w-3 h-3" />
                  {meeting.action_items.length} tasks
                </span>
              )}
            </div>
            <span className="flex items-center gap-1 text-[11px] text-violet-400 opacity-0 group-hover:opacity-100 transition-opacity">
              View <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        )}

        {/* Processing bar */}
        {isProcessing && (
          <div className="mt-3 h-0.5 bg-secondary rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-violet-600 to-violet-400 rounded-full animate-shimmer" style={{ width: "60%", backgroundSize: "400px 100%" }} />
          </div>
        )}
      </Link>
    </motion.div>
  );
}
