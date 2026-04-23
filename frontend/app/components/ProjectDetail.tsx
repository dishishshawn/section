"use client";

import { useState } from "react";
import Runsheet from "./Runsheet";
import OwnershipView from "./OwnershipView";
import ObligationCalendar from "./ObligationCalendar";
import RiskDashboard from "./RiskDashboard";
import DocumentUpload from "./DocumentUpload";
import ExportButton from "./ExportButton";

type ViewType = "documents" | "runsheet" | "ownership" | "calendar" | "risk";

interface ProjectDetailProps {
  projectId: number;
  projectName: string;
  jurisdiction: string;
  onBack: () => void;
}

export default function ProjectDetail({ projectId, projectName, jurisdiction, onBack }: ProjectDetailProps) {
  const [currentView, setCurrentView] = useState<ViewType>("documents");

  const views: { id: ViewType; label: string }[] = [
    { id: "documents", label: "Documents" },
    { id: "runsheet", label: "Runsheet" },
    { id: "ownership", label: "Ownership" },
    { id: "calendar", label: "Obligations" },
    { id: "risk", label: "Risk Dashboard" },
  ];

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="bg-slate-900 text-white p-6 border-b border-slate-700">
        <button
          onClick={onBack}
          className="mb-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm"
        >
          ← Back to Projects
        </button>
        <h1 className="text-2xl font-bold">{projectName}</h1>
        <p className="text-slate-400">{jurisdiction} • Project ID: {projectId}</p>
      </header>

      {/* View Switcher & Actions */}
      <div className="bg-slate-100 border-b border-slate-300 p-4">
        <div className="flex gap-4 flex-wrap items-center justify-between">
          <div className="flex gap-4 flex-wrap">
            {views.map((view) => (
              <button
                key={view.id}
                onClick={() => setCurrentView(view.id)}
                className={`px-4 py-2 rounded font-semibold transition-colors ${
                  currentView === view.id
                    ? "bg-blue-600 text-white"
                    : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
                }`}
              >
                {view.label}
              </button>
            ))}
          </div>
          <ExportButton projectId={projectId} projectName={projectName} />
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto">
        {currentView === "documents" && <DocumentUpload projectId={projectId} />}
        {currentView === "runsheet" && <Runsheet projectId={projectId} />}
        {currentView === "ownership" && <OwnershipView projectId={projectId} />}
        {currentView === "calendar" && <ObligationCalendar projectId={projectId} />}
        {currentView === "risk" && <RiskDashboard projectId={projectId} />}
      </div>
    </div>
  );
}
