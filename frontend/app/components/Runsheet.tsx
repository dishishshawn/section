"use client";

import { useState, useEffect } from "react";

interface RunsheetData {
  project_id: number;
  chain: Array<{
    instrument_type: string;
    grantor: string;
    grantee: string;
    date: string;
    status: "complete" | "missing" | "flagged";
  }>;
  gaps: Array<{
    from: string;
    to: string;
    missing_document: string;
  }>;
}

export default function Runsheet({ projectId }: { projectId: number }) {
  const [data, setData] = useState<RunsheetData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRunsheet = async () => {
      try {
        setData({
          project_id: projectId,
          chain: [
            {
              instrument_type: "Warranty Deed",
              grantor: "John Smith Estate",
              grantee: "Compass Operating LLC",
              date: "2020-03-15",
              status: "complete",
            },
            {
              instrument_type: "Assignment",
              grantor: "Compass Operating LLC",
              grantee: "Unknown Assignee",
              date: "2021-06-01",
              status: "flagged",
            },
            {
              instrument_type: "Affidavit of Heirship",
              grantor: "John Smith Heirs",
              grantee: "John Smith Estate",
              date: "1999-01-01",
              status: "missing",
            },
          ],
          gaps: [
            {
              from: "John Smith Estate",
              to: "Unknown Assignee",
              missing_document: "Deed from John Smith estate to heirs - need affidavit of heirship",
            },
          ],
        });
      } finally {
        setLoading(false);
      }
    };

    fetchRunsheet();
  }, [projectId]);

  if (loading) return <div className="p-4">Loading runsheet...</div>;

  return (
    <div className="p-4">
      <h2 className="text-2xl font-bold mb-6">Chain of Title</h2>

      <div className="mb-8">
        <div className="space-y-2">
          {data?.chain.map((item, idx) => (
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
              <div className="font-semibold">{item.instrument_type}</div>
              <div className="text-sm text-gray-600">
                {item.grantor} → {item.grantee}
              </div>
              <div className="text-xs text-gray-500">{item.date}</div>
              {item.status === "missing" && <div className="text-xs text-red-600 mt-2">Missing document</div>}
              {item.status === "flagged" && <div className="text-xs text-yellow-600 mt-2">Requires review</div>}
            </div>
          ))}
        </div>
      </div>

      {data?.gaps && data.gaps.length > 0 && (
        <div className="mt-8 p-4 bg-red-50 border border-red-300 rounded-lg">
          <h3 className="font-bold text-red-800 mb-3">Curative Needs</h3>
          <ul className="space-y-2">
            {data.gaps.map((gap, idx) => (
              <li key={idx} className="text-sm text-red-700">
                • <span className="font-semibold">{gap.missing_document}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
