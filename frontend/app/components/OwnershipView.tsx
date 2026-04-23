"use client";

import { useState, useEffect } from "react";
import axios from "axios";

interface Owner {
  name: string;
  fraction: string;
  percentage: number;
  mineral_estate: string;
}

interface OwnershipData {
  project_id: number;
  owners: Owner[];
  total_acres: number;
  leased_acres: number;
  open_acres: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function OwnershipView({ projectId }: { projectId: number }) {
  const [data, setData] = useState<OwnershipData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOwnership = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/projects/${projectId}/ownership`);
        setData(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load ownership data");
      } finally {
        setLoading(false);
      }
    };
    fetchOwnership();
  }, [projectId]);

  if (loading) {
    return (
      <div className="px-8 py-10 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        Loading ownership data…
      </div>
    );
  }
  if (error) return <div className="px-8 py-10 text-sm text-danger">{error}</div>;

  const isEmpty = !data?.owners?.length;

  return (
    <div className="px-8 py-10">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
          03 — Ownership
        </div>
        <h2 className="font-display text-3xl font-semibold text-ink">Ownership position</h2>
      </div>

      {isEmpty ? (
        <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
          <div className="font-display text-lg text-ink mb-1">No ownership data yet</div>
          <p className="text-sm text-ink-3 max-w-md mx-auto">
            Upload deeds in the Documents tab to establish fractional ownership.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-px bg-line rounded-xl overflow-hidden border border-line mb-10">
            <Stat label="Total acres" value={data!.total_acres} suffix="ac" />
            <Stat label="Leased" value={data!.leased_acres} suffix="ac" tone="positive" />
            <Stat label="Open" value={data!.open_acres} suffix="ac" tone="warn" />
          </div>

          <div className="flex items-baseline justify-between mb-4">
            <h3 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink-3">
              Fractional ownership
            </h3>
            <span className="text-xs text-ink-3 tabular">{data!.owners.length} parties</span>
          </div>
          <div className="space-y-2">
            {data!.owners.map((owner, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-line bg-surface px-4 py-4 hover:border-line-strong transition-colors"
              >
                <div className="flex items-center justify-between mb-2.5">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="flex-shrink-0 w-7 h-7 rounded-md bg-accent-tint text-accent-strong font-mono text-xs font-semibold flex items-center justify-center tabular">
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    <span className="font-display font-semibold text-ink truncate">
                      {owner.name}
                    </span>
                  </div>
                  <span className="font-mono text-sm tabular text-ink font-semibold">
                    {owner.percentage}%
                  </span>
                </div>
                <div className="relative w-full h-1.5 bg-line/60 rounded-full overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 bg-accent rounded-full transition-all"
                    style={{ width: `${Math.min(owner.percentage, 100)}%` }}
                  />
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs text-ink-3 font-mono tabular">
                  <span>{owner.fraction}</span>
                  <span className="text-line-strong">·</span>
                  <span>{owner.mineral_estate}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  suffix,
  tone = "neutral",
}: {
  label: string;
  value: number;
  suffix?: string;
  tone?: "neutral" | "positive" | "warn";
}) {
  const valueColor =
    tone === "positive" ? "text-positive" : tone === "warn" ? "text-warn" : "text-ink";
  return (
    <div className="bg-surface px-5 py-5">
      <div className="text-[0.7rem] font-mono uppercase tracking-[0.16em] text-ink-3 mb-2">
        {label}
      </div>
      <div className={`font-display text-3xl font-semibold tabular ${valueColor}`}>
        {value}
        {suffix && <span className="text-base text-ink-3 font-normal ml-1">{suffix}</span>}
      </div>
    </div>
  );
}
