"use client";

import { useEffect, useState } from "react";
import Runsheet from "./Runsheet";
import type { SearchTarget } from "./GlobalSearch";
import OwnershipView from "./OwnershipView";
import ObligationCalendar from "./ObligationCalendar";
import RiskDashboard from "./RiskDashboard";
import DocumentUpload from "./DocumentUpload";
import ExportButton from "./ExportButton";
import AuditDrawer from "./AuditDrawer";
import TractMap from "./TractMap";
import ShareMenu from "./ShareMenu";

type ViewType = "documents" | "runsheet" | "ownership" | "map" | "calendar" | "risk";

interface ProjectDetailProps {
  projectId: number;
  projectName: string;
  jurisdiction: string;
  orgId: number | null;
  yourRole: string;
  searchTarget?: SearchTarget;
  onBack: () => void;
}

export default function ProjectDetail({ projectId, projectName, jurisdiction, orgId, yourRole, searchTarget, onBack }: ProjectDetailProps) {
  const [currentView, setCurrentView] = useState<ViewType>(searchTarget?.view ?? "documents");
  const [auditOpen, setAuditOpen] = useState(false);
  const [highlight, setHighlight] = useState<string | null>(searchTarget?.highlight ?? null);

  useEffect(() => {
    if (searchTarget) {
      setCurrentView(searchTarget.view);
      setHighlight(searchTarget.highlight);
    }
  }, [searchTarget]);

  const views: { id: ViewType; label: string }[] = [
    { id: "documents", label: "Documents" },
    { id: "runsheet", label: "Runsheet" },
    { id: "ownership", label: "Ownership" },
    { id: "map", label: "Tract map" },
    { id: "calendar", label: "Obligations" },
    { id: "risk", label: "Risk" },
  ];

  return (
    <div className="min-h-screen bg-paper">
      {/* Masthead — styled like the top of a county-clerk recorded document */}
      <header className="bg-paper-deep">
        <div className="max-w-6xl mx-auto px-10 pt-8 pb-10">
          <button
            onClick={onBack}
            className="group inline-flex items-center gap-2 text-sm text-ink-3 hover:text-ink transition-colors mb-8"
          >
            <span className="inline-block text-accent transition-transform group-hover:-translate-x-0.5">
              ←
            </span>
            <span className="font-serif-italic">All projects</span>
          </button>

          <div className="flex items-start gap-6">
            <span className="brand-mark" aria-hidden>§</span>
            <div className="flex-1 min-w-0">
              <div className="eyebrow mb-1.5">Project file</div>
              <h1 className="font-display text-[2.6rem] font-medium leading-[1.05] text-ink tracking-tight">
                {projectName}
              </h1>
              <div className="mt-3 flex items-center flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
                <span className="font-serif-italic">{jurisdiction}</span>
              </div>
            </div>
          </div>
        </div>
        {/* Legal-document double rule */}
        <div className="max-w-6xl mx-auto px-10">
          <div className="border-t-[2.5px] border-rule" />
          <div className="border-t border-rule mt-[3px]" />
        </div>
      </header>

      {/* Tab strip — no mono numerals, no all-caps, no tech tracking. Just a refined row. */}
      <div className="sticky top-0 z-10 bg-paper/95 backdrop-blur-sm border-b border-line-strong">
        <div className="max-w-6xl mx-auto px-10">
          <div className="flex items-center justify-between gap-4">
            <nav className="flex -mb-px" aria-label="Project sections">
              {views.map((view) => {
                const active = currentView === view.id;
                return (
                  <button
                    key={view.id}
                    onClick={() => {
                      setCurrentView(view.id);
                      setHighlight(null);
                    }}
                    className={`relative px-5 py-4 text-[0.95rem] transition-colors ${
                      active
                        ? "text-ink font-medium"
                        : "text-ink-3 hover:text-ink font-normal"
                    }`}
                  >
                    {view.label}
                    {active && (
                      <span className="absolute left-5 right-5 -bottom-px h-[2px] bg-accent" />
                    )}
                  </button>
                );
              })}
            </nav>
            <div className="flex-shrink-0 py-2.5 flex items-center gap-3">
              <button
                onClick={() => setAuditOpen(true)}
                className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors"
              >
                Audit trail
              </button>
              <ShareMenu projectId={projectId} orgId={orgId} yourRole={yourRole} />
              <ExportButton projectId={projectId} projectName={projectName} />
            </div>
          </div>
        </div>
      </div>

      <main className="max-w-6xl mx-auto">
        {currentView === "documents" && <DocumentUpload projectId={projectId} highlight={highlight} />}
        {currentView === "runsheet" && <Runsheet projectId={projectId} highlight={highlight} />}
        {currentView === "ownership" && <OwnershipView projectId={projectId} />}
        {currentView === "calendar" && <ObligationCalendar projectId={projectId} />}
        {currentView === "map" && <TractMap projectId={projectId} />}
        {currentView === "risk" && <RiskDashboard projectId={projectId} />}
      </main>

      <AuditDrawer
        projectId={projectId}
        open={auditOpen}
        onClose={() => setAuditOpen(false)}
      />
    </div>
  );
}
