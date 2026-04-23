"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { SourceRef } from "./SourceBadge";

interface Obligation {
  id: number;
  type: string;
  due_date: string | null;
  days_until: number;
  priority: "high" | "medium" | "low";
  description: string;
  source: SourceRef | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function formatType(raw: string): string {
  return raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

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

  if (loading) return <div className="p-4">Loading obligations...</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  if (obligations.length === 0) {
    return (
      <div className="p-4">
        <h2 className="text-2xl font-bold mb-6">Obligation Calendar</h2>
        <div className="p-8 text-center border-2 border-dashed border-slate-300 rounded-lg">
          <p className="text-slate-500 mb-2">No obligations yet.</p>
          <p className="text-sm text-slate-400">
            Upload leases in the Documents tab to track term expirations, Pugh triggers, and rental payments.
          </p>
        </div>
      </div>
    );
  }

  const highPriority = obligations.filter((o) => o.priority === "high");
  const mediumPriority = obligations.filter((o) => o.priority === "medium");
  const lowPriority = obligations.filter((o) => o.priority === "low");

  const renderBucket = (items: Obligation[], title: string, colorClass: string, borderClass: string) => (
    <div className={`mb-6 p-4 ${colorClass} border ${borderClass} rounded-lg`}>
      <h3 className="font-bold mb-3">{title}</h3>
      <div className="space-y-3">
        {items.map((obl) => (
          <div key={obl.id} className="bg-white p-3 rounded border-l-4 border-slate-500">
            <div className="flex justify-between items-start gap-4">
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{formatType(obl.type)}</div>
                <div className="text-sm text-gray-600">{obl.description}</div>
                <div className="mt-1">
                  <SourceBadge source={obl.source} />
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-bold">{obl.days_until} days</div>
                <div className="text-xs text-gray-500">{obl.due_date?.slice(0, 10)}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Obligation Calendar</h2>
      {highPriority.length > 0 && renderBucket(highPriority, "HIGH PRIORITY (Next 30 days)", "bg-red-50", "border-red-300")}
      {mediumPriority.length > 0 && renderBucket(mediumPriority, "MEDIUM PRIORITY (31-120 days)", "bg-yellow-50", "border-yellow-300")}
      {lowPriority.length > 0 && renderBucket(lowPriority, "LOW PRIORITY (120+ days)", "bg-blue-50", "border-blue-300")}
    </div>
  );
}
