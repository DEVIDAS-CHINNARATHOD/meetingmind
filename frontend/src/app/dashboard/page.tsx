"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Mic2, Clock, CheckSquare, Sparkles, TrendingUp, Users, ArrowRight,
  BarChart3, Zap,
} from "lucide-react";
import Link from "next/link";
import { analyticsService, meetingService } from "@/services";
import { Card, CardHeader, CardTitle, Badge, Button, Skeleton, EmptyState } from "@/components/ui/primitives";
import {
  formatDuration, formatDate, timeAgo,
  getMeetingStatusColor, getMeetingStatusLabel,
} from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip,
  AreaChart, Area,
} from "recharts";

// ── Stat card ─────────────────────────────────────────────────

function StatCard({
  icon: Icon, label, value, change, color = "violet", loading,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  change?: string;
  color?: "violet" | "teal" | "amber" | "blue";
  loading?: boolean;
}) {
  const colors = {
    violet: "from-violet-500/20 to-violet-600/10 border-violet-500/20",
    teal:   "from-emerald-500/15 to-emerald-600/8 border-emerald-500/15",
    amber:  "from-amber-500/15 to-amber-600/8 border-amber-500/15",
    blue:   "from-blue-500/15 to-blue-600/8 border-blue-500/15",
  };
  const iconColors = {
    violet: "text-violet-400", teal: "text-emerald-400",
    amber: "text-amber-400",  blue: "text-blue-400",
  };

  if (loading) {
    return (
      <div className="surface-card p-5 space-y-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-8 w-16" />
        <Skeleton className="h-3 w-32" />
      </div>
    );
  }

  return (
    <div className={`relative overflow-hidden rounded-xl border p-5 bg-gradient-to-br ${colors[color]}`}>
      <div className="flex items-start justify-between mb-3">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest">{label}</p>
        <div className={`p-1.5 rounded-lg bg-background/50 ${iconColors[color]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <p className="font-display font-bold text-3xl text-foreground">{value}</p>
      {change && <p className="text-xs text-emerald-400 mt-1">{change}</p>}
    </div>
  );
}

// ── Custom tooltip ────────────────────────────────────────────

const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className="text-foreground font-semibold">{payload[0].value} meetings</p>
    </div>
  );
};

// ── Page ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: () => analyticsService.overview(30),
  });

  const { data: freq } = useQuery({
    queryKey: ["analytics", "frequency"],
    queryFn: () => analyticsService.meetingFrequency(30),
  });

  const { data: speakersData } = useQuery({
    queryKey: ["analytics", "speakers"],
    queryFn: () => analyticsService.speakers(5),
  });

  const { data: meetingsData, isLoading: meetingsLoading } = useQuery({
    queryKey: ["meetings", { page: 1, page_size: 5 }],
    queryFn: () => meetingService.list({ page: 1, page_size: 5 }),
  });

  const chartData = freq?.data?.slice(-14).map((d) => ({
    date: new Date(d.date).toLocaleDateString("en", { month: "short", day: "numeric" }),
    meetings: d.meetings,
  })) ?? [];

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-bold text-xl text-foreground">
            Good morning 👋
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {overview
              ? `${overview.open_action_items} open action items · ${overview.meetings_in_period} meetings this month`
              : "Loading your workspace…"}
          </p>
        </div>
        <Button variant="primary" size="md" asChild>
          <Link href="/meetings/upload">
            <Zap className="w-4 h-4" />
            Upload Meeting
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Mic2} label="Total Meetings" color="violet"
          value={overview?.total_meetings ?? "—"}
          change={`↑ ${overview?.meetings_in_period ?? 0} this month`}
          loading={overviewLoading}
        />
        <StatCard
          icon={Clock} label="Hours Recorded" color="blue"
          value={overview ? `${overview.total_hours_recorded}h` : "—"}
          change={`avg ${overview?.avg_meeting_minutes ?? 0}m / meeting`}
          loading={overviewLoading}
        />
        <StatCard
          icon={CheckSquare} label="Action Items" color="amber"
          value={overview?.open_action_items ?? "—"}
          change={`${overview?.action_completion_rate_pct ?? 0}% completed`}
          loading={overviewLoading}
        />
        <StatCard
          icon={Sparkles} label="AI Summaries" color="teal"
          value={overview?.total_meetings ?? "—"}
          change="100% coverage"
          loading={overviewLoading}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Activity chart */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Meeting Activity (30 days)</CardTitle>
            <BarChart3 className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <div className="h-44">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barSize={14}>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "hsl(220 15% 55%)" }}
                    axisLine={false}
                    tickLine={false}
                    interval={2}
                  />
                  <YAxis hide />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(124,58,237,0.08)" }} />
                  <Bar dataKey="meetings" radius={[4, 4, 0, 0]}
                    fill="url(#barGrad)" />
                  <defs>
                    <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7c3aed" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#6d28d9" stopOpacity={0.5} />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-sm text-muted-foreground">No data yet</p>
              </div>
            )}
          </div>
        </Card>

        {/* Speaker participation */}
        <Card>
          <CardHeader>
            <CardTitle>Top Speakers</CardTitle>
            <Users className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <div className="space-y-3">
            {speakersData?.speakers?.slice(0, 4).map((sp, i) => (
              <div key={sp.name}>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-foreground truncate max-w-[120px]">{sp.name}</p>
                  <p className="text-xs text-muted-foreground">{sp.participation_pct}%</p>
                </div>
                <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-violet-600 to-violet-400"
                    initial={{ width: 0 }}
                    animate={{ width: `${sp.participation_pct}%` }}
                    transition={{ duration: 0.8, delay: i * 0.1 }}
                  />
                </div>
              </div>
            )) ?? (
              <p className="text-xs text-muted-foreground">No speaker data yet</p>
            )}
          </div>
        </Card>
      </div>

      {/* Recent meetings */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Meetings</CardTitle>
          <Link href="/meetings" className="text-xs text-violet-400 hover:text-violet-300 flex items-center gap-1 transition-colors">
            View all <ArrowRight className="w-3 h-3" />
          </Link>
        </CardHeader>

        {meetingsLoading ? (
          <div className="space-y-2">
            {[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : meetingsData?.items.length === 0 ? (
          <EmptyState
            icon={Mic2}
            title="No meetings yet"
            description="Upload your first meeting recording to get started."
            action={
              <Button variant="primary" size="sm" asChild>
                <Link href="/meetings/upload">Upload Meeting</Link>
              </Button>
            }
          />
        ) : (
          <div className="divide-y divide-border/50">
            {meetingsData?.items.map((meeting) => (
              <Link
                key={meeting.id}
                href={`/meetings/${meeting.id}`}
                className="flex items-center gap-3 py-3 hover:bg-secondary/50 -mx-5 px-5 transition-colors group"
              >
                <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate group-hover:text-violet-300 transition-colors">
                    {meeting.title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {formatDate(meeting.created_at)} · {formatDuration(meeting.duration_seconds)}
                    {meeting.word_count ? ` · ${meeting.word_count.toLocaleString()} words` : ""}
                  </p>
                </div>
                <Badge variant={getMeetingStatusColor(meeting.status) as any}>
                  {getMeetingStatusLabel(meeting.status)}
                </Badge>
                <ArrowRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-violet-400 transition-colors shrink-0" />
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
