"use client";

import { useState, useCallback, useId } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Upload, Film, Music, CheckCircle2, AlertCircle, Loader2,
  Mic2, Video, Globe, Zap, X,
} from "lucide-react";
import { meetingService } from "@/services";
import { useMeetingStore } from "@/stores/meeting-store";
import {
  Card, CardHeader, CardTitle, Button, Input, Progress,
} from "@/components/ui/primitives";
import { cn, formatBytes } from "@/lib/utils";

const PIPELINE_STEPS = [
  { label: "Upload & Extract Audio", sub: "FFmpeg audio extraction" },
  { label: "Speech Transcription",  sub: "Faster Whisper large-v3" },
  { label: "Speaker Diarization",   sub: "Pyannote.audio 3.x" },
  { label: "Face Recognition",      sub: "InsightFace ArcFace" },
  { label: "AI Summarization",      sub: "Groq LLaMA 3.3-70B" },
  { label: "Embed & Store",         sub: "ChromaDB + PostgreSQL" },
];

const STEP_PROGRESS_MAP: Record<string, number> = {
  downloading: 8, extracting_audio: 18, transcribing: 35,
  diarizing: 50, analyzing: 65, summarizing: 78,
  generating_mom: 85, embedding: 90, saving: 95,
};

type UploadPhase = "idle" | "uploading" | "processing" | "done" | "error";

export default function UploadPage() {
  const router = useRouter();
  const titleId = useId();
  const { upsertMeeting, setUploadProgress, setProcessingStatus } = useMeetingStore();

  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [uploadPct, setUploadPct] = useState(0);
  const [processPct, setProcessPct] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [zoomUrl, setZoomUrl] = useState("");
  const [meetUrl, setMeetUrl] = useState("");

  // ── Drop zone ────────────────────────────────────────────────
  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
  }, [title]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "video/*": [".mp4", ".mkv", ".mov", ".avi"],
      "audio/*": [".mp3", ".wav", ".m4a", ".ogg"],
    },
    maxSize: 2 * 1024 * 1024 * 1024,
    multiple: false,
  });

  // ── Poll processing status ────────────────────────────────────
  const pollStatus = useCallback(async (id: string) => {
    let attempts = 0;
    const maxAttempts = 360; // 30 min @ 5s intervals

    const interval = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(interval);
        return;
      }
      try {
        const status = await meetingService.getStatus(id);
        setCurrentStep(status.current_step ?? status.status);
        const pct = STEP_PROGRESS_MAP[status.current_step ?? ""] ?? status.progress_percent ?? 0;
        setProcessPct(pct);
        setProcessingStatus(id, status);

        if (status.status === "completed") {
          clearInterval(interval);
          setProcessPct(100);
          setPhase("done");
          toast.success("Meeting processed! Redirecting…");
          setTimeout(() => router.push(`/meetings/${id}`), 1500);
        } else if (status.status === "failed") {
          clearInterval(interval);
          setPhase("error");
          toast.error(status.error ?? "Processing failed");
        }
      } catch { /* ignore */ }
    }, 5000);
  }, [router, setProcessingStatus]);

  // ── Submit ────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!file || !title.trim()) {
      toast.error("Please select a file and enter a title");
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title.trim());

    setPhase("uploading");
    setUploadPct(0);

    try {
      const meeting = await meetingService.upload(fd, (pct) => {
        setUploadPct(pct);
        setUploadProgress("upload", pct);
      });
      setMeetingId(meeting.id);
      upsertMeeting(meeting);
      setPhase("processing");
      setProcessPct(5);
      toast.info("File uploaded! Processing pipeline started…");
      pollStatus(meeting.id);
    } catch (err: any) {
      setPhase("error");
      toast.error(err?.response?.data?.detail ?? "Upload failed");
    }
  };

  // ── Reset ─────────────────────────────────────────────────────
  const reset = () => {
    setFile(null); setTitle(""); setPhase("idle");
    setUploadPct(0); setProcessPct(0); setCurrentStep(""); setMeetingId(null);
  };

  const activeStep = Math.floor((processPct / 100) * PIPELINE_STEPS.length);

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      <div className="mb-6">
        <h2 className="font-display font-bold text-xl text-foreground">Upload Meeting</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Upload a recording or send a bot to join live.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left: Upload */}
        <div className="space-y-4">
          {/* Drop zone */}
          <Card>
            <AnimatePresence mode="wait">
              {phase === "idle" || phase === "error" ? (
                <motion.div key="dropzone" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  {/* Meeting title */}
                  <div className="mb-4">
                    <Input
                      id={titleId}
                      label="Meeting Title"
                      placeholder="e.g. Q4 Budget Review"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                    />
                  </div>

                  {/* Drop zone */}
                  <div
                    {...getRootProps()}
                    className={cn(
                      "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200",
                      isDragActive
                        ? "border-violet-500 bg-violet-500/8"
                        : "border-border hover:border-violet-500/50 hover:bg-secondary/50"
                    )}
                  >
                    <input {...getInputProps()} />
                    <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-3">
                      <Upload className="w-5 h-5 text-violet-400" />
                    </div>
                    {file ? (
                      <div>
                        <p className="text-sm font-medium text-foreground">{file.name}</p>
                        <p className="text-xs text-muted-foreground mt-1">{formatBytes(file.size)}</p>
                        <button
                          onClick={(e) => { e.stopPropagation(); setFile(null); setTitle(""); }}
                          className="mt-2 text-xs text-red-400 hover:text-red-300 flex items-center gap-1 mx-auto"
                        >
                          <X className="w-3 h-3" /> Remove
                        </button>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm font-medium text-foreground mb-1">
                          {isDragActive ? "Drop it here!" : "Drop file or click to browse"}
                        </p>
                        <p className="text-xs text-muted-foreground">MP4, MKV, MOV, MP3, WAV · up to 2 GB</p>
                      </div>
                    )}
                  </div>

                  <Button
                    variant="primary"
                    className="w-full mt-4"
                    disabled={!file || !title.trim()}
                    onClick={handleUpload}
                  >
                    <Zap className="w-4 h-4" />
                    Start Processing
                  </Button>

                  {phase === "error" && (
                    <p className="text-xs text-red-400 text-center mt-2">
                      Upload failed. <button onClick={reset} className="underline">Try again</button>
                    </p>
                  )}
                </motion.div>
              ) : (
                <motion.div key="progress" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                  {/* File info */}
                  <div className="flex items-center gap-3 mb-5">
                    <div className="w-9 h-9 bg-violet-500/15 rounded-lg flex items-center justify-center">
                      <Film className="w-4 h-4 text-violet-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file?.name}</p>
                      <p className="text-xs text-muted-foreground">{formatBytes(file?.size)}</p>
                    </div>
                    {phase === "done" ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
                    )}
                  </div>

                  {/* Upload progress */}
                  {phase === "uploading" && (
                    <div className="mb-4">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
                        <span>Uploading…</span>
                        <span>{uploadPct}%</span>
                      </div>
                      <Progress value={uploadPct} />
                    </div>
                  )}

                  {/* Processing progress */}
                  {(phase === "processing" || phase === "done") && (
                    <div className="mb-4">
                      <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
                        <span>{phase === "done" ? "Complete!" : currentStep || "Processing…"}</span>
                        <span>{processPct}%</span>
                      </div>
                      <Progress value={processPct} />
                    </div>
                  )}

                  {/* Pipeline steps */}
                  <div className="space-y-2">
                    {PIPELINE_STEPS.map((step, i) => {
                      const isDone = i < activeStep;
                      const isActive = i === activeStep && phase === "processing";
                      return (
                        <div key={i} className="flex items-center gap-3">
                          <div className={cn(
                            "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 transition-colors",
                            isDone  ? "bg-violet-600 text-white" :
                            isActive? "bg-violet-500/30 text-violet-300 ring-1 ring-violet-500/50" :
                                      "bg-secondary text-muted-foreground"
                          )}>
                            {isDone ? "✓" : i + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={cn("text-xs font-medium",
                              isDone   ? "text-foreground" :
                              isActive ? "text-violet-300" :
                                         "text-muted-foreground"
                            )}>
                              {step.label}
                            </p>
                            <p className="text-[10px] text-muted-foreground/60">{step.sub}</p>
                          </div>
                          {isActive && <Loader2 className="w-3 h-3 text-violet-400 animate-spin shrink-0" />}
                        </div>
                      );
                    })}
                  </div>

                  {phase === "done" && (
                    <Button variant="primary" className="w-full mt-5" onClick={() => router.push(`/meetings/${meetingId}`)}>
                      View Meeting →
                    </Button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </div>

        {/* Right: Format guide + Live bots */}
        <div className="space-y-4">
          {/* Supported formats */}
          <Card>
            <CardTitle className="mb-3">Supported Formats</CardTitle>
            <div className="grid grid-cols-3 gap-2">
              {[
                { icon: Film, label: "MP4" }, { icon: Film, label: "MKV" },
                { icon: Film, label: "MOV" }, { icon: Music, label: "MP3" },
                { icon: Music, label: "WAV" }, { icon: Music, label: "M4A" },
              ].map(({ icon: Icon, label }) => (
                <div key={label} className="flex flex-col items-center gap-1.5 p-3 bg-secondary rounded-lg">
                  <Icon className="w-4 h-4 text-muted-foreground" />
                  <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Bot join */}
          <Card>
            <CardHeader>
              <CardTitle>Join Live Meeting</CardTitle>
              <div className="dot-live" />
            </CardHeader>
            <div className="space-y-3">
              <Input
                label="Zoom Meeting URL"
                placeholder="https://zoom.us/j/123456789"
                value={zoomUrl}
                onChange={(e) => setZoomUrl(e.target.value)}
              />
              <Button
                variant="secondary"
                className="w-full"
                disabled={!zoomUrl.trim()}
                onClick={() => { toast.info("🤖 Bot joining Zoom in 30s…"); }}
              >
                <Video className="w-4 h-4" />
                Send Bot to Zoom
              </Button>

              <div className="relative flex items-center gap-2 py-1">
                <div className="flex-1 h-px bg-border" />
                <span className="text-[10px] text-muted-foreground uppercase">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              <Input
                label="Google Meet URL"
                placeholder="https://meet.google.com/abc-defg-hij"
                value={meetUrl}
                onChange={(e) => setMeetUrl(e.target.value)}
              />
              <Button
                variant="secondary"
                className="w-full"
                disabled={!meetUrl.includes("meet.google.com")}
                onClick={() => { toast.info("🤖 Bot joining Meet in 30s…"); }}
              >
                <Globe className="w-4 h-4" />
                Send Bot to Meet
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
