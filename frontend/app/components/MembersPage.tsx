"use client";

import { useEffect, useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Member {
  user_id: number;
  email: string;
  display_name: string | null;
  role: string;
  joined_at: string;
}

interface InviteResult {
  id: number;
  invited_email: string;
  role: string;
  expires_at: string;
  dev_link: string | null;
}

interface MembersPageProps {
  orgId: number;
  orgName: string;
  yourRole: string;
  onClose: () => void;
}

const ORG_ROLES = ["owner", "admin", "member"] as const;
type OrgRole = (typeof ORG_ROLES)[number];

export default function MembersPage({ orgId, orgName, yourRole, onClose }: MembersPageProps) {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<OrgRole>("member");
  const [inviting, setInviting] = useState(false);
  const [inviteResult, setInviteResult] = useState<InviteResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [billingStatus, setBillingStatus] = useState<string | null>(null);
  const [seatCount, setSeatCount] = useState(0);

  const canManage = yourRole === "owner" || yourRole === "admin";

  useEffect(() => {
    fetchMembers();
    fetchBilling();
  }, []);

  const fetchMembers = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_URL}/orgs/${orgId}/members`, {
        withCredentials: true,
      });
      setMembers(res.data);
    } catch {
      setError("Failed to load members");
    } finally {
      setLoading(false);
    }
  };

  const fetchBilling = async () => {
    try {
      const res = await axios.get(`${API_URL}/billing/org/${orgId}/status`, {
        withCredentials: true,
      });
      setBillingStatus(res.data.billing_status);
      setSeatCount(res.data.seat_count);
    } catch {
      // billing may not be configured
    }
  };

  const sendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviting(true);
    setError(null);
    setInviteResult(null);
    try {
      const res = await axios.post(
        `${API_URL}/orgs/${orgId}/invites`,
        { email: inviteEmail.trim().toLowerCase(), role: inviteRole },
        { withCredentials: true }
      );
      setInviteResult(res.data);
      setInviteEmail("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  };

  const updateRole = async (userId: number, role: OrgRole) => {
    try {
      await axios.patch(
        `${API_URL}/orgs/${orgId}/members/${userId}`,
        { role },
        { withCredentials: true }
      );
      setMembers(members.map((m) => (m.user_id === userId ? { ...m, role } : m)));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update role");
    }
  };

  const removeMember = async (userId: number) => {
    if (!confirm("Remove this member from the workspace?")) return;
    try {
      await axios.delete(`${API_URL}/orgs/${orgId}/members/${userId}`, {
        withCredentials: true,
      });
      setMembers(members.filter((m) => m.user_id !== userId));
      setSeatCount((c) => Math.max(c - 1, 0));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to remove member");
    }
  };

  const roleBadgeClass = (role: string) => {
    if (role === "owner") return "text-accent-strong border-accent/40";
    if (role === "admin") return "text-ink border-line-strong";
    return "text-ink-3 border-line";
  };

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-paper-deep border-b-[2.5px] border-rule">
        <div className="max-w-4xl mx-auto px-10 pt-8 pb-10">
          <button
            onClick={onClose}
            className="group inline-flex items-center gap-2 text-sm text-ink-3 hover:text-ink transition-colors mb-8"
          >
            <span className="inline-block text-accent transition-transform group-hover:-translate-x-0.5">←</span>
            <span className="font-serif-italic">Back</span>
          </button>

          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="eyebrow mb-1.5">Workspace members</div>
              <h1 className="font-display text-3xl font-medium text-ink tracking-tight">{orgName}</h1>
              {billingStatus && (
                <div className="mt-3 flex items-center gap-3 text-sm">
                  <span className="font-serif-italic text-ink-3">
                    {seatCount} {seatCount === 1 ? "seat" : "seats"}
                  </span>
                  <span className="text-line-strong">·</span>
                  <span className={`font-serif-italic capitalize ${
                    billingStatus === "active" ? "text-positive" :
                    billingStatus === "trialing" ? "text-ink-2" : "text-rust"
                  }`}>
                    {billingStatus}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-10 py-12 space-y-12">
        {error && (
          <div className="flex items-start gap-3 border-l-2 border-rust bg-rust-soft/40 px-4 py-3">
            <span className="font-serif-italic text-rust mt-0.5">Error —</span>
            <span className="text-ink-2 text-sm">{error}</span>
          </div>
        )}

        {/* Invite form */}
        {canManage && (
          <section>
            <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
              <h2 className="font-display text-xl font-medium text-ink">Invite a team member</h2>
            </div>
            <form onSubmit={sendInvite}>
              <div className="border border-line-strong bg-surface rounded-sm overflow-hidden">
                <div className="grid md:grid-cols-[1fr_160px_auto] divide-x divide-line-strong">
                  <input
                    type="email"
                    placeholder="colleague@company.com"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    required
                    className="px-5 py-4 bg-surface text-ink placeholder:text-ink-3 placeholder:font-serif-italic focus:outline-none focus:bg-accent-tint transition-colors text-[1rem]"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as OrgRole)}
                    className="px-4 py-4 bg-surface text-ink focus:outline-none text-[0.95rem] capitalize"
                  >
                    {ORG_ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={inviting}
                    className="px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors disabled:bg-ink-3 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {inviting ? (
                      <>
                        <span className="inline-block w-3 h-3 border-2 border-paper/30 border-t-paper rounded-full animate-spin" />
                        <span>Sending</span>
                      </>
                    ) : (
                      <span>Send invite →</span>
                    )}
                  </button>
                </div>
              </div>
            </form>

            {inviteResult && (
              <div className="mt-4 border-l-[3px] border-positive pl-4 py-2">
                <div className="font-display text-base text-ink">Invite sent</div>
                <p className="mt-1 text-sm font-serif-italic text-ink-2">
                  Link sent to <strong>{inviteResult.invited_email}</strong> — expires{" "}
                  {new Date(inviteResult.expires_at).toLocaleDateString()}.
                </p>
                {inviteResult.dev_link && (
                  <div className="mt-2 text-xs font-mono text-ink-3 break-all bg-surface border border-line px-3 py-2 rounded-sm">
                    <span className="text-ink-2 font-sans font-medium">Dev link: </span>
                    <a
                      href={inviteResult.dev_link}
                      className="text-accent hover:underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {inviteResult.dev_link}
                    </a>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* Member list */}
        <section>
          <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
            <h2 className="font-display text-xl font-medium text-ink">Members</h2>
            <span className="text-sm font-serif-italic text-ink-3 tabular">
              {members.length} {members.length === 1 ? "member" : "members"}
            </span>
          </div>

          {loading ? (
            <div className="py-12 text-center text-ink-3 text-sm">
              <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
              <span className="font-serif-italic">Loading members…</span>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {members.map((m) => (
                <li
                  key={m.user_id}
                  className="group py-4 flex items-center gap-4"
                >
                  {/* Avatar initial */}
                  <div className="w-9 h-9 rounded-full bg-surface border border-line-strong flex items-center justify-center flex-shrink-0">
                    <span className="font-display text-sm font-medium text-ink">
                      {(m.display_name || m.email)[0].toUpperCase()}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink truncate">
                        {m.display_name || m.email}
                      </span>
                      <span
                        className={`text-[0.65rem] border px-1.5 py-0.5 rounded-sm capitalize font-serif-italic flex-shrink-0 ${roleBadgeClass(m.role)}`}
                      >
                        {m.role}
                      </span>
                    </div>
                    {m.display_name && (
                      <div className="text-sm text-ink-3 font-serif-italic">{m.email}</div>
                    )}
                    <div className="text-xs text-ink-3 mt-0.5 tabular">
                      Joined {new Date(m.joined_at).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                  </div>

                  {canManage && (
                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                      <select
                        value={m.role}
                        onChange={(e) => updateRole(m.user_id, e.target.value as OrgRole)}
                        className="text-xs border border-line bg-surface px-2 py-1 text-ink focus:outline-none"
                      >
                        {ORG_ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => removeMember(m.user_id)}
                        className="text-xs text-ink-3 hover:text-rust transition-colors px-2 py-1 border border-transparent hover:border-rust/30 font-serif-italic"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
