"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Org {
  id: number;
  name: string;
  slug: string;
  billing_status: string | null;
  your_role: string | null;
}

interface OrgSwitcherProps {
  currentOrgId: number | null;
  onOrgChange: (org: Org | null) => void;
}

export default function OrgSwitcher({ currentOrgId, onOrgChange }: OrgSwitcherProps) {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgSlug, setNewOrgSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchOrgs();
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const fetchOrgs = async () => {
    try {
      const res = await axios.get(`${API_URL}/orgs`, { withCredentials: true });
      setOrgs(res.data);
      // Auto-select the first org if none selected
      if (!currentOrgId && res.data.length > 0) {
        onOrgChange(res.data[0]);
      }
    } catch {
      // Not in any org yet — fine
    }
  };

  const createOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await axios.post(
        `${API_URL}/orgs`,
        { name: newOrgName.trim(), slug: newOrgSlug.trim().toLowerCase().replace(/\s+/g, "-") },
        { withCredentials: true }
      );
      const created = res.data as Org;
      setOrgs([...orgs, created]);
      onOrgChange(created);
      setCreating(false);
      setNewOrgName("");
      setNewOrgSlug("");
      setOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create workspace");
    } finally {
      setSubmitting(false);
    }
  };

  const currentOrg = orgs.find((o) => o.id === currentOrgId) || null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setOpen(!open); setCreating(false); }}
        className="flex items-center gap-2 px-3 py-1.5 border border-line-strong bg-surface hover:bg-surface-2 transition-colors rounded-sm text-sm"
      >
        <span className="font-medium text-ink truncate max-w-[140px]">
          {currentOrg ? currentOrg.name : "Personal"}
        </span>
        {currentOrg && (
          <span className="text-[0.65rem] font-serif-italic text-ink-3 border border-line px-1 rounded-sm uppercase tracking-wide">
            {currentOrg.your_role}
          </span>
        )}
        <span className="text-ink-3 text-xs ml-0.5" aria-hidden>▾</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1.5 w-64 bg-paper border border-line-strong shadow-lg z-50 rounded-sm">
          {/* Personal (no org) */}
          <button
            onClick={() => { onOrgChange(null); setOpen(false); }}
            className={`w-full text-left px-4 py-3 text-sm transition-colors hover:bg-surface-2 flex items-center justify-between ${!currentOrgId ? "bg-surface-2" : ""}`}
          >
            <span className="font-medium text-ink">Personal</span>
            {!currentOrgId && <span className="text-xs text-ink-3">current</span>}
          </button>

          {orgs.length > 0 && (
            <>
              <div className="border-t border-line mx-3 my-1" />
              <div className="px-4 py-1">
                <span className="text-[0.7rem] eyebrow text-ink-3">Workspaces</span>
              </div>
              {orgs.map((org) => (
                <button
                  key={org.id}
                  onClick={() => { onOrgChange(org); setOpen(false); }}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-surface-2 flex items-center justify-between ${currentOrgId === org.id ? "bg-surface-2" : ""}`}
                >
                  <div>
                    <div className="font-medium text-ink">{org.name}</div>
                    <div className="text-[0.75rem] text-ink-3 font-serif-italic">{org.slug}</div>
                  </div>
                  <span className="text-[0.65rem] font-serif-italic text-ink-3 border border-line px-1 rounded-sm uppercase tracking-wide ml-2 flex-shrink-0">
                    {org.your_role}
                  </span>
                </button>
              ))}
            </>
          )}

          <div className="border-t border-line mx-3 my-1" />

          {!creating ? (
            <button
              onClick={() => setCreating(true)}
              className="w-full text-left px-4 py-2.5 text-sm text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors font-serif-italic"
            >
              + New workspace
            </button>
          ) : (
            <form onSubmit={createOrg} className="px-4 py-3 space-y-2">
              <div className="text-xs font-medium text-ink mb-2">New workspace</div>
              <input
                type="text"
                placeholder="Name (e.g. Apex Land Co.)"
                value={newOrgName}
                onChange={(e) => {
                  setNewOrgName(e.target.value);
                  setNewOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""));
                }}
                required
                autoFocus
                className="w-full px-3 py-2 text-sm border border-line-strong bg-surface focus:outline-none focus:border-accent rounded-sm"
              />
              <input
                type="text"
                placeholder="slug"
                value={newOrgSlug}
                onChange={(e) => setNewOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                required
                className="w-full px-3 py-2 text-sm border border-line-strong bg-surface focus:outline-none focus:border-accent rounded-sm font-mono"
              />
              {error && <p className="text-xs text-rust">{error}</p>}
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 px-3 py-2 bg-ink text-paper text-xs font-medium hover:bg-accent transition-colors disabled:bg-ink-3 rounded-sm"
                >
                  {submitting ? "Creating…" : "Create"}
                </button>
                <button
                  type="button"
                  onClick={() => setCreating(false)}
                  className="px-3 py-2 text-xs text-ink-3 hover:text-ink border border-line-strong rounded-sm"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
