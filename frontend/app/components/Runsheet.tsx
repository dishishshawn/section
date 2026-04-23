"use client";

import { useState, useEffect } from "react";
import axios from "axios";

interface ChainItem {
  instrument_type: string;
  grantor: string;
  grantee: string;
  date: string;
  status: "complete" | "missing" | "flagged";
}

interface Gap {
  from: string;
  to: string;
  missing_document: string;
}

interface RunsheetData {
  project_id: number;
  chain: ChainItem[];
  gaps: Gap[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const STATUS = {
  complete: { dot: "bg-positive", label: "Complete", chip: "bg-positive-soft text-positive" },
  flagged: { dot: "bg-warn", label: "Review", chip: "bg-warn-soft text-warn" },
  missing: { dot: "bg-danger", label: "Missing", chip: "bg-danger-soft text-danger" },
} as const;

export default function Runsheet({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RunsheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRunsheet = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/projects/${projectId}/runsheet`);
        setData(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load runsheet");
      } finally {
        setLoading(false);
      }
    };
    fetchRunsheet();
  }, [projectId]);

  if (loading) {
    return (
      <div className="px-8 py-10 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        Loading runsheet…
      </div>
    );
  }
  if (error) return <div className="px-8 py-10 text-sm text-danger">{error}</div>;

  const isEmpty = !data?.chain?.length;

  return (
    <div className="px-8 py-10">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
          02 — Runsheet
        </div>
        <h2 className="font-display text-3xl font-semibold text-ink">Chain of title</h2>
      </div>

      {isEmpty ? (
        <EmptyState
          title="No instruments yet"
          body="Upload deeds, leases, or assignments in the Documents tab to build the chain of title."
        />
      ) : (
        <>
          <ol className="relative space-y-3 mb-10">
            <span className="absolute left-[19px] top-2 bottom-2 w-px bg-line" aria-hidden />
            {data!.chain.map((item, idx) => {
              const meta = STATUS[item.status];
              return (
                <li
                  key={idx}
                  className="relative pl-12 rounded-xl border border-line bg-surface px-4 py-4 hover:border-line-strong transition-colors"
                >
                  <span
                    className={`absolute left-3 top-5 w-3.5 h-3.5 rounded-full ring-4 ring-paper ${meta.dot}`}
                    aria-hidden
                  />
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="font-display text-base font-semibold text-ink">
                        {item.instrument_type}
                      </div>
                      <div className="mt-1 text-sm text-ink-2">
                        <span className="font-medium">{item.grantor}</span>
                        <span className="mx-2 text-ink-3">→</span>
                        <span className="font-medium">{item.grantee}</span>
                      </div>
                      <div className="mt-1 text-xs font-mono tabular text-ink-3">{item.date}</div>
                    </div>
                    <span className={`shrink-0 text-xs font-mono uppercase tracking-wider px-2 py-1 rounded-md ${meta.chip}`}>
                      {meta.label}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>

          {data!.gaps.length > 0 && (
            <section className="rounded-xl border border-danger/30 bg-danger-soft/40 px-5 py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="font-mono text-[0.65rem] uppercase tracking-[0.18em] text-danger">
                  Curative
                </span>
                <span className="text-xs text-ink-3 tabular">{data!.gaps.length} item(s)</span>
              </div>
              <ul className="space-y-2">
                {data!.gaps.map((gap, idx) => (
                  <li key={idx} className="text-sm text-ink-2 flex items-start gap-2">
                    <span className="text-danger mt-0.5">·</span>
                    <span className="font-medium">{gap.missing_document}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
      <div className="font-display text-lg text-ink mb-1">{title}</div>
      <p className="text-sm text-ink-3 max-w-md mx-auto">{body}</p>
    </div>
  );
}
