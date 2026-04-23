"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import SourceBadge, { SourceRef } from "./SourceBadge";

interface Owner {
  name: string;
  fraction: string;
  percentage: number;
  mineral_estate: string;
  source: SourceRef | null;
}

interface OwnershipData {
  project_id: number;
  owners: Owner[];
  total_acres: number;
  leased_acres: number;
  open_acres: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function OwnershipView({ projectId }: { projectId: number }) {
  const [data, setData] = useState<OwnershipData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOwnership = async () => {
      try {
        setLoading(true);
        const res = await axios.get(`${API_URL}/projects/${projectId}/ownership`);
        setData(res.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || "Failed to load ownership data");
      } finally {
        setLoading(false);
      }
    };
    fetchOwnership();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading ownership data...</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  const isEmpty = !data?.owners?.length;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Ownership Position</h2>

      {isEmpty ? (
        <div className="p-8 text-center border-2 border-dashed border-slate-300 rounded-lg">
          <p className="text-slate-500 mb-2">No ownership data yet.</p>
          <p className="text-sm text-slate-400">
            Upload deeds in the Documents tab to establish fractional ownership.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="text-sm text-gray-600">Total Acres</div>
              <div className="text-2xl font-bold">{data!.total_acres}</div>
            </div>
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="text-sm text-gray-600">Leased</div>
              <div className="text-2xl font-bold">{data!.leased_acres} ac</div>
            </div>
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="text-sm text-gray-600">Open</div>
              <div className="text-2xl font-bold">{data!.open_acres} ac</div>
            </div>
          </div>

          <h3 className="text-lg font-bold mb-4">Fractional Ownership</h3>
          <div className="space-y-2 mb-8">
            {data!.owners.map((owner, idx) => (
              <div key={idx} className="border rounded-lg p-3">
                <div className="flex items-center justify-between mb-2 gap-4">
                  <div className="font-semibold min-w-0 flex-1 truncate">{owner.name}</div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-sm text-gray-600">{owner.percentage}%</span>
                    <SourceBadge source={owner.source} />
                  </div>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-blue-500 h-4 rounded-full"
                    style={{ width: `${Math.min(owner.percentage, 100)}%` }}
                  ></div>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {owner.fraction} - {owner.mineral_estate}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
