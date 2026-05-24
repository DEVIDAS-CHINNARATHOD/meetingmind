"use client";

import { motion } from "framer-motion";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/primitives";
import type { ProcessingStatus } from "@/types";

const STEPS = [
  { key: "uploading",    label: "Upload & Extract Audio", sub: "FFmpeg" },
  { key: "transcribing", label: "Transcription",          sub: "Faster Whisper" },
  { key: "diarizing",   label: "Speaker Diarization",     sub: "Pyannote" },
  { key: "analyzing",   label: "Face Recognition",        sub: "InsightFace" },
  { key: "summarizing", label: "AI Summarization",        sub: "Groq LLaMA" },
  { key: "saving",      label: "Embed & Store",           sub: "ChromaDB" },
];

const STEP_INDEX: Record<string, number> = {
  uploading: 0, extracting_audio: 0,
  transcribing: 1,
  diarizing: 2,
  analyzing: 3, face_recognition: 3,
  summarizing: 4, generating_mom: 4,
  embedding: 5, saving: 5,
};

interface Props {
  status: ProcessingStatus;
}

export function ProcessingPipeline({ status }: Props) {
  const activeIdx = STEP_INDEX[status.current_step ?? status.status] ?? 0;
  const isCompleted = status.status === "completed";
  const isFailed = status.status === "failed";
  const progress = status.progress_percent ?? 0;

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span className="capitalize">{status.current_step?.replace(/_/g, " ") ?? status.status}</span>
          <span>{progress}%</span>
        </div>
        <Progress value={progress} />
      </div>

      {/* Steps */}
      <div className="space-y-2">
        {STEPS.map((step, i) => {
          const done    = isCompleted || i < activeIdx;
          const active  = !isCompleted && !isFailed && i === activeIdx;
          const failed  = isFailed && i === activeIdx;
          const pending = !done && !active && !failed;

          return (
            <motion.div
              key={step.key}
              initial={{ opacity: 0.5 }}
              animate={{ opacity: pending ? 0.4 : 1 }}
              className="flex items-center gap-3"
            >
              {/* Icon */}
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold transition-colors",
                done   && "bg-violet-600 text-white",
                active && "bg-violet-500/20 text-violet-300 ring-1 ring-violet-500/50",
                failed && "bg-red-500/20 text-red-400",
                pending&& "bg-secondary text-muted-foreground/50",
              )}>
                {done   ? "✓" :
                 failed ? <AlertCircle className="w-3 h-3" /> :
                 active ? <Loader2 className="w-3 h-3 animate-spin" /> :
                 i + 1}
              </div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-xs font-medium",
                  done   ? "text-foreground" :
                  active ? "text-violet-300" :
                  failed ? "text-red-400" :
                           "text-muted-foreground/50"
                )}>
                  {step.label}
                </p>
                <p className="text-[10px] text-muted-foreground/40">{step.sub}</p>
              </div>

              {active && (
                <div className="flex gap-0.5 items-end h-4 shrink-0">
                  {[0,1,2,3].map(j => (
                    <div key={j} className="w-0.5 bg-violet-500 rounded-full animate-wave"
                      style={{ height: "60%", animationDelay: `${j * 0.15}s` }} />
                  ))}
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Error message */}
      {isFailed && status.error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 font-mono">
          {status.error}
        </p>
      )}
    </div>
  );
}
