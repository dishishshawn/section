"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import EmptyState from "./EmptyState";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface AuditEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  field: string;
  old_value: string | null;
  new_value: string | null;
  user_display: string | null;
  reason: string | null;
  changed_at: string | null;
}

interface AuditDrawerProps {
  projectId: number;
  open: boolean;
  onClose: () => void;
}

export default function AuditDrawer({ projectId, open, onClose }: AuditDrawerProps) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    axios
      .get(`${API_URL}/projects/${projectId}/audit`, { withCredentials: true })
      .then((r) => setEntries(r.data.entries))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [open, projectId]);

  const filtered = filter.trim()
    ? entries.filter((e) =>
        [e.field, e.user_display, e.entity_type, e.old_value, e.new_value, e.reason]
          .filter(Boolean)
          .some((v) => v!.toLowerCase().includes(filter.toLowerCase()))
      )
    : entries;

  const exportCsv = () => {
    const header = "id,entity_type,entity_id,field,old_value,new_value,user,reason,changed_at";
    const rows = filtered.map((e) =>
      [e.id, e.entity_type, e.entity_id, e.field, e.old_value ?? "", e.new_value ?? "", e.user_display ?? "", e.reason ?? "", e.changed_at ?? ""]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-project-${projectId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-ink/20" onClick={onClose} aria-hidden />

      {/* Drawer */}
      <aside className="fixed right-0 top-0 h-full z-50 w-full max-w-xl bg-paper border-l border-rule shadow-[−10px_0_40px_-15px_rgba(29,38,53,0.25)] flex flex-col">
        {/* Header */}
        <div className="border-b-[2.5px] border-rule">
          <div className="border-b border-rule mt-[2px]" />
          <div className="px-8 py-6 flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow mb-1">Section III — Provenance</div>
              <h2 className="font-display text-[1.8rem] font-medium text-ink leading-none tracking-tight">
                Audit trail
              </h2>
              <p className="mt-1.5 font-serif-italic text-ink-2 text-sm">
                Every human correction, in order.
              </p>
            </div>
            <button onClick={onClose} className="text-ink-3 hover:text-ink text-2xl leading-none mt-1" aria-label="Close">×</button>
          </div>
        </div>

        {/* Controls */}
        <div className="px-8 py-3 border-b border-line flex items-center gap-3">
          <input
            type="search"
            placeholder="Filter by field, user, value…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="flex-1 text-sm bg-surface border border-line px-3 py-1.5 focus:outline-none focus:border-accent font-serif-italic text-ink placeholder:text-ink-3"
          />
          <button
            onClick={exportCsv}
            className="text-xs font-serif-italic text-ink-3 hover:text-ink transition-colors whitespace-nowrap"
          >
            Export CSV ↓
          </button>
        </div>

        {/* Entries */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="px-8 py-12 text-sm font-serif-italic text-ink-3 flex items-center gap-2">
              <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin" />
              Loading…
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-6 py-8">
              <EmptyState
                title="No overrides recorded yet"
                description="Edit a grantor or grantee name on the Runsheet to create the first audit entry."
              />
            </div>
          ) : (
            <ol className="divide-y divide-line">
              {filtered.map((e) => (
                <li key={e.id} className="px-8 py-5">
                  <div className="flex items-baseline justify-between gap-3 mb-1.5">
                    <div className="flex items-baseline gap-2 flex-wrap">
                      <span className="font-display text-[1rem] text-ink capitalize">{e.field}</span>
                      <span className="text-xs font-serif-italic text-ink-3 capitalize">{e.entity_type} #{e.entity_id}</span>
                    </div>
                    <span className="tabular text-xs text-ink-3 whitespace-nowrap">
                      {e.changed_at ? new Date(e.changed_at.endsWith("Z") ? e.changed_at : e.changed_at + "Z").toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                    </span>
                  </div>

                  <div className="text-[0.93rem] text-ink-2 leading-snug mb-1">
                    {e.old_value && (
                      <>
                        <span className="line-through text-ink-3">{e.old_value}</span>
                        <span className="mx-2 text-accent">→</span>
                      </>
                    )}
                    <span className="font-medium text-ink">{e.new_value}</span>
                  </div>

                  <div className="flex items-baseline gap-3 text-xs font-serif-italic text-ink-3">
                    {e.user_display && <span>{e.user_display}</span>}
                    {e.reason && (
                      <>
                        <span className="text-line-strong">·</span>
                        <span>"{e.reason}"</span>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </aside>
    </>
  );
}
