"use client";

import { motion } from "framer-motion";
import { Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

type Color = "violet" | "teal" | "amber" | "blue" | "red";

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: string | number;
  change?: string;
  changePositive?: boolean;
  color?: Color;
  loading?: boolean;
  index?: number;
}

const COLOR_MAP: Record<Color, { grad: string; icon: string; dot: string }> = {
  violet: { grad: "from-violet-500/15",  icon: "text-violet-400",  dot: "bg-violet-500" },
  teal:   { grad: "from-emerald-500/12", icon: "text-emerald-400", dot: "bg-emerald-500" },
  amber:  { grad: "from-amber-500/12",   icon: "text-amber-400",   dot: "bg-amber-500" },
  blue:   { grad: "from-blue-500/12",    icon: "text-blue-400",    dot: "bg-blue-500" },
  red:    { grad: "from-red-500/12",     icon: "text-red-400",     dot: "bg-red-500" },
};

export function StatCard({
  icon: Icon,
  label,
  value,
  change,
  changePositive = true,
  color = "violet",
  loading,
  index = 0,
}: StatCardProps) {
  const c = COLOR_MAP[color];

  if (loading) {
    return (
      <div className="surface-card p-5 space-y-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-8 w-16" />
        <Skeleton className="h-3 w-28" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.07 }}
      className={cn(
        "relative overflow-hidden rounded-xl border border-border p-5",
        `bg-gradient-to-br ${c.grad} to-transparent`,
      )}
    >
      {/* Glow orb */}
      <div className={cn(
        "absolute -top-4 -right-4 w-16 h-16 rounded-full opacity-15 blur-xl",
        c.dot,
      )} />

      <div className="flex items-start justify-between mb-3">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          {label}
        </p>
        <div className={cn("p-1.5 rounded-lg bg-background/40", c.icon)}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <p className="font-display font-bold text-[2rem] leading-none text-foreground">
        {value}
      </p>

      {change && (
        <p className={cn(
          "text-xs mt-1.5",
          changePositive ? "text-emerald-400" : "text-muted-foreground"
        )}>
          {change}
        </p>
      )}
    </motion.div>
  );
}
