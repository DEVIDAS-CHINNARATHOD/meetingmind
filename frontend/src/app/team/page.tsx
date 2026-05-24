"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UserPlus, Crown, Eye, ShieldCheck, Trash2 } from "lucide-react";
import { teamService } from "@/services";
import { Card, CardHeader, CardTitle, Button, Input, EmptyState } from "@/components/ui/primitives";
import { formatDate } from "@/lib/utils";

const ROLE_ICON: Record<string, React.ElementType> = {
  admin: Crown, manager: ShieldCheck, viewer: Eye,
};
const ROLE_COLOR: Record<string, string> = {
  admin: "text-violet-400", manager: "text-blue-400", viewer: "text-emerald-400",
};

export default function TeamPage() {
  const qc = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [showInvite, setShowInvite] = useState(false);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["team", "members"],
    queryFn: teamService.members,
  });
  const { data: workspace } = useQuery({
    queryKey: ["team", "workspace"],
    queryFn: teamService.workspace,
  });

  const inviteMutation = useMutation({
    mutationFn: () => teamService.invite({ name: inviteName, email: inviteEmail, role: inviteRole }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["team"] });
      toast.success(`Invite sent to ${inviteEmail}`);
      setShowInvite(false); setInviteEmail(""); setInviteName("");
    },
    onError: () => toast.error("Invite failed"),
  });

  const removeMutation = useMutation({
    mutationFn: teamService.remove,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["team"] }); toast.success("Member removed"); },
  });

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-bold text-xl text-foreground">Team</h2>
          {workspace && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {workspace.name} · {workspace.plan} plan · {workspace.member_count} members
            </p>
          )}
        </div>
        <Button variant="primary" onClick={() => setShowInvite(true)}>
          <UserPlus className="w-4 h-4" /> Invite Member
        </Button>
      </div>

      {/* Invite form */}
      {showInvite && (
        <Card className="border-violet-500/25 bg-violet-500/5">
          <CardTitle className="mb-4">Invite New Member</CardTitle>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            <Input label="Name" value={inviteName} onChange={(e) => setInviteName(e.target.value)} placeholder="Full name" />
            <Input label="Email" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="email@company.com" />
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full h-9 px-3 bg-secondary border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-violet-500/50"
              >
                <option value="viewer">Viewer</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="primary" size="sm" loading={inviteMutation.isPending}
              onClick={() => inviteMutation.mutate()} disabled={!inviteEmail || !inviteName}>
              Send Invite
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowInvite(false)}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Members list */}
      <Card className="p-0 overflow-hidden">
        <div className="grid grid-cols-[1fr_120px_140px_80px] gap-3 px-5 py-3 bg-secondary/50 border-b border-border">
          {["Member","Role","Joined",""].map(h => (
            <p key={h} className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{h}</p>
          ))}
        </div>
        {members.length === 0 ? (
          <EmptyState icon={UserPlus} title="No members yet" description="Invite team members to collaborate." />
        ) : (
          <div className="divide-y divide-border/50">
            {members.map((m) => {
              const RoleIcon = ROLE_ICON[m.role] ?? Eye;
              return (
                <div key={m.id} className="grid grid-cols-[1fr_120px_140px_80px] gap-3 items-center px-5 py-3.5 hover:bg-secondary/40 transition-colors group">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center text-white text-xs font-bold shrink-0">
                      {m.name[0]?.toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">{m.name}</p>
                      <p className="text-[11px] text-muted-foreground truncate">{m.email}</p>
                    </div>
                  </div>
                  <div className={`flex items-center gap-1.5 text-xs font-medium ${ROLE_COLOR[m.role]}`}>
                    <RoleIcon className="w-3.5 h-3.5" />
                    {m.role.charAt(0).toUpperCase() + m.role.slice(1)}
                  </div>
                  <p className="text-xs text-muted-foreground">{formatDate(m.created_at)}</p>
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon-sm" className="hover:text-red-400"
                      onClick={() => confirm("Remove member?") && removeMutation.mutate(m.id)}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
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
