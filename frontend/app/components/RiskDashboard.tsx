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

const severityStyles: Record<string, { bg: string; badge: string }> = {
  critical: { bg: "bg-red-50 border-red-300", badge: "bg-red-200 text-red-800" },
  high: { bg: "bg-orange-50 border-orange-300", badge: "bg-orange-200 text-orange-800" },
  medium: { bg: "bg-yellow-50 border-yellow-300", badge: "bg-yellow-200 text-yellow-800" },
  low: { bg: "bg-blue-50 border-blue-300", badge: "bg-blue-200 text-blue-800" },
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

  if (loading) return <div className="p-4">Loading risk dashboard...</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  const isEmpty = !data?.total_leases && !data?.flagged_issues?.length;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">A&D / Risk Dashboard</h2>

      {isEmpty ? (
        <div className="p-8 text-center border-2 border-dashed border-slate-300 rounded-lg">
          <p className="text-slate-500 mb-2">No risk data yet.</p>
          <p className="text-sm text-slate-400">
            Upload documents to surface title defects, expirations, and burdens.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="text-sm text-gray-600">Total Leases</div>
              <div className="text-2xl font-bold">{data!.total_leases}</div>
            </div>
            <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
              <div className="text-sm text-gray-600">Expiring Soon</div>
              <div className="text-2xl font-bold text-orange-700">{data!.expiring_soon}</div>
            </div>
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="text-sm text-gray-600">Royalty Range</div>
              <div className="text-lg font-bold text-red-700">
                {data!.royalty_range.min}% - {data!.royalty_range.max}%
              </div>
            </div>
          </div>

          {data!.flagged_issues.length > 0 && (
            <>
              <h3 className="text-lg font-bold mb-4">Flagged Issues Requiring Senior Review</h3>
              <div className="space-y-3">
                {data!.flagged_issues.map((issue) => {
                  const style = severityStyles[issue.severity] || severityStyles.low;
                  return (
                    <div key={issue.id} className={`border rounded-lg p-4 ${style.bg}`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-semibold">{issue.lease}</div>
                          <div className="text-sm text-gray-600 mt-1">{issue.description}</div>
                        </div>
                        <span className={`px-2 py-1 text-xs font-bold rounded-full ml-2 ${style.badge}`}>
                          {issue.risk_type}
                        </span>
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
