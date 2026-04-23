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
  { rail: string; label: string; chip: string }
> = {
  critical: { rail: "bg-rust", label: "Critical", chip: "text-rust" },
  high: { rail: "bg-warn", label: "High", chip: "text-warn" },
  medium: { rail: "bg-accent", label: "Medium", chip: "text-accent" },
  low: { rail: "bg-info", label: "Low", chip: "text-info" },
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
      <div className="px-10 py-12 text-sm text-ink-3">
        <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
        <span className="font-serif-italic">Loading risk dashboard…</span>
      </div>
    );
  }
  if (error) return <div className="px-10 py-12 text-sm text-danger font-serif-italic">{error}</div>;

  const isEmpty = !data?.total_leases && !data?.flagged_issues?.length;

  return (
    <div className="px-10 py-12">
      <div className="mb-8">
        <div className="eyebrow mb-2">Section V</div>
        <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
          A&amp;D &amp; risk summary
        </h2>
        <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
          The partner-memo view: title defects, burdens, and approaching deadlines at a glance.
        </p>
      </div>

      {isEmpty ? (
        <div className="border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
          <div className="font-display text-xl text-ink mb-1">No risk data yet</div>
          <p className="text-sm text-ink-3 font-serif-italic max-w-md mx-auto">
            Upload documents to surface title defects, expirations, and burdens.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 border-y-[2.5px] border-rule divide-x divide-line-strong mb-10">
            <Metric label="Leases of record" value={data!.total_leases.toString()} />
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
              <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
                <h3 className="font-display text-xl font-medium text-ink">
                  Matters requiring senior review
                </h3>
                <span className="text-sm font-serif-italic text-ink-3 tabular">
                  {data!.flagged_issues.length}
                </span>
              </div>
              <ul className="divide-y divide-line">
                {data!.flagged_issues.map((issue) => {
                  const meta = SEVERITY[issue.severity] || SEVERITY.low;
                  return (
                    <li key={issue.id} className="relative py-5 pl-5">
                      <span className={`absolute left-0 top-6 bottom-6 w-[3px] ${meta.rail}`} aria-hidden />
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-6 items-baseline">
                        <div className="min-w-0">
                          <div className="flex items-baseline gap-3 flex-wrap">
                            <span className="font-display text-[1.2rem] font-medium text-ink leading-tight">
                              {issue.lease}
                            </span>
                            <span className="text-xs font-serif-italic text-ink-3">
                              {issue.risk_type}
                            </span>
                          </div>
                          <p className="mt-1 text-[0.98rem] text-ink-2 leading-snug">
                            {issue.description}
                          </p>
                        </div>
                        <div className="text-right">
                          <span className={`font-serif-italic text-sm ${meta.chip}`}>
                            {meta.label}
                          </span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
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
    <div className="bg-paper px-6 py-6">
      <div className="eyebrow mb-2">{label}</div>
      <div className={`font-numeric text-[2.4rem] leading-none ${valueColor}`}>
        {value}
      </div>
    </div>
  );
}
