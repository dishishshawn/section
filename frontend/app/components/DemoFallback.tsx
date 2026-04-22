"use client";

import Image from "next/image";

export default function DemoFallback() {
  const fallbackData = {
    project_name: "Garfield County 640 - STACK Area",
    jurisdiction: "Oklahoma",
    runsheet_status: "Complete with 2 flagged gaps",
    owners_count: 4,
    obligations_count: 3,
  };

  return (
    <div className="min-h-screen bg-white">
      <header className="bg-slate-900 text-white p-6 border-b border-slate-700">
        <h1 className="text-2xl font-bold">{fallbackData.project_name}</h1>
        <p className="text-slate-400">{fallbackData.jurisdiction} • Demo Project</p>
      </header>

      <div className="max-w-6xl mx-auto p-6">
        <div className="bg-blue-50 border border-blue-300 rounded-lg p-6 mb-8">
          <h2 className="text-lg font-bold text-blue-900 mb-2">📋 Demo Fallback Mode</h2>
          <p className="text-blue-800 text-sm">
            Live database unavailable. Showing pre-rendered demo state. In production, this would be the live Garfield County project.
          </p>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-center">
            <div className="text-3xl font-bold text-blue-600">640</div>
            <div className="text-sm text-gray-600">Gross Acres</div>
          </div>
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-center">
            <div className="text-3xl font-bold text-green-600">4</div>
            <div className="text-sm text-gray-600">Owners</div>
          </div>
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg text-center">
            <div className="text-3xl font-bold text-orange-600">2</div>
            <div className="text-sm text-gray-600">Flagged Gaps</div>
          </div>
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-center">
            <div className="text-3xl font-bold text-red-600">3</div>
            <div className="text-sm text-gray-600">At-Risk Obligations</div>
          </div>
        </div>

        <div className="border-t border-gray-300 pt-8">
          <h3 className="text-xl font-bold mb-6">Demo Feature Overview</h3>

          <div className="grid grid-cols-2 gap-6">
            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ Runsheet View</h4>
              <p className="text-sm text-gray-600">
                Chain of title: Warranty Deed (complete) → Assignment (flagged) → Missing heirship affidavit
              </p>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ Ownership Calculator</h4>
              <p className="text-sm text-gray-600">
                Compass (50%) + Smith Estate (25%) + 2 Unknown Heirs (12.5% each)
              </p>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ Obligation Calendar</h4>
              <p className="text-sm text-gray-600">
                Rental due in 15d, Drilling deadline in 45d, Primary term expires in 90d
              </p>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ Risk Dashboard</h4>
              <p className="text-sm text-gray-600">
                Title defects (critical) + expiring leases (high) + ORRI burdens (medium)
              </p>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ PDF Export</h4>
              <p className="text-sm text-gray-600">
                Ownership report rendered in Compass template. Auto-populated fields.
              </p>
            </div>

            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="font-bold mb-2">✅ Multi-Document Ingestion</h4>
              <p className="text-sm text-gray-600">
                Drag-drop up to 40 documents. Claude extracts all structured data.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-8 p-6 bg-green-50 border border-green-300 rounded-lg">
          <h3 className="font-bold text-green-900 mb-2">💡 What This Demo Shows</h3>
          <ul className="text-sm text-green-800 space-y-2">
            <li>• AI-powered document extraction (lease/deed fields)</li>
            <li>• Structured land graph model persisted in Postgres</li>
            <li>• Real-time ownership calculations across instrument chains</li>
            <li>• Obligation tracking with smart deadline alerts</li>
            <li>• Risk scoring and portfolio-level insights</li>
            <li>• Template-driven PDF exports matching Compass deliverables</li>
            <li>• Project-scoped workspace (no data evaporation)</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
