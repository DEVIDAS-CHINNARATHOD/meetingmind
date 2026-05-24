"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, Clock, CheckSquare, Users, TrendingUp } from "lucide-react";
import { analyticsService } from "@/services";
import { Card, CardHeader, CardTitle, Skeleton } from "@/components/ui/primitives";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip,
  AreaChart, Area, PieChart, Pie, Cell, Legend,
} from "recharts";
import { getSpeakerColor } from "@/lib/utils";

const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className="text-foreground font-semibold">{payload[0].value}</p>
    </div>
  );
};

function KpiCard({ label, value, sub, icon: Icon, color }: any) {
  const bg = color === "violet" ? "from-violet-500/15" : color === "teal" ? "from-emerald-500/12" : color === "amber" ? "from-amber-500/12" : "from-blue-500/12";
  const ic = color === "violet" ? "text-violet-400" : color === "teal" ? "text-emerald-400" : color === "amber" ? "text-amber-400" : "text-blue-400";
  return (
    <div className={`rounded-xl border border-border p-5 bg-gradient-to-br ${bg} to-transparent`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</p>
        <Icon className={`w-4 h-4 ${ic}`} />
      </div>
      <p className="font-display font-bold text-2xl text-foreground">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: overview, isLoading } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: () => analyticsService.overview(30),
  });
  const { data: freq } = useQuery({
    queryKey: ["analytics", "frequency"],
    queryFn: () => analyticsService.meetingFrequency(30),
  });
  const { data: speakersData } = useQuery({
    queryKey: ["analytics", "speakers"],
    queryFn: () => analyticsService.speakers(8),
  });

  const freqChart = freq?.data?.slice(-14).map((d) => ({
    date: new Date(d.date).toLocaleDateString("en", { month: "short", day: "numeric" }),
    meetings: d.meetings,
  })) ?? [];

  const speakers = speakersData?.speakers ?? [];

  const pieData = [
    { name: "Completed", value: overview?.completed_action_items ?? 0 },
    { name: "Pending",   value: overview?.open_action_items ?? 0 },
  ];

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h2 className="font-display font-bold text-xl text-foreground">Analytics</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Last 30 days · workspace overview</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={BarChart3} label="Total Meetings" color="violet"
          value={isLoading ? "…" : overview?.total_meetings ?? 0}
          sub={`${overview?.meetings_in_period ?? 0} this month`} />
        <KpiCard icon={Clock} label="Avg Length" color="blue"
          value={isLoading ? "…" : `${overview?.avg_meeting_minutes ?? 0}m`}
          sub="per meeting" />
        <KpiCard icon={CheckSquare} label="Action Rate" color="amber"
          value={isLoading ? "…" : `${overview?.action_completion_rate_pct ?? 0}%`}
          sub={`${overview?.open_action_items ?? 0} open`} />
        <KpiCard icon={Users} label="Hours Recorded" color="teal"
          value={isLoading ? "…" : `${overview?.total_hours_recorded ?? 0}h`}
          sub="total" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Frequency */}
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Meeting Frequency (14 days)</CardTitle></CardHeader>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={freqChart}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stopColor="#7c3aed" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#7c3aed" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(220 15% 55%)" }} axisLine={false} tickLine={false} interval={1} />
                <YAxis hide />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="meetings" stroke="#7c3aed" strokeWidth={2} fill="url(#areaGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Action item donut */}
        <Card>
          <CardHeader><CardTitle>Action Items</CardTitle></CardHeader>
          <div className="h-52 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={72} paddingAngle={3} dataKey="value">
                  <Cell fill="#7c3aed" />
                  <Cell fill="hsl(224 25% 14%)" />
                </Pie>
                <Legend formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Speaker analytics */}
      <Card>
        <CardHeader>
          <CardTitle>Talk Time by Speaker</CardTitle>
          <p className="text-xs text-muted-foreground">across all meetings</p>
        </CardHeader>
        {speakers.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No speaker data — diarization required.
          </p>
        ) : (
          <div className="space-y-3">
            {speakers.map((sp, i) => {
              const color = getSpeakerColor(i);
              return (
                <div key={sp.name}>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs font-medium text-foreground">{sp.name}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span>{sp.total_talk_time_minutes}m</span>
                      <span>{sp.total_words.toLocaleString()} words</span>
                      <span>{sp.meetings_attended} mtgs</span>
                    </div>
                  </div>
                  <div className="h-2 bg-secondary rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ background: `linear-gradient(90deg, ${color.text}cc, ${color.text}55)` }}
                      initial={{ width: 0 }}
                      animate={{ width: `${sp.participation_pct}%` }}
                      transition={{ duration: 0.9, delay: i * 0.08 }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
