"use client";

import { useState, useEffect } from "react";
import axios from "axios";

interface RiskItem {
  id: number;
  lease: string;
  risk_type: string;
  severity: "critical" | "high" | "medium" | "low";
  description: string;
}

interface RiskDashboardData {
  project_id: number;
  total_leases: number;
  expiring_soon: number;
  flagged_issues: RiskItem[];
  royalty_range: { min: number; max: number };
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const SEVERITY: Record<
  string,
  { rail: string; chip: string; label: string }
> = {
  critical: { rail: "bg-danger", chip: "bg-danger-soft text-danger", label: "Critical" },
  high: { rail: "bg-warn", chip: "bg-warn-soft text-warn", label: "High" },
  medium: { rail: "bg-accent", chip: "bg-accent-soft text-accent-strong", label: "Medium" },
  low: { rail: "bg-info", chip: "bg-info-soft text-info", label: "Low" },
};

export default function RiskDashboard({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RiskDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/projects/${projectId}/risk`);
        setData(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load risk dashboard");
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [projectId]);

  if (loading) {
    return (
      <div className="px-8 py-10 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        Loading risk dashboard…
      </div>
    );
  }
  if (error) return <div className="px-8 py-10 text-sm text-danger">{error}</div>;

  const isEmpty = !data?.total_leases && !data?.flagged_issues?.length;

  return (
    <div className="px-8 py-10">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
          05 — A&D / Risk
        </div>
        <h2 className="font-display text-3xl font-semibold text-ink">Risk dashboard</h2>
      </div>

      {isEmpty ? (
        <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
          <div className="font-display text-lg text-ink mb-1">No risk data yet</div>
          <p className="text-sm text-ink-3 max-w-md mx-auto">
            Upload documents to surface title defects, expirations, and burdens.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-px bg-line rounded-xl overflow-hidden border border-line mb-10">
            <Metric label="Total leases" value={data!.total_leases.toString()} />
            <Metric
              label="Expiring soon"
              value={data!.expiring_soon.toString()}
              tone={data!.expiring_soon > 0 ? "warn" : "neutral"}
            />
            <Metric
              label="Royalty range"
              value={`${data!.royalty_range.min}–${data!.royalty_range.max}%`}
            />
          </div>

          {data!.flagged_issues.length > 0 && (
            <>
              <div className="flex items-baseline justify-between mb-4">
                <h3 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink-3">
                  Flagged issues
                </h3>
                <span className="text-xs text-ink-3 tabular">
                  {data!.flagged_issues.length} requiring senior review
                </span>
              </div>
              <div className="space-y-2">
                {data!.flagged_issues.map((issue) => {
                  const meta = SEVERITY[issue.severity] || SEVERITY.low;
                  return (
                    <div
                      key={issue.id}
                      className="relative rounded-xl border border-line bg-surface pl-5 pr-4 py-4 hover:border-line-strong transition-colors"
                    >
                      <span className={`absolute left-0 top-3 bottom-3 w-1 rounded-r ${meta.rail}`} />
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="font-display font-semibold text-ink">{issue.lease}</div>
                          <div className="mt-1 text-sm text-ink-2">{issue.description}</div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          <span className={`text-xs font-mono uppercase tracking-wider px-2 py-1 rounded-md ${meta.chip}`}>
                            {meta.label}
                          </span>
                          <span className="text-[0.7rem] font-mono text-ink-3">{issue.risk_type}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warn";
}) {
  const valueColor = tone === "warn" ? "text-warn" : "text-ink";
  return (
    <div className="bg-surface px-5 py-5">
      <div className="text-[0.7rem] font-mono uppercase tracking-[0.16em] text-ink-3 mb-2">
        {label}
      </div>
      <div className={`font-display text-3xl font-semibold tabular ${valueColor}`}>{value}</div>
    </div>
  );
}
