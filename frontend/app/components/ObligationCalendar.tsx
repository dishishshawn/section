"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { ReviewedBadge, ReviewMeta, SourceRef } from "./SourceBadge";
import EditableFact from "./EditableFact";
import EmptyState from "./EmptyState";

interface Obligation {
  id: number;
  type: string;
  due_date: string | null;
  days_until: number;
  priority: "high" | "medium" | "low";
  description: string;
  source: SourceRef | null;
  reviewed: Record<string, ReviewMeta>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function formatType(raw: string): string {
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const BUCKETS = {
  high: {
    label: "Immediate attention",
    note: "Within 30 days",
    accent: "text-rust",
    rail: "bg-rust",
  },
  medium: {
    label: "On the calendar",
    note: "31 to 120 days out",
    accent: "text-warn",
    rail: "bg-warn",
  },
  low: {
    label: "In the distance",
    note: "More than 120 days out",
    accent: "text-positive",
    rail: "bg-positive",
  },
} as const;

export default function ObligationCalendar({ projectId }: { projectId: number }) {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchObligations = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/projects/${projectId}/obligations`);
      setObligations(res.data.obligations || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load obligations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchObligations(); }, [projectId]);

  if (loading) {
    return (
      <div className="px-10 py-12 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        <span className="font-serif-italic">Loading obligations…</span>
      </div>
    );
  }
  if (error) return <div className="px-10 py-12 text-sm text-danger font-serif-italic">{error}</div>;

  const heading = (
    <div className="mb-8">
      <div className="eyebrow mb-2">Section IV</div>
      <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
        Obligation calendar
      </h2>
      <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
        Term expirations, Pugh triggers, rentals, and drilling deadlines &mdash; in order of urgency.
      </p>
    </div>
  );

  if (obligations.length === 0) {
    return (
      <div className="px-10 py-12">
        {heading}
        <EmptyState
          title="No obligations extracted from this project"
          description="Upload leases in the Documents tab — Section will track term expirations, rentals, and drilling deadlines."
        />
      </div>
    );
  }

  const buckets: { key: "high" | "medium" | "low"; items: Obligation[] }[] = [
    { key: "high", items: obligations.filter((o) => o.priority === "high") },
    { key: "medium", items: obligations.filter((o) => o.priority === "medium") },
    { key: "low", items: obligations.filter((o) => o.priority === "low") },
  ];

  return (
    <div className="px-10 py-12">
      {heading}

      <div className="space-y-10">
        {buckets.map(({ key, items }) =>
          items.length === 0 ? null : (
            <section key={key}>
              <div className="flex items-baseline justify-between mb-3 pb-2 rule-hairline">
                <div>
                  <h3 className={`font-display text-xl font-medium ${BUCKETS[key].accent}`}>
                    {BUCKETS[key].label}
                  </h3>
                  <div className="text-xs font-serif-italic text-ink-3 mt-0.5">
                    {BUCKETS[key].note}
                  </div>
                </div>
                <span className="text-sm font-serif-italic text-ink-3 tabular">
                  {items.length}
                </span>
              </div>

              <ul className="divide-y divide-line">
                {items.map((obl) => (
                  <li key={obl.id} className="py-5 relative pl-5">
                    <span className={`absolute left-0 top-6 bottom-6 w-[3px] ${BUCKETS[key].rail}`} aria-hidden />
                    <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-6 items-baseline">
                      <div className="min-w-0">
                        <div className="font-display text-[1.2rem] font-medium text-ink leading-tight">
                          <EditableFact
                            entityType="obligation"
                            entityId={obl.id}
                            field="type"
                            value={formatType(obl.type)}
                            reviewMeta={obl.reviewed?.type ?? null}
                            onSave={fetchObligations}
                          />
                        </div>
                        <p className="mt-1 text-[0.98rem] text-ink-2 leading-snug">
                          <EditableFact
                            entityType="obligation"
                            entityId={obl.id}
                            field="description"
                            value={obl.description}
                            sourceQuote={obl.source?.quote ?? null}
                            reviewMeta={obl.reviewed?.description ?? null}
                            onSave={fetchObligations}
                          />
                        </p>
                        <div className="mt-2">
                          {Object.keys(obl.reviewed || {}).length > 0 ? (
                            <ReviewedBadge meta={Object.values(obl.reviewed)[0]} source={obl.source} />
                          ) : (
                            <SourceBadge source={obl.source} />
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-numeric text-[1.8rem] text-ink leading-none">
                          {obl.days_until}
                          <span className="text-xs font-serif-italic text-ink-3 font-normal ml-1">days</span>
                        </div>
                        <div className="mt-1.5 text-xs tabular text-ink-3">
                          {obl.due_date?.slice(0, 10)}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )
        )}
      </div>
    </div>
  );
}
