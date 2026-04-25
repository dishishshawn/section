"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { ReviewedBadge, ReviewMeta, SourceRef } from "./SourceBadge";
import EditableFact from "./EditableFact";
import EmptyState from "./EmptyState";

interface ChainItem {
  instrument_id: number;
  instrument_type: string;
  grantor: string;
  grantee: string;
  date: string;
  status: "complete" | "missing" | "flagged";
  source: SourceRef | null;
  reviewed: Record<string, ReviewMeta>;
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
  complete: { label: "Of record", class: "text-positive", italics: true },
  flagged: { label: "Review", class: "text-warn", italics: true },
  missing: { label: "Incomplete", class: "text-rust", italics: true },
} as const;

export default function Runsheet({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RunsheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => { fetchRunsheet(); }, [projectId]);

  if (loading) {
    return (
      <div className="px-10 py-12 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        <span className="font-serif-italic">Loading runsheet…</span>
      </div>
    );
  }
  if (error) return <div className="px-10 py-12 text-sm text-danger font-serif-italic">{error}</div>;

  const isEmpty = !data?.chain?.length;

  return (
    <div className="px-10 py-12">
      <SectionHeading
        eyebrow="Section II"
        title="Chain of title"
        subtitle="Every recorded instrument that touches this tract, in order of date."
      />

      {isEmpty ? (
        <EmptyState
          title="No instruments of record"
          description="Upload a document to see instruments — Section will build the chain of title automatically."
        />
      ) : (
        <>
          {/* Table-style register — like a courthouse grantor/grantee index */}
          <div className="border-t-[2.5px] border-rule">
            <div className="border-t border-rule mt-[3px] mb-4" />
            <ol>
              {data!.chain.map((item, idx) => {
                const meta = STATUS[item.status];
                return (
                  <li
                    key={idx}
                    className="grid grid-cols-[3rem_minmax(0,1fr)_auto] gap-4 items-baseline py-5 border-b border-line last:border-b-0 group"
                  >
                    {/* Entry number */}
                    <div className="text-right">
                      <div className="font-numeric text-[1.1rem] text-ink-3 leading-none">
                        {String(idx + 1).padStart(2, "0")}
                      </div>
                    </div>

                    {/* Main record body */}
                    <div className="min-w-0">
                      <div className="flex items-baseline gap-3 flex-wrap mb-1">
                        <span className="font-display text-[1.15rem] font-medium text-ink">
                          {item.instrument_type}
                        </span>
                        <span className="tabular text-sm text-ink-3">{item.date}</span>
                      </div>
                      <div className="text-[0.98rem] text-ink-2 leading-snug">
                        <EditableFact
                          entityType="instrument"
                          entityId={item.instrument_id}
                          field="grantor"
                          value={item.grantor}
                          sourceQuote={item.source?.quote ?? null}
                          reviewMeta={item.reviewed?.grantor ?? null}
                          onSave={fetchRunsheet}
                          renderValue={(v) => <span className="font-medium">{v}</span>}
                        />
                        <span className="mx-2 text-accent">→</span>
                        <EditableFact
                          entityType="instrument"
                          entityId={item.instrument_id}
                          field="grantee"
                          value={item.grantee}
                          sourceQuote={item.source?.quote ?? null}
                          reviewMeta={item.reviewed?.grantee ?? null}
                          onSave={fetchRunsheet}
                          renderValue={(v) => <span className="font-medium">{v}</span>}
                        />
                      </div>
                      <div className="mt-2 flex items-center gap-4 flex-wrap">
                        {Object.keys(item.reviewed).length > 0 ? (
                          <ReviewedBadge
                            meta={Object.values(item.reviewed)[0]}
                            source={item.source}
                          />
                        ) : (
                          <SourceBadge source={item.source} />
                        )}
                      </div>
                    </div>

                    {/* Status column */}
                    <div className="text-right">
                      <span className={`font-serif-italic text-sm ${meta.class}`}>
                        {meta.label}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="border-b-[2.5px] border-rule mt-[3px]" />
            <div className="border-b border-rule mt-[3px]" />
          </div>

          {data!.gaps.length > 0 && (
            <section className="mt-16">
              <div className="mb-8 flex items-end justify-between gap-6">
                <div>
                  <div className="eyebrow text-rust mb-2">Section III</div>
                  <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
                    Curative
                  </h2>
                  <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
                    Gaps, defects, and items that must be resolved before title can be certified.
                  </p>
                </div>
                <div className="tabular text-sm text-ink-3 whitespace-nowrap pb-1">
                  {data!.gaps.length} item{data!.gaps.length === 1 ? "" : "s"}
                </div>
              </div>

              <div className="border-t-[2.5px] border-rust/70">
                <div className="border-t border-rule mt-[3px] mb-4" />
                <ol>
                  {data!.gaps.map((gap, idx) => {
                    const hasParties = Boolean(gap.from && gap.to);
                    return (
                      <li
                        key={idx}
                        className="grid grid-cols-[3rem_minmax(0,1fr)_auto] gap-4 items-baseline py-5 border-b border-line last:border-b-0"
                      >
                        <div className="text-right">
                          <div className="font-numeric text-[1.1rem] text-ink-3 leading-none">
                            {String(idx + 1).padStart(2, "0")}
                          </div>
                        </div>
                        <div className="min-w-0">
                          <div className="font-display text-[1.15rem] font-medium text-ink mb-1">
                            {gap.missing_document}
                          </div>
                          {hasParties && (
                            <div className="text-[0.98rem] text-ink-2 leading-snug">
                              <span className="font-medium">{gap.from}</span>
                              <span className="mx-2 text-accent">→</span>
                              <span className="font-medium">{gap.to}</span>
                            </div>
                          )}
                        </div>
                        <div className="text-right">
                          <span className="font-serif-italic text-sm text-rust">
                            Curative
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <div className="border-b-[2.5px] border-rust/70 mt-[3px]" />
                <div className="border-b border-rule mt-[3px]" />
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-8">
      <div className="eyebrow mb-2">{eyebrow}</div>
      <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
          {subtitle}
        </p>
      )}
    </div>
  );
}

