"use client";

import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { toast } from "sonner";
import { User, Key, Bell, Cpu, Building } from "lucide-react";
import { Card, CardHeader, CardTitle, Button, Input } from "@/components/ui/primitives";

type Section = "profile" | "api" | "ai" | "notifications" | "workspace";

export default function SettingsPage() {
  const { user } = useUser();
  const [section, setSection] = useState<Section>("profile");

  const nav = [
    { id: "profile" as Section,       icon: User,     label: "Profile" },
    { id: "api" as Section,            icon: Key,      label: "API Keys" },
    { id: "ai" as Section,             icon: Cpu,      label: "AI Models" },
    { id: "notifications" as Section,  icon: Bell,     label: "Notifications" },
    { id: "workspace" as Section,      icon: Building, label: "Workspace" },
  ];

  return (
    <div className="p-6 animate-fade-in">
      <div className="mb-6">
        <h2 className="font-display font-bold text-xl text-foreground">Settings</h2>
        <p className="text-sm text-muted-foreground mt-0.5">Manage your account and workspace preferences</p>
      </div>

      <div className="flex gap-5">
        {/* Sidebar */}
        <div className="w-44 shrink-0 space-y-0.5">
          {nav.map(({ id, icon: Icon, label }) => (
            <button key={id} onClick={() => setSection(id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${section === id ? "bg-violet-500/15 text-violet-300 border border-violet-500/25" : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-4">
          {section === "profile" && (
            <Card>
              <CardTitle className="mb-5">Profile</CardTitle>
              <div className="flex items-center gap-4 mb-6 pb-5 border-b border-border">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center text-white text-xl font-bold">
                  {user?.firstName?.[0] ?? "U"}
                </div>
                <div>
                  <p className="font-semibold text-foreground">{user?.fullName ?? "User"}</p>
                  <p className="text-sm text-muted-foreground">{user?.primaryEmailAddress?.emailAddress}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input label="Display Name" defaultValue={user?.fullName ?? ""} />
                <Input label="Email" type="email" defaultValue={user?.primaryEmailAddress?.emailAddress ?? ""} disabled />
              </div>
              <Button variant="primary" size="sm" className="mt-4" onClick={() => toast.success("Profile updated!")}>
                Save Changes
              </Button>
            </Card>
          )}

          {section === "api" && (
            <Card>
              <CardTitle className="mb-5">API Keys</CardTitle>
              <div className="space-y-4">
                <Input label="Groq API Key" type="password" placeholder="gsk_…" />
                <Input label="OpenAI API Key (fallback)" type="password" placeholder="sk-…" />
                <Input label="HuggingFace Token (diarization)" type="password" placeholder="hf_…" />
              </div>
              <Button variant="primary" size="sm" className="mt-4" onClick={() => toast.success("Keys saved!")}>
                Save Keys
              </Button>
            </Card>
          )}

          {section === "ai" && (
            <Card>
              <CardTitle className="mb-5">AI Configuration</CardTitle>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Primary LLM</label>
                  <select className="w-full h-9 px-3 bg-secondary border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-violet-500/50">
                    <option>llama-3.3-70b-versatile (Groq)</option>
                    <option>deepseek-r1-distill-llama-70b (Groq)</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">Transcription Engine</label>
                  <select className="w-full h-9 px-3 bg-secondary border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-violet-500/50">
                    <option>Faster Whisper large-v3</option>
                    <option>Faster Whisper medium</option>
                  </select>
                </div>
                <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-foreground">Speaker Diarization</p>
                    <p className="text-xs text-muted-foreground">Requires HuggingFace token</p>
                  </div>
                  <div className="w-10 h-5 bg-violet-600 rounded-full relative cursor-pointer">
                    <div className="w-3.5 h-3.5 bg-white rounded-full absolute right-0.75 top-0.75" />
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-foreground">Face Recognition</p>
                    <p className="text-xs text-muted-foreground">InsightFace buffalo_l</p>
                  </div>
                  <div className="w-10 h-5 bg-violet-600 rounded-full relative cursor-pointer">
                    <div className="w-3.5 h-3.5 bg-white rounded-full absolute right-0.75 top-0.75" />
                  </div>
                </div>
              </div>
              <Button variant="primary" size="sm" className="mt-4" onClick={() => toast.success("AI config saved!")}>
                Save
              </Button>
            </Card>
          )}

          {section === "notifications" && (
            <Card>
              <CardTitle className="mb-5">Notifications</CardTitle>
              <div className="space-y-3">
                {[
                  { label: "Meeting processed",    sub: "When transcription and summary complete", on: true },
                  { label: "Action item reminders", sub: "Daily digest of pending tasks",           on: true },
                  { label: "Team mentions",         sub: "When you are assigned an action item",    on: false },
                  { label: "Slack alerts",          sub: "Post MoM to configured Slack channel",   on: false },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-foreground">{item.label}</p>
                      <p className="text-xs text-muted-foreground">{item.sub}</p>
                    </div>
                    <div className={`w-10 h-5 rounded-full relative cursor-pointer transition-colors ${item.on ? "bg-violet-600" : "bg-secondary border border-border"}`}>
                      <div className={`w-3.5 h-3.5 bg-white rounded-full absolute top-0.75 transition-all ${item.on ? "right-0.75" : "left-0.75"}`} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {section === "workspace" && (
            <Card>
              <CardTitle className="mb-5">Workspace</CardTitle>
              <div className="space-y-4">
                <Input label="Workspace Name" defaultValue="My Workspace" />
                <Input label="Workspace Slug" defaultValue="my-workspace" />
                <div className="p-3 bg-secondary rounded-lg">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Current Plan</p>
                  <p className="text-sm font-semibold text-violet-400">Pro Plan</p>
                  <p className="text-xs text-muted-foreground mt-0.5">Unlimited meetings · Speaker diarization · AI Chat</p>
                </div>
              </div>
              <Button variant="primary" size="sm" className="mt-4" onClick={() => toast.success("Workspace updated!")}>
                Save
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
