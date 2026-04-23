"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { SourceRef } from "./SourceBadge";

interface ChainItem {
  instrument_type: string;
  grantor: string;
  grantee: string;
  date: string;
  status: "complete" | "missing" | "flagged";
  source: SourceRef | null;
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

export default function Runsheet({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RunsheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
    fetchRunsheet();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading runsheet...</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  const isEmpty = !data?.chain?.length;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Chain of Title</h2>

      {isEmpty ? (
        <div className="p-8 text-center border-2 border-dashed border-slate-300 rounded-lg">
          <p className="text-slate-500 mb-2">No instruments yet.</p>
          <p className="text-sm text-slate-400">
            Upload deeds, leases, or assignments in the Documents tab to build the chain of title.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-2 mb-8">
            {data!.chain.map((item, idx) => (
              <div
                key={idx}
                className={`p-4 border rounded-lg ${
                  item.status === "missing"
                    ? "bg-red-50 border-red-300"
                    : item.status === "flagged"
                      ? "bg-yellow-50 border-yellow-300"
                      : "bg-green-50 border-green-300"
                }`}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold">{item.instrument_type}</div>
                    <div className="text-sm text-gray-600">
                      {item.grantor} → {item.grantee}
                    </div>
                    <div className="text-xs text-gray-500">{item.date}</div>
                    {item.status === "missing" && <div className="text-xs text-red-600 mt-2">Missing document</div>}
                    {item.status === "flagged" && <div className="text-xs text-yellow-600 mt-2">Requires review</div>}
                  </div>
                  <SourceBadge source={item.source} />
                </div>
              </div>
            ))}
          </div>

          {data!.gaps.length > 0 && (
            <div className="mt-8 p-4 bg-red-50 border border-red-300 rounded-lg">
              <h3 className="font-bold text-red-800 mb-3">Curative Needs</h3>
              <ul className="space-y-2">
                {data!.gaps.map((gap, idx) => (
                  <li key={idx} className="text-sm text-red-700">
                    • <span className="font-semibold">{gap.missing_document}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
