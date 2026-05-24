"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Video, Globe, Slack, Calendar, StopCircle, ExternalLink } from "lucide-react";
import { integrationService } from "@/services";
import { Card, CardHeader, CardTitle, Button, Input, Badge } from "@/components/ui/primitives";
import { timeAgo } from "@/lib/utils";

const STATUS_COLOR: Record<string, any> = {
  completed: "green", processing: "amber", pending: "blue",
  failed: "red", queued: "violet",
};

export default function IntegrationsPage() {
  const [zoomId, setZoomId] = useState("");
  const [zoomPass, setZoomPass] = useState("");
  const [meetUrl, setMeetUrl] = useState("");

  const { data: sessions = [], refetch } = useQuery({
    queryKey: ["integrations", "status"],
    queryFn: integrationService.status,
    refetchInterval: 10000,
  });

  const zoomMutation = useMutation({
    mutationFn: () => integrationService.zoomJoin(zoomId, zoomPass),
    onSuccess: () => { toast.success("Zoom bot dispatched!"); refetch(); setZoomId(""); setZoomPass(""); },
    onError: () => toast.error("Failed to dispatch Zoom bot"),
  });

  const meetMutation = useMutation({
    mutationFn: () => integrationService.meetJoin(meetUrl),
    onSuccess: () => { toast.success("Meet bot dispatched!"); refetch(); setMeetUrl(""); },
    onError: () => toast.error("Failed to dispatch Meet bot"),
  });

  const stopMutation = useMutation({
    mutationFn: integrationService.stop,
    onSuccess: () => { toast.success("Bot stopped"); refetch(); },
  });

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-bold text-xl text-foreground">Integrations</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Connect your meeting platforms</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Zoom bot */}
        <Card className="border-blue-500/20">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Video className="w-4 h-4 text-blue-400" />
              <CardTitle>Zoom Bot</CardTitle>
            </div>
          </CardHeader>
          <p className="text-xs text-muted-foreground mb-4">
            Enter a Zoom meeting ID to dispatch a bot that auto-joins, transcribes, and generates MoM.
          </p>
          <div className="space-y-3">
            <Input label="Meeting Number" placeholder="123 456 7890" value={zoomId} onChange={(e) => setZoomId(e.target.value)} />
            <Input label="Passcode (optional)" placeholder="passcode" value={zoomPass} onChange={(e) => setZoomPass(e.target.value)} />
            <Button variant="primary" className="w-full" loading={zoomMutation.isPending}
              disabled={!zoomId.trim()} onClick={() => zoomMutation.mutate()}>
              <Video className="w-4 h-4" /> Send Bot to Zoom
            </Button>
          </div>
        </Card>

        {/* Google Meet bot */}
        <Card className="border-emerald-500/20">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-emerald-400" />
              <CardTitle>Google Meet Bot</CardTitle>
            </div>
          </CardHeader>
          <p className="text-xs text-muted-foreground mb-4">
            Paste a Google Meet link. The Playwright bot joins, mutes itself, and captures audio in real time.
          </p>
          <div className="space-y-3">
            <Input label="Meet URL" placeholder="https://meet.google.com/abc-defg-hij"
              value={meetUrl} onChange={(e) => setMeetUrl(e.target.value)} />
            <Button variant="primary" className="w-full" loading={meetMutation.isPending}
              disabled={!meetUrl.includes("meet.google.com")} onClick={() => meetMutation.mutate()}>
              <Globe className="w-4 h-4" /> Send Bot to Meet
            </Button>
          </div>
        </Card>

        {/* Coming soon */}
        {[
          { icon: "💬", name: "Slack", desc: "Post MoM and action items to channels after meetings end." },
          { icon: "📅", name: "Google Calendar", desc: "Auto-detect scheduled meetings and pre-configure the bot." },
        ].map((item) => (
          <Card key={item.name} className="opacity-60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="text-lg">{item.icon}</span>
                <CardTitle>{item.name}</CardTitle>
              </div>
              <Badge variant="muted">Soon</Badge>
            </CardHeader>
            <p className="text-xs text-muted-foreground">{item.desc}</p>
          </Card>
        ))}
      </div>

      {/* Active sessions */}
      {sessions.length > 0 && (
        <Card>
          <CardTitle className="mb-4">Bot Sessions</CardTitle>
          <div className="divide-y divide-border/50">
            {sessions.map((s) => (
              <div key={s.meeting_id} className="flex items-center gap-3 py-3">
                {s.platform === "zoom" ? <Video className="w-4 h-4 text-blue-400 shrink-0" /> : <Globe className="w-4 h-4 text-emerald-400 shrink-0" />}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{s.title}</p>
                  <p className="text-xs text-muted-foreground">{s.platform} · {timeAgo(s.created_at)}</p>
                </div>
                <Badge variant={(STATUS_COLOR[s.status] ?? "muted") as any}>{s.status}</Badge>
                {["processing","queued","pending"].includes(s.status) && (
                  <Button variant="danger" size="sm" onClick={() => stopMutation.mutate(s.meeting_id)}>
                    <StopCircle className="w-3.5 h-3.5" /> Stop
                  </Button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
