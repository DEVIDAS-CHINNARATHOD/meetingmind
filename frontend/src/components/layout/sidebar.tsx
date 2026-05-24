"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";
import { motion } from "framer-motion";
import {
  LayoutDashboard, Mic2, Upload, MessageSquare, BarChart3,
  FileText, Users, Puzzle, Settings, ChevronRight, Sparkles,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useMeetingStore } from "@/stores/meeting-store";

const navSections = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard",      icon: LayoutDashboard, label: "Dashboard"  },
      { href: "/meetings",       icon: Mic2,            label: "Meetings", badge: "12" },
      { href: "/meetings/upload",icon: Upload,          label: "Upload"    },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/chat",      icon: MessageSquare, label: "AI Chat"   },
      { href: "/analytics", icon: BarChart3,     label: "Analytics" },
      { href: "/reports",   icon: FileText,      label: "Reports"   },
    ],
  },
  {
    label: "Workspace",
    items: [
      { href: "/team",         icon: Users,   label: "Team"         },
      { href: "/integrations", icon: Puzzle,  label: "Integrations" },
      { href: "/settings",     icon: Settings,label: "Settings"     },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const processingCount = useMeetingStore((s) => s.processingCount);

  return (
    <aside className="w-56 shrink-0 bg-card border-r border-border flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-4 pt-5 pb-4 border-b border-border">
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center shrink-0 shadow-lg group-hover:shadow-violet-500/30 transition-shadow">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <p className="font-display font-bold text-sm text-gradient leading-none">
              MeetingMind
            </p>
            <p className="text-[10px] text-muted-foreground mt-0.5 tracking-widest uppercase">
              AI Platform
            </p>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-5">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-1.5 text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-widest">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard"
                    : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn("nav-item", isActive && "active")}
                  >
                    <item.icon className="w-4 h-4 shrink-0" />
                    <span className="flex-1 text-sm">{item.label}</span>
                    {item.badge && (
                      <span className="text-[10px] font-semibold bg-violet-600 text-white px-1.5 py-0.5 rounded-full leading-none">
                        {item.badge}
                      </span>
                    )}
                    {item.href === "/meetings/upload" && processingCount > 0 && (
                      <span className="text-[10px] font-semibold bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full leading-none animate-pulse">
                        {processingCount}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Processing indicator */}
      {processingCount > 0 && (
        <div className="px-3 py-2 mx-2 mb-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-amber-400 animate-spin-slow" />
            <p className="text-xs text-amber-400 font-medium">
              {processingCount} processing…
            </p>
          </div>
        </div>
      )}

      {/* User */}
      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-secondary transition-colors">
          <UserButton
            appearance={{
              elements: {
                avatarBox: "w-7 h-7",
                userButtonPopoverCard: "bg-card border border-border",
              },
            }}
          />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-foreground truncate">My Account</p>
            <p className="text-[10px] text-violet-400">Pro Plan</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
