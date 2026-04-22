"use client";

import { useState, useEffect } from "react";

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

export default function RiskDashboard({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RiskDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        setData({
          project_id: projectId,
          total_leases: 12,
          expiring_soon: 3,
          royalty_range: { min: 3.125, max: 18.75 },
          flagged_issues: [
            {
              id: 1,
              lease: "Section 1A - Compass Operating",
              risk_type: "Title Defect",
              severity: "critical",
              description: "Unknown assignee in chain of title (2021-2022). Curative affidavit needed.",
            },
            {
              id: 2,
              lease: "Section 2B - XYZ Energy",
              risk_type: "Expiration",
              severity: "high",
              description: "Primary term expires in 45 days. No continuous drilling on record.",
            },
            {
              id: 3,
              lease: "Section 3C - Independent Operators",
              risk_type: "ORRI Burden",
              severity: "medium",
              description: "1/8 ORRI to John Smith Trust. Verify estate closure and successor parties.",
            },
            {
              id: 4,
              lease: "Section 4D - Regional Operator",
              risk_type: "Rental Payment",
              severity: "low",
              description: "Delay rental payment due in 30 days. Standard renewal.",
            },
          ],
        });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading risk dashboard...</div>;

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-red-50 border-red-300";
      case "high":
        return "bg-orange-50 border-orange-300";
      case "medium":
        return "bg-yellow-50 border-yellow-300";
      default:
        return "bg-blue-50 border-blue-300";
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-red-200 text-red-800";
      case "high":
        return "bg-orange-200 text-orange-800";
      case "medium":
        return "bg-yellow-200 text-yellow-800";
      default:
        return "bg-blue-200 text-blue-800";
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">A&D / Risk Dashboard</h2>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm text-gray-600">Total Leases</div>
          <div className="text-2xl font-bold">{data?.total_leases}</div>
        </div>
        <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
          <div className="text-sm text-gray-600">Expiring Soon</div>
          <div className="text-2xl font-bold text-orange-700">{data?.expiring_soon}</div>
        </div>
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-sm text-gray-600">Royalty Range</div>
          <div className="text-lg font-bold text-red-700">
            {data?.royalty_range.min}% - {data?.royalty_range.max}%
          </div>
        </div>
      </div>

      {/* Flagged Issues */}
      <h3 className="text-lg font-bold mb-4">Flagged Issues Requiring Senior Review</h3>
      <div className="space-y-3">
        {data?.flagged_issues.map((issue) => (
          <div key={issue.id} className={`border rounded-lg p-4 ${getSeverityColor(issue.severity)}`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="font-semibold">{issue.lease}</div>
                <div className="text-sm text-gray-600 mt-1">{issue.description}</div>
              </div>
              <span className={`px-2 py-1 text-xs font-bold rounded-full ml-2 ${getSeverityBadge(issue.severity)}`}>
                {issue.risk_type}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
