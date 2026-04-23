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

  const views: { id: ViewType; label: string; hint: string }[] = [
    { id: "documents", label: "Documents", hint: "01" },
    { id: "runsheet", label: "Runsheet", hint: "02" },
    { id: "ownership", label: "Ownership", hint: "03" },
    { id: "calendar", label: "Obligations", hint: "04" },
    { id: "risk", label: "Risk", hint: "05" },
  ];

  return (
    <div className="min-h-screen bg-paper">
      <header className="relative overflow-hidden border-b border-line-strong bg-ink text-white">
        <div className="section-grid pointer-events-none absolute inset-0 opacity-30" />
        <div className="relative max-w-6xl mx-auto px-8 py-7">
          <button
            onClick={onBack}
            className="group inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.16em] text-zinc-400 hover:text-white transition-colors mb-5"
          >
            <span className="inline-block transition-transform group-hover:-translate-x-0.5">←</span>
            All projects
          </button>
          <div className="flex items-start gap-4">
            <span className="brand-mark mt-1.5">S§</span>
            <div className="flex-1 min-w-0">
              <h1 className="font-display text-3xl font-semibold leading-tight truncate">
                {projectName}
              </h1>
              <div className="mt-2 flex items-center gap-3 text-xs text-zinc-400 font-mono">
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  {jurisdiction}
                </span>
                <span className="text-zinc-600">·</span>
                <span className="tabular">PROJECT-{String(projectId).padStart(4, "0")}</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="sticky top-0 z-10 border-b border-line bg-paper/85 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-8">
          <div className="flex items-center justify-between gap-4">
            <nav className="flex -mb-px overflow-x-auto" aria-label="Project sections">
              {views.map((view) => {
                const active = currentView === view.id;
                return (
                  <button
                    key={view.id}
                    onClick={() => setCurrentView(view.id)}
                    className={`group relative px-4 py-4 flex items-center gap-2 text-sm font-medium whitespace-nowrap transition-colors ${
                      active ? "text-ink" : "text-ink-3 hover:text-ink"
                    }`}
                  >
                    <span
                      className={`font-mono text-[0.65rem] tabular ${
                        active ? "text-accent" : "text-ink-3 group-hover:text-ink-2"
                      }`}
                    >
                      {view.hint}
                    </span>
                    {view.label}
                    {active && (
                      <span className="absolute left-3 right-3 -bottom-px h-0.5 bg-accent rounded-full" />
                    )}
                  </button>
                );
              })}
            </nav>
            <div className="flex-shrink-0 py-2.5">
              <ExportButton projectId={projectId} projectName={projectName} />
            </div>
          </div>
        </div>
      </div>

      <main className="max-w-6xl mx-auto">
        {currentView === "documents" && <DocumentUpload projectId={projectId} />}
        {currentView === "runsheet" && <Runsheet projectId={projectId} />}
        {currentView === "ownership" && <OwnershipView projectId={projectId} />}
        {currentView === "calendar" && <ObligationCalendar projectId={projectId} />}
        {currentView === "risk" && <RiskDashboard projectId={projectId} />}
      </main>
    </div>
  );
}
