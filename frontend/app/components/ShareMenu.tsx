"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface AccessEntry {
  user_id: number;
  email: string;
  display_name: string | null;
  role: string;
}

interface ShareMenuProps {
  projectId: number;
  orgId: number | null;
  yourRole: string;
}

const PROJECT_ROLES = ["owner", "editor", "viewer"] as const;
type ProjectRole = (typeof PROJECT_ROLES)[number];

export default function ShareMenu({ projectId, orgId, yourRole }: ShareMenuProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"access" | "invite">("access");
  const [entries, setEntries] = useState<AccessEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<ProjectRole>("viewer");
  const [inviteOrgRole, setInviteOrgRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteResult, setInviteResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const canManage = yourRole === "owner" || yourRole === "editor";

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const fetchAccess = async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const res = await axios.get(
        `${API_URL}/orgs/${orgId}/projects/${projectId}/access`,
        { withCredentials: true }
      );
      setEntries(res.data);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    fetchAccess();
  };

  const updateRole = async (userId: number, role: ProjectRole) => {
    if (!orgId) return;
    try {
      await axios.patch(
        `${API_URL}/orgs/${orgId}/projects/${projectId}/access/${userId}`,
        { role },
        { withCredentials: true }
      );
      setEntries(entries.map((e) => (e.user_id === userId ? { ...e, role } : e)));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update role");
    }
  };

  const revokeAccess = async (userId: number) => {
    if (!orgId) return;
    try {
      await axios.delete(
        `${API_URL}/orgs/${orgId}/projects/${projectId}/access/${userId}`,
        { withCredentials: true }
      );
      setEntries(entries.filter((e) => e.user_id !== userId));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to revoke access");
    }
  };

  const sendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgId) return;
    setInviting(true);
    setError(null);
    setInviteResult(null);
    try {
      const res = await axios.post(
        `${API_URL}/orgs/${orgId}/invites`,
        {
          email: inviteEmail.trim().toLowerCase(),
          role: inviteOrgRole,
          project_id: projectId,
          project_role: inviteRole,
        },
        { withCredentials: true }
      );
      const data = res.data;
      if (data.dev_link) {
        setInviteResult(`Dev link: ${data.dev_link}`);
      } else {
        setInviteResult(`Invite sent to ${inviteEmail}`);
      }
      setInviteEmail("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={handleOpen}
        className="flex items-center gap-2 px-4 py-2 border border-line-strong bg-surface hover:bg-surface-2 transition-colors text-sm font-medium text-ink"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-3">
          <circle cx="10" cy="2" r="1.5" />
          <circle cx="4" cy="7" r="1.5" />
          <circle cx="10" cy="12" r="1.5" />
          <line x1="5.3" y1="6.2" x2="8.7" y2="3.0" />
          <line x1="5.3" y1="7.8" x2="8.7" y2="11.0" />
        </svg>
        Share
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-80 bg-paper border border-line-strong shadow-lg z-50 rounded-sm">
          <div className="px-4 pt-4 pb-2">
            <h3 className="font-display text-base font-medium text-ink">Share project</h3>
            {!orgId && (
              <p className="mt-1 text-xs text-ink-3 font-serif-italic">
                Create a workspace first to share with your team.
              </p>
            )}
          </div>

          {orgId && (
            <>
              {/* Tab strip */}
              <div className="flex border-b border-line mx-4 mb-3">
                {(["access", "invite"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`px-3 py-2 text-xs transition-colors capitalize ${
                      tab === t
                        ? "text-ink font-medium border-b-2 border-accent -mb-px"
                        : "text-ink-3 hover:text-ink"
                    }`}
                  >
                    {t === "access" ? "Members with access" : "Invite"}
                  </button>
                ))}
              </div>

              {tab === "access" && (
                <div className="px-4 pb-4">
                  {loading ? (
                    <p className="text-xs text-ink-3 font-serif-italic py-4 text-center">Loading…</p>
                  ) : entries.length === 0 ? (
                    <p className="text-xs text-ink-3 font-serif-italic py-2">No explicit access records — members can see this project via their org role.</p>
                  ) : (
                    <ul className="space-y-1">
                      {entries.map((entry) => (
                        <li key={entry.user_id} className="flex items-center justify-between gap-2 py-1.5">
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-ink truncate">
                              {entry.display_name || entry.email}
                            </div>
                            {entry.display_name && (
                              <div className="text-xs text-ink-3 truncate">{entry.email}</div>
                            )}
                          </div>
                          {canManage ? (
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              <select
                                value={entry.role}
                                onChange={(e) => updateRole(entry.user_id, e.target.value as ProjectRole)}
                                className="text-xs border border-line bg-surface px-1.5 py-0.5 text-ink focus:outline-none"
                              >
                                {PROJECT_ROLES.map((r) => (
                                  <option key={r} value={r}>{r}</option>
                                ))}
                              </select>
                              <button
                                onClick={() => revokeAccess(entry.user_id)}
                                className="text-xs text-ink-3 hover:text-rust transition-colors"
                                title="Revoke"
                              >
                                ×
                              </button>
                            </div>
                          ) : (
                            <span className="text-xs text-ink-3 font-serif-italic capitalize">{entry.role}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {error && <p className="mt-2 text-xs text-rust">{error}</p>}
                </div>
              )}

              {tab === "invite" && (
                <form onSubmit={sendInvite} className="px-4 pb-4 space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-ink mb-1">Email address</label>
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      required
                      placeholder="colleague@company.com"
                      className="w-full px-3 py-2 text-sm border border-line-strong bg-surface focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-ink mb-1">Workspace role</label>
                      <select
                        value={inviteOrgRole}
                        onChange={(e) => setInviteOrgRole(e.target.value)}
                        className="w-full px-2 py-1.5 text-sm border border-line-strong bg-surface focus:outline-none"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                        <option value="owner">Owner</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-ink mb-1">Project access</label>
                      <select
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value as ProjectRole)}
                        className="w-full px-2 py-1.5 text-sm border border-line-strong bg-surface focus:outline-none"
                      >
                        {PROJECT_ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  {inviteResult && (
                    <div className="border-l-2 border-positive pl-3 py-1">
                      <p className="text-xs text-ink break-all">{inviteResult}</p>
                    </div>
                  )}
                  {error && <p className="text-xs text-rust">{error}</p>}
                  <button
                    type="submit"
                    disabled={inviting}
                    className="w-full px-3 py-2 bg-ink text-paper text-sm font-medium hover:bg-accent transition-colors disabled:bg-ink-3"
                  >
                    {inviting ? "Sending…" : "Send invite"}
                  </button>
                </form>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
