"use client";

import { useState, useEffect } from "react";

interface Obligation {
  id: number;
  type: string;
  due_date: string;
  days_until: number;
  priority: "high" | "medium" | "low";
  description: string;
}

export default function ObligationCalendar({ projectId }: { projectId: number }) {
  const [obligations, setObligations] = useState<Obligation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchObligations = async () => {
      try {
        const now = new Date();
        setObligations([
          {
            id: 1,
            type: "Primary Term Expiration",
            due_date: new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
            days_until: 90,
            priority: "high",
            description: "Section 1A, Township 12N - primary lease term expires",
          },
          {
            id: 2,
            type: "Pugh Clause Trigger",
            due_date: new Date(now.getTime() + 180 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
            days_until: 180,
            priority: "medium",
            description: "Non-core acreage must be released from lease obligations",
          },
          {
            id: 3,
            type: "Continuous Drilling Requirement",
            due_date: new Date(now.getTime() + 45 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
            days_until: 45,
            priority: "high",
            description: "Must drill or plug within 90 days of last well completion",
          },
          {
            id: 4,
            type: "Rental Payment",
            due_date: new Date(now.getTime() + 15 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
            days_until: 15,
            priority: "high",
            description: "$500 delay rental due to maintain lease",
          },
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchObligations();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading obligations...</div>;

  const highPriority = obligations.filter((o) => o.priority === "high");
  const mediumPriority = obligations.filter((o) => o.priority === "medium");

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Obligation Calendar</h2>

      {highPriority.length > 0 && (
        <div className="mb-6 p-4 bg-red-50 border border-red-300 rounded-lg">
          <h3 className="font-bold text-red-800 mb-3">⚠️ HIGH PRIORITY (Next 90 days)</h3>
          <div className="space-y-3">
            {highPriority.map((obl) => (
              <div key={obl.id} className="bg-white p-3 rounded border-l-4 border-red-500">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-semibold">{obl.type}</div>
                    <div className="text-sm text-gray-600">{obl.description}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-red-600 font-bold">{obl.days_until} days</div>
                    <div className="text-xs text-gray-500">{obl.due_date}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {mediumPriority.length > 0 && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg">
          <h3 className="font-bold text-yellow-800 mb-3">⚡ MEDIUM PRIORITY</h3>
          <div className="space-y-3">
            {mediumPriority.map((obl) => (
              <div key={obl.id} className="bg-white p-3 rounded border-l-4 border-yellow-500">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-semibold">{obl.type}</div>
                    <div className="text-sm text-gray-600">{obl.description}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm text-yellow-600 font-bold">{obl.days_until} days</div>
                    <div className="text-xs text-gray-500">{obl.due_date}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
