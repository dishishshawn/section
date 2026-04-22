"use client";

import { useState, useEffect } from "react";

interface Owner {
  name: string;
  fraction: string;
  percentage: number;
  mineral_estate: string;
}

interface OwnershipData {
  project_id: number;
  owners: Owner[];
  total_acres: number;
  leased_acres: number;
  open_acres: number;
}

export default function OwnershipView({ projectId }: { projectId: number }) {
  const [data, setData] = useState<OwnershipData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOwnership = async () => {
      try {
        setData({
          project_id: projectId,
          owners: [
            { name: "Compass Operating LLC", fraction: "1/2", percentage: 50, mineral_estate: "Surface & Minerals" },
            { name: "John Smith Trust", fraction: "1/4", percentage: 25, mineral_estate: "Minerals Only (ORRI 1/8)" },
            { name: "Unknown Heir #1", fraction: "1/8", percentage: 12.5, mineral_estate: "Minerals Only" },
            { name: "Unknown Heir #2", fraction: "1/8", percentage: 12.5, mineral_estate: "Minerals Only" },
          ],
          total_acres: 640,
          leased_acres: 480,
          open_acres: 160,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchOwnership();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading ownership data...</div>;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Ownership Position</h2>

      {/* Acreage Summary */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm text-gray-600">Total Acres</div>
          <div className="text-2xl font-bold">{data?.total_acres}</div>
        </div>
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="text-sm text-gray-600">Leased</div>
          <div className="text-2xl font-bold">{data?.leased_acres} ac</div>
        </div>
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="text-sm text-gray-600">Open</div>
          <div className="text-2xl font-bold">{data?.open_acres} ac</div>
        </div>
      </div>

      {/* Ownership Waterfall */}
      <h3 className="text-lg font-bold mb-4">Fractional Ownership</h3>
      <div className="space-y-2 mb-8">
        {data?.owners.map((owner, idx) => (
          <div key={idx} className="border rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="font-semibold">{owner.name}</div>
              <div className="text-sm text-gray-600">{owner.percentage}%</div>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className="bg-blue-500 h-4 rounded-full"
                style={{ width: `${owner.percentage}%` }}
              ></div>
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {owner.fraction} - {owner.mineral_estate}
            </div>
          </div>
        ))}
      </div>

      {/* Ownership Pie Chart (simplified) */}
      <h3 className="text-lg font-bold mb-4">Final Pie</h3>
      <div className="grid grid-cols-2 gap-4">
        {data?.owners.map((owner, idx) => (
          <div key={idx} className="text-sm p-2 bg-gray-50 border rounded">
            <div className="font-semibold">{owner.name}</div>
            <div className="text-gray-600">{owner.percentage}%</div>
          </div>
        ))}
      </div>
    </div>
  );
}
