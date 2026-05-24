"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, RefreshCw, X, Mic2, ChevronRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { aiService, meetingService } from "@/services";
import { useChatStore } from "@/stores/meeting-store";
import { Button, Badge, Waveform, Skeleton } from "@/components/ui/primitives";
import { cn, timeAgo, truncate } from "@/lib/utils";
import { nanoid } from "@/lib/nanoid";
import type { ChatMessage } from "@/types";

const SAMPLE_QUESTIONS = [
  "What decisions were made in the last meeting?",
  "List all action items assigned to me",
  "Who spoke the most in this week's standups?",
  "Summarize the budget discussion",
  "What risks were identified?",
];

// ── Message bubble ────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center shrink-0 mt-0.5 mr-2">
          <Sparkles className="w-3.5 h-3.5 text-white" />
        </div>
      )}
      <div className="max-w-[78%] space-y-1">
        {!isUser && (
          <p className="text-[10px] font-semibold text-violet-400 flex items-center gap-1">
            <span>MeetingMind AI</span>
            {msg.model && <span className="text-muted-foreground font-normal">· {msg.model}</span>}
          </p>
        )}
        <div
          className={cn(
            "px-4 py-3 rounded-2xl text-sm leading-relaxed",
            isUser
              ? "bg-violet-600/20 border border-violet-500/30 rounded-tr-sm text-foreground"
              : "bg-card border border-border rounded-tl-sm text-foreground"
          )}
        >
          {msg.isStreaming ? (
            <span>
              {msg.content}
              <span className="inline-block w-1 h-4 bg-violet-400 ml-0.5 animate-pulse rounded-sm" />
            </span>
          ) : (
            <span className="whitespace-pre-wrap">{msg.content}</span>
          )}
        </div>

        {/* Sources */}
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {msg.sources.map((src, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-2 py-1 bg-secondary border border-border rounded-lg cursor-pointer hover:border-violet-500/30 transition-colors group"
                title={src.excerpt}
              >
                <Mic2 className="w-2.5 h-2.5 text-muted-foreground group-hover:text-violet-400" />
                <span className="text-[10px] text-muted-foreground group-hover:text-foreground transition-colors">
                  {truncate(src.meeting_title, 28)}
                </span>
                {src.relevance && (
                  <span className="text-[10px] text-violet-400 font-medium">
                    {Math.round(src.relevance * 100)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        <p className="text-[10px] text-muted-foreground/60 px-1">{timeAgo(msg.timestamp)}</p>
      </div>
    </motion.div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function ChatPage() {
  const { messages, addMessage, updateLastAssistant, clearMessages, isStreaming, setStreaming, contextMeetingIds, setContextMeetingIds } = useChatStore();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { data: meetingsData } = useQuery({
    queryKey: ["meetings", { page: 1, page_size: 20 }],
    queryFn: () => meetingService.list({ page: 1, page_size: 20 }),
  });
  const completedMeetings = meetingsData?.items.filter(m => m.status === "completed") ?? [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async (question?: string) => {
    const text = (question ?? input).trim();
    if (!text || isStreaming) return;

    setInput("");
    const userMsg: ChatMessage = {
      id: nanoid(), role: "user", content: text,
      timestamp: new Date().toISOString(),
    };
    addMessage(userMsg);

    const aiMsg: ChatMessage = {
      id: nanoid(), role: "assistant", content: "",
      isStreaming: true, timestamp: new Date().toISOString(),
    };
    addMessage(aiMsg);
    setStreaming(true);

    try {
      await aiService.streamChat(
        text,
        contextMeetingIds.length > 0 ? contextMeetingIds : undefined,
        (token) => updateLastAssistant({ content: (messages[messages.length - 1]?.content ?? "") + token }),
        (sources) => updateLastAssistant({ sources, isStreaming: false }),
        (err) => updateLastAssistant({ content: `Error: ${err}`, isStreaming: false }),
      );
    } catch {
      updateLastAssistant({ content: "Something went wrong. Please try again.", isStreaming: false });
    } finally {
      setStreaming(false);
    }
  }, [input, isStreaming, messages, contextMeetingIds, addMessage, updateLastAssistant, setStreaming]);

  return (
    <div className="h-[calc(100vh-56px)] flex flex-col animate-fade-in">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border flex items-center gap-3 shrink-0">
        <div>
          <h2 className="font-display font-bold text-sm text-foreground">AI Meeting Assistant</h2>
          <p className="text-[11px] text-muted-foreground">RAG · Groq LLaMA 3.3-70B · ChromaDB</p>
        </div>
        <div className="flex-1 flex flex-wrap gap-1.5 mx-3">
          {contextMeetingIds.length > 0 ? (
            contextMeetingIds.map((id) => {
              const m = completedMeetings.find(m => m.id === id);
              return m ? (
                <span key={id} className="flex items-center gap-1 text-[10px] bg-violet-500/15 border border-violet-500/25 text-violet-300 px-2 py-0.5 rounded-full">
                  {truncate(m.title, 20)}
                  <button onClick={() => setContextMeetingIds(contextMeetingIds.filter(i => i !== id))}>
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              ) : null;
            })
          ) : (
            <span className="text-[10px] text-muted-foreground">All meetings in context</span>
          )}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <select
            className="h-7 px-2 bg-secondary border border-border rounded-lg text-[11px] text-muted-foreground focus:outline-none focus:border-violet-500/50"
            onChange={(e) => { if (e.target.value) setContextMeetingIds([...contextMeetingIds, e.target.value]); }}
            value=""
          >
            <option value="">+ Add meeting context</option>
            {completedMeetings.filter(m => !contextMeetingIds.includes(m.id)).map(m => (
              <option key={m.id} value={m.id}>{truncate(m.title, 35)}</option>
            ))}
          </select>
          <Button variant="ghost" size="icon-sm" onClick={clearMessages} title="Clear chat">
            <RefreshCw className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {/* Sample questions (only when just welcome message) */}
        {messages.length === 1 && (
          <div className="flex flex-wrap gap-2 justify-center py-4">
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-secondary border border-border rounded-full text-muted-foreground hover:border-violet-500/40 hover:text-violet-300 transition-all"
              >
                <ChevronRight className="w-3 h-3" />
                {q}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div className="px-5 py-1.5 flex items-center gap-2 border-t border-border/50">
          <Waveform bars={8} className="h-4" />
          <span className="text-[11px] text-muted-foreground">Generating response…</span>
        </div>
      )}

      {/* Input */}
      <div className="px-5 py-4 border-t border-border shrink-0">
        <div className="flex gap-2.5 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about decisions, action items, speakers…"
            rows={1}
            style={{ resize: "none" }}
            className={cn(
              "flex-1 px-4 py-2.5 bg-secondary border border-border rounded-xl text-sm text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 transition-all",
              "min-h-[42px] max-h-[120px] overflow-y-auto"
            )}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              t.style.height = "auto";
              t.style.height = `${Math.min(t.scrollHeight, 120)}px`;
            }}
          />
          <Button
            variant="primary"
            size="icon"
            onClick={() => handleSend()}
            disabled={!input.trim() || isStreaming}
            className="shrink-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 text-center">
          Shift+Enter for new line · Enter to send
        </p>
      </div>
    </div>
  );
}
