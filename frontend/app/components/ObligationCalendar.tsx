"use client";

import { useState, useEffect } from "react";
import axios from "axios";

interface Obligation {
  id: number;
  type: string;
  due_date: string | null;
  days_until: number;
  priority: "high" | "medium" | "low";
  description: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function formatType(raw: string): string {
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const BUCKETS = {
  high: {
    rail: "bg-danger",
    chipDot: "bg-danger",
    label: "High priority",
    note: "Next 30 days",
  },
  medium: {
    rail: "bg-warn",
    chipDot: "bg-warn",
    label: "Medium",
    note: "31–120 days",
  },
  low: {
    rail: "bg-info",
    chipDot: "bg-info",
    label: "Low",
    note: "120+ days",
  },
} as const;

export default function ObligationCalendar({ projectId }: { projectId: number }) {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
    fetchObligations();
  }, [projectId]);

  if (loading) {
    return (
      <div className="px-8 py-10 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        Loading obligations…
      </div>
    );
  }
  if (error) return <div className="px-8 py-10 text-sm text-danger">{error}</div>;

  const heading = (
    <div className="mb-8">
      <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
        04 — Obligations
      </div>
      <h2 className="font-display text-3xl font-semibold text-ink">Obligation calendar</h2>
    </div>
  );

  if (obligations.length === 0) {
    return (
      <div className="px-8 py-10">
        {heading}
        <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
          <div className="font-display text-lg text-ink mb-1">No obligations yet</div>
          <p className="text-sm text-ink-3 max-w-md mx-auto">
            Upload leases in the Documents tab to track term expirations, Pugh triggers, and rental
            payments.
          </p>
        </div>
      </div>
    );
  }

  const buckets: { key: "high" | "medium" | "low"; items: Obligation[] }[] = [
    { key: "high", items: obligations.filter((o) => o.priority === "high") },
    { key: "medium", items: obligations.filter((o) => o.priority === "medium") },
    { key: "low", items: obligations.filter((o) => o.priority === "low") },
  ];

  return (
    <div className="px-8 py-10">
      {heading}
      <div className="space-y-8">
        {buckets.map(({ key, items }) =>
          items.length === 0 ? null : (
            <section key={key}>
              <div className="flex items-baseline justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${BUCKETS[key].chipDot}`} />
                  <h3 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink">
                    {BUCKETS[key].label}
                  </h3>
                  <span className="text-xs text-ink-3 font-mono">{BUCKETS[key].note}</span>
                </div>
                <span className="text-xs text-ink-3 tabular">{items.length}</span>
              </div>
              <div className="space-y-2">
                {items.map((obl) => (
                  <div
                    key={obl.id}
                    className="relative rounded-xl border border-line bg-surface pl-5 pr-4 py-4 hover:border-line-strong transition-colors"
                  >
                    <span className={`absolute left-0 top-3 bottom-3 w-1 rounded-r ${BUCKETS[key].rail}`} />
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="font-display font-semibold text-ink">
                          {formatType(obl.type)}
                        </div>
                        <div className="mt-1 text-sm text-ink-2">{obl.description}</div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-display text-xl font-semibold tabular text-ink">
                          {obl.days_until}
                          <span className="text-xs text-ink-3 font-normal ml-1">days</span>
                        </div>
                        <div className="text-[0.7rem] font-mono tabular text-ink-3">
                          {obl.due_date?.slice(0, 10)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )
        )}
      </div>
    </div>
  );
}
