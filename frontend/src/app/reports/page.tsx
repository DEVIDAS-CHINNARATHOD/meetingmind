// ────────────────────────────────────────────────────────────────
// Reports Page
// ────────────────────────────────────────────────────────────────
"use client";
export default function ReportsPage() { return <ReportsContent />; }

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Download, FileText, BarChart2, Mic2 } from "lucide-react";
import { meetingService, reportService } from "@/services";
import { Card, CardHeader, CardTitle, Button, Badge, EmptyState } from "@/components/ui/primitives";
import { formatDate, formatDuration, getMeetingStatusColor } from "@/lib/utils";
import { toast } from "sonner";
import { useState } from "react";

function ReportsContent() {
  const [downloading, setDownloading] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["meetings", { page: 1, page_size: 50, status: "completed" }],
    queryFn: () => meetingService.list({ page: 1, page_size: 50, status: "completed" }),
  });
  const meetings = data?.items ?? [];

  async function dl(id: string, fmt: "pdf" | "docx" | "txt", type = "mom") {
    const key = `${id}-${fmt}`;
    setDownloading(key);
    try { await reportService.download(id, fmt, type); toast.success(`${fmt.toUpperCase()} ready`); }
    catch { toast.error("Download failed"); }
    finally { setDownloading(null); }
  }

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div>
        <h2 className="font-display font-bold text-xl text-foreground">Reports</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Download transcripts, MoM, and analytics</p>
      </div>
      {meetings.length === 0 ? (
        <EmptyState icon={FileText} title="No completed meetings" description="Complete a meeting to generate reports." />
      ) : (
        <div className="space-y-3">
          {meetings.map((m) => (
            <Card key={m.id} className="flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{m.title}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatDate(m.created_at)} · {formatDuration(m.duration_seconds)}
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                {(["pdf", "docx", "txt"] as const).map((fmt) => (
                  <Button key={fmt} variant="secondary" size="sm"
                    loading={downloading === `${m.id}-${fmt}`}
                    onClick={() => dl(m.id, fmt)}>
                    <Download className="w-3 h-3" />{fmt.toUpperCase()}
                  </Button>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
