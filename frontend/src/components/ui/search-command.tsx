"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Search, X, Mic2, Clock, ArrowRight } from "lucide-react";
import { useUIStore } from "@/stores/meeting-store";
import { useSearch } from "@/hooks/use-search";
import { cn, formatDate, truncate } from "@/lib/utils";

export function SearchCommand() {
  const router = useRouter();
  const { commandOpen, setCommandOpen } = useUIStore();
  const { query, setQuery, results, isLoading, hasQuery, clear } = useSearch();
  const inputRef = useRef<HTMLInputElement>(null);

  // Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
      if (e.key === "Escape") setCommandOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setCommandOpen]);

  // Auto-focus input when opened
  useEffect(() => {
    if (commandOpen) setTimeout(() => inputRef.current?.focus(), 50);
    else clear();
  }, [commandOpen, clear]);

  const navigateTo = (meetingId: string) => {
    router.push(`/meetings/${meetingId}`);
    setCommandOpen(false);
    clear();
  };

  return (
    <AnimatePresence>
      {commandOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCommandOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -8 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="fixed top-[20vh] left-1/2 -translate-x-1/2 w-full max-w-xl z-50"
          >
            <div className="glass-strong rounded-2xl border border-border shadow-2xl overflow-hidden">
              {/* Search input */}
              <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
                <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search meetings, transcripts, topics…"
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                />
                {query && (
                  <button onClick={clear} className="text-muted-foreground hover:text-foreground transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                )}
                <kbd className="text-[10px] font-mono text-muted-foreground bg-secondary border border-border px-1.5 py-0.5 rounded">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto">
                {isLoading ? (
                  <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                    Searching…
                  </div>
                ) : hasQuery && results.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-muted-foreground">
                    No results for "{query}"
                  </div>
                ) : results.length > 0 ? (
                  <div className="py-2">
                    <p className="px-4 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
                      {results.length} result{results.length !== 1 ? "s" : ""}
                    </p>
                    {results.map((r, i) => (
                      <button
                        key={r.meeting_id + i}
                        onClick={() => navigateTo(r.meeting_id)}
                        className="w-full flex items-start gap-3 px-4 py-3 hover:bg-secondary/60 transition-colors text-left group"
                      >
                        <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/20 flex items-center justify-center shrink-0 mt-0.5">
                          <Mic2 className="w-3.5 h-3.5 text-violet-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground group-hover:text-violet-300 transition-colors truncate">
                            {r.title}
                          </p>
                          {r.snippet && (
                            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
                              {r.snippet}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1">
                            {r.created_at && (
                              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <Clock className="w-2.5 h-2.5" />
                                {formatDate(r.created_at)}
                              </span>
                            )}
                            <span className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded-full",
                              r.match_type === "hybrid"   && "bg-violet-500/15 text-violet-400",
                              r.match_type === "semantic" && "bg-blue-500/15 text-blue-400",
                              r.match_type === "text"     && "bg-emerald-500/15 text-emerald-400",
                            )}>
                              {r.match_type}
                            </span>
                          </div>
                        </div>
                        <ArrowRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-violet-400 transition-colors shrink-0 mt-1" />
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="px-4 py-5 text-center text-xs text-muted-foreground">
                    Type to search across all meetings and transcripts
                  </div>
                )}
              </div>

              {/* Footer hints */}
              <div className="px-4 py-2.5 border-t border-border flex items-center gap-4 text-[10px] text-muted-foreground">
                <span>↵ Open</span>
                <span>↑↓ Navigate</span>
                <span>ESC Close</span>
                <span className="ml-auto">Hybrid semantic + text search</span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
