"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Bell, Plus, Command, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";

const PAGE_LABELS: Record<string, string> = {
  "/dashboard":       "Dashboard",
  "/meetings":        "All Meetings",
  "/meetings/upload": "Upload Meeting",
  "/chat":            "AI Chat",
  "/analytics":       "Analytics",
  "/reports":         "Reports",
  "/team":            "Team",
  "/integrations":    "Integrations",
  "/settings":        "Settings",
};

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchValue, setSearchValue] = useState("");

  const title = PAGE_LABELS[pathname] ?? "MeetingMind";

  return (
    <header className="h-14 bg-card/80 backdrop-blur-md border-b border-border flex items-center px-5 gap-3 sticky top-0 z-40">
      {/* Page title */}
      <h1 className="font-display font-bold text-[15px] text-foreground mr-2 shrink-0">
        {title}
      </h1>

      <div className="flex-1" />

      {/* Search bar */}
      <AnimatePresence mode="wait">
        {searchOpen ? (
          <motion.div
            key="search-open"
            initial={{ width: 120, opacity: 0 }}
            animate={{ width: 320, opacity: 1 }}
            exit={{ width: 120, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="relative"
          >
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <input
              autoFocus
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && searchValue.trim()) {
                  router.push(`/meetings?q=${encodeURIComponent(searchValue)}`);
                  setSearchOpen(false);
                  setSearchValue("");
                }
                if (e.key === "Escape") {
                  setSearchOpen(false);
                  setSearchValue("");
                }
              }}
              placeholder="Search meetings, transcripts…"
              className="w-full h-8 pl-8 pr-8 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 transition-all"
            />
            <button
              onClick={() => { setSearchOpen(false); setSearchValue(""); }}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        ) : (
          <motion.button
            key="search-closed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSearchOpen(true)}
            className="h-8 px-3 flex items-center gap-2 bg-secondary border border-border rounded-lg text-sm text-muted-foreground hover:border-violet-500/40 hover:text-foreground transition-all group"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-xs">Search</span>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono text-muted-foreground group-hover:text-foreground transition-colors">
              <Command className="w-2.5 h-2.5" />K
            </kbd>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Notification bell */}
      <button className="relative w-8 h-8 flex items-center justify-center rounded-lg bg-secondary border border-border text-muted-foreground hover:border-violet-500/40 hover:text-foreground transition-all">
        <Bell className="w-4 h-4" />
        {/* Unread dot */}
        <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-violet-500 rounded-full" />
      </button>

      {/* New meeting CTA */}
      <button
        onClick={() => router.push("/meetings/upload")}
        className="h-8 px-3 flex items-center gap-1.5 btn-gradient text-white text-xs font-medium rounded-lg"
      >
        <Plus className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">New Meeting</span>
      </button>
    </header>
  );
}
