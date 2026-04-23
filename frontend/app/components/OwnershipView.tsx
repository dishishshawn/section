"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { SourceRef } from "./SourceBadge";

interface Owner {
  name: string;
  fraction: string;
  percentage: number;
  mineral_estate: string;
  source: SourceRef | null;
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
      <div className="px-10 py-12 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        <span className="font-serif-italic">Loading ownership…</span>
      </div>
    );
  }
  if (error) return <div className="px-10 py-12 text-sm text-danger font-serif-italic">{error}</div>;

  const isEmpty = !data?.owners?.length;

  return (
    <div className="px-10 py-12">
      <div className="mb-8">
        <div className="eyebrow mb-2">Section III</div>
        <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
          Ownership position
        </h2>
        <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
          Fractional mineral interests, with the instrument that established each.
        </p>
      </div>

      {isEmpty ? (
        <div className="border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
          <div className="font-display text-xl text-ink mb-1">No ownership of record</div>
          <p className="text-sm text-ink-3 font-serif-italic max-w-md mx-auto">
            Upload deeds in the Documents tab to establish fractional ownership.
          </p>
        </div>
      ) : (
        <>
          {/* Acreage summary — styled like an abstract cover sheet */}
          <div className="grid grid-cols-3 border-y-[2.5px] border-rule divide-x divide-line-strong mb-10">
            <Stat label="Total acres" value={data!.total_acres} />
            <Stat label="Under lease" value={data!.leased_acres} tone="positive" />
            <Stat label="Open" value={data!.open_acres} tone="warn" />
          </div>

          {/* Owner register */}
          <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
            <h3 className="font-display text-xl font-medium text-ink">
              Fractional ownership
            </h3>
            <span className="text-sm font-serif-italic text-ink-3 tabular">
              {data!.owners.length} part{data!.owners.length === 1 ? "y" : "ies"}
            </span>
          </div>

          <ul className="divide-y divide-line">
            {data!.owners.map((owner, idx) => (
              <li key={idx} className="py-5">
                <div className="grid grid-cols-[2rem_minmax(0,1fr)_auto] gap-5 items-baseline mb-2">
                  {/* Roman-ish small numeral */}
                  <div className="text-right font-serif-italic text-ink-3 text-[0.9rem] tabular">
                    {idx + 1}.
                  </div>
                  <div className="min-w-0">
                    <div className="font-display text-[1.2rem] font-medium text-ink leading-tight truncate">
                      {owner.name}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-numeric text-[1.35rem] text-ink leading-none">
                      {owner.percentage}%
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-[2rem_minmax(0,1fr)_auto] gap-5">
                  <div />
                  <div>
                    {/* Ownership bar — thin pen-drawn feel */}
                    <div className="relative w-full h-[6px] bg-line/70 mb-2 overflow-hidden rounded-[1px]">
                      <div
                        className="absolute inset-y-0 left-0 bg-accent rounded-[1px] transition-all"
                        style={{ width: `${Math.min(owner.percentage, 100)}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="text-sm text-ink-3 flex items-center gap-2.5">
                        <span className="tabular font-medium text-ink-2">{owner.fraction}</span>
                        <span className="text-line-strong">·</span>
                        <span className="font-serif-italic">{owner.mineral_estate}</span>
                      </div>
                      <SourceBadge source={owner.source} />
                    </div>
                  </div>
                  <div />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "positive" | "warn";
}) {
  const valueColor =
    tone === "positive" ? "text-positive" : tone === "warn" ? "text-warn" : "text-ink";
  return (
    <div className="bg-paper px-6 py-6">
      <div className="eyebrow mb-2">{label}</div>
      <div className={`font-numeric text-[2.4rem] leading-none ${valueColor}`}>
        {value}
        <span className="text-sm font-serif-italic text-ink-3 font-normal ml-1.5">ac</span>
      </div>
    </div>
  );
}
