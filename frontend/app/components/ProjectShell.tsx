"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import ProjectDetail from "./ProjectDetail";
import GlobalSearch from "./GlobalSearch";
import OrgSwitcher from "./OrgSwitcher";
import MembersPage from "./MembersPage";
import EmptyState from "./EmptyState";

interface Project {
  id: number;
  name: string;
  jurisdiction: string;
  created_at: string;
  your_role?: "owner" | "editor" | "viewer" | null;
}

interface Org {
  id: number;
  name: string;
  slug: string;
  billing_status: string | null;
  your_role: string | null;
}

interface Me {
  id: number;
  email: string;
  display_name: string | null;
}

interface ProjectShellProps {
  me: Me;
  onSignOut: () => void;
}

export default function ProjectShell({ me, onSignOut }: ProjectShellProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectJurisdiction, setNewProjectJurisdiction] = useState("Oklahoma");
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [currentOrg, setCurrentOrg] = useState<Org | null>(null);
  const [showMembers, setShowMembers] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  // Re-fetch whenever the active org changes
  useEffect(() => {
    fetchProjects();
  }, [currentOrg]);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/projects`, { withCredentials: true });
      setProjects(res.data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to fetch projects");
    } finally {
      setLoading(false);
    }
  };

  const createProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await axios.post(
        `${API_URL}/projects`,
        {
          name: newProjectName,
          jurisdiction: newProjectJurisdiction,
          org_id: currentOrg?.id ?? null,
        },
        { withCredentials: true }
      );
      setProjects([...projects, res.data]);
      setNewProjectName("");
      setError(null);
      setSelectedProjectId(res.data.id);
    } catch (err: any) {
      console.error("Create project error:", err);
      setError(err.response?.data?.detail || err.message || "Failed to create project");
      setSubmitting(false);
    }
  };

  const deleteProject = async (projectId: number) => {
    if (!confirm("Delete this project? This cannot be undone.")) return;
    setDeleting(projectId);
    try {
      await axios.delete(`${API_URL}/projects/${projectId}`, { withCredentials: true });
      setProjects(projects.filter((p) => p.id !== projectId));
      setError(null);
    } catch (err: any) {
      console.error("Delete error:", err);
      setError("Failed to delete project");
    } finally {
      setDeleting(null);
    }
  };

  // TODO: wire to POST /api/demo/seed-sample once the backend endpoint ships.
  // For now this is a UI stub — surfaces a message so the user understands
  // the feature is coming without creating a broken request.
  const seedSampleDeed = () => {
    setError(null);
    setSuccess(
      "Sample deed seeding is coming soon — the backend endpoint (POST /api/demo/seed-sample) is not yet wired up."
    );
  };

  const handleSignOut = async () => {
    try {
      await axios.post(`${API_URL}/auth/signout`, {}, { withCredentials: true });
    } finally {
      onSignOut();
    }
  };

  // Route: members page
  if (showMembers && currentOrg) {
    return (
      <MembersPage
        orgId={currentOrg.id}
        orgName={currentOrg.name}
        yourRole={currentOrg.your_role || "member"}
        onClose={() => setShowMembers(false)}
      />
    );
  }

  // Route: project detail
  if (selectedProjectId !== null) {
    const selected = projects.find((p) => p.id === selectedProjectId);
    if (selected) {
      return (
        <ProjectDetail
          projectId={selected.id}
          projectName={selected.name}
          jurisdiction={selected.jurisdiction}
          orgId={currentOrg?.id ?? null}
          yourRole={selected.your_role ?? "viewer"}
          onBack={() => setSelectedProjectId(null)}
        />
      );
    }
  }

  const today = new Date().toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="min-h-screen bg-paper">
      {/* Masthead */}
      <header className="bg-paper-deep border-b-[2.5px] border-rule">
        <div className="max-w-6xl mx-auto px-10 pt-10 pb-12">
          {/* Dateline / toolbar */}
          <div className="flex items-center justify-between mb-6 pb-3 rule-hairline gap-4">
            <div className="eyebrow">Section &middot; Land graph</div>
            <div className="flex items-center gap-3">
              {/* Org switcher */}
              <OrgSwitcher
                currentOrgId={currentOrg?.id ?? null}
                onOrgChange={(org) => setCurrentOrg(org)}
              />
              {/* Members link (only when in an org) */}
              {currentOrg && (currentOrg.your_role === "owner" || currentOrg.your_role === "admin") && (
                <button
                  onClick={() => setShowMembers(true)}
                  className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors"
                >
                  Members
                </button>
              )}
              <span className="text-line-strong text-sm">·</span>
              <span className="text-sm font-serif-italic text-ink-3 tabular">{today}</span>
              <span className="text-line-strong text-sm">·</span>
              <button
                onClick={handleSignOut}
                className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors"
              >
                Sign out
              </button>
            </div>
          </div>

          <div className="flex items-start justify-between gap-8">
            <div className="flex items-baseline gap-5">
              <span className="brand-mark" aria-hidden>§</span>
              <div>
                <h1 className="font-display text-6xl font-medium leading-[0.95] text-ink tracking-tight">
                  Section
                </h1>
                <p className="mt-2 font-serif-italic text-lg text-ink-2">
                  The operating record for upstream land work.
                </p>
              </div>
            </div>
          </div>

          <p className="mt-8 max-w-2xl text-[1.05rem] leading-[1.55] text-ink-2 oldstyle">
            Title chains, fractional ownership, obligations, and risk &mdash;
            extracted from your recorded documents into a single structured
            record. Every fact cites the page it came from.
          </p>

          <div className="mt-8">
            <GlobalSearch onOpenProject={(id) => setSelectedProjectId(id)} />
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-10 py-12">
        {/* New project form */}
        <section className="mb-12">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="font-display text-2xl font-medium text-ink">Open a new file</h2>
            <span className="text-xs font-serif-italic text-ink-3">
              {currentOrg ? `In ${currentOrg.name}` : "Personal workspace"}
            </span>
          </div>

          <form onSubmit={createProject}>
            <div className="rounded-sm border border-line-strong bg-surface overflow-hidden">
              <div className="grid md:grid-cols-[1fr_220px_auto] divide-x divide-line-strong">
                <input
                  type="text"
                  placeholder="e.g. Garfield County 640 — STACK area"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  required
                  className="px-5 py-4 bg-surface text-ink placeholder:text-ink-3 placeholder:font-serif-italic focus:outline-none focus:bg-accent-tint transition-colors text-[1rem]"
                />
                <select
                  value={newProjectJurisdiction}
                  onChange={(e) => setNewProjectJurisdiction(e.target.value)}
                  className="px-5 py-4 bg-surface text-ink focus:outline-none focus:bg-accent-tint transition-colors text-[0.95rem]"
                >
                  <option value="Oklahoma">Oklahoma</option>
                  <option value="Texas">Texas</option>
                  <option value="New Mexico">New Mexico</option>
                </select>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-7 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors disabled:bg-ink-3 disabled:cursor-not-allowed flex items-center gap-2.5"
                >
                  {submitting ? (
                    <>
                      <span className="inline-block w-3 h-3 border-2 border-paper/30 border-t-paper rounded-full animate-spin" />
                      <span>Creating</span>
                    </>
                  ) : (
                    <>
                      <span>Open file</span>
                      <span aria-hidden>→</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        </section>

        {error && (
          <div className="mb-6 flex items-start gap-3 border-l-2 border-rust bg-rust-soft/40 px-4 py-3">
            <span className="font-serif-italic text-rust mt-0.5">Error —</span>
            <span className="text-ink-2 text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 flex items-start gap-3 border-l-2 border-moss bg-moss-soft/40 px-4 py-3">
            <span className="font-serif-italic text-moss mt-0.5">Note —</span>
            <span className="text-ink-2 text-sm flex-1">{success}</span>
            <button
              onClick={() => setSuccess(null)}
              className="text-ink-3 hover:text-ink text-sm"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        )}

        {/* Project register */}
        <section>
          <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
            <h2 className="font-display text-2xl font-medium text-ink">Project register</h2>
            <span className="text-sm font-serif-italic text-ink-3 tabular">
              {projects.length} on file
            </span>
          </div>

          {loading ? (
            <div className="px-6 py-16 text-center text-ink-3 text-sm">
              <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
              <span className="font-serif-italic">Loading projects…</span>
            </div>
          ) : projects.length === 0 ? (
            <EmptyState
              title="No projects yet"
              description="Open your first file above to start ingesting documents, or seed a sample deed to explore a worked example."
              primaryAction={{
                label: "Create your first project",
                onClick: () => {
                  // focus the project-name input at the top of the form
                  const el = document.querySelector<HTMLInputElement>(
                    'input[placeholder^="e.g."]'
                  );
                  el?.focus();
                  el?.scrollIntoView({ behavior: "smooth", block: "center" });
                },
              }}
              secondaryAction={{
                label: "Try with sample deed",
                onClick: seedSampleDeed,
              }}
            />
          ) : (
            <ul className="divide-y divide-line">
              {projects.map((project, idx) => (
                <li
                  key={project.id}
                  className="group relative bg-transparent hover:bg-surface-2 transition-colors"
                >
                  <button
                    onClick={() => setSelectedProjectId(project.id)}
                    className="w-full text-left px-4 py-5 flex items-center gap-6"
                  >
                    <div className="flex-shrink-0 w-14 text-right">
                      <div className="font-numeric text-[1.35rem] text-ink-3 leading-none">
                        {String(idx + 1).padStart(2, "0")}
                      </div>
                      <div className="eyebrow mt-0.5 text-[0.65rem]">Folio</div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-display text-[1.3rem] font-medium text-ink leading-tight group-hover:text-accent-strong transition-colors truncate">
                        {project.name}
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-sm">
                        <span className="font-serif-italic text-ink-2">{project.jurisdiction}</span>
                        <span className="text-line-strong">·</span>
                        <span className="tabular text-ink-3">
                          Filed{" "}
                          {new Date(project.created_at).toLocaleDateString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                    <span
                      className="text-ink-3 group-hover:text-accent group-hover:translate-x-0.5 transition-all text-xl"
                      aria-hidden
                    >
                      →
                    </span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteProject(project.id);
                    }}
                    disabled={deleting === project.id}
                    className="absolute top-1/2 right-12 -translate-y-1/2 opacity-0 group-hover:opacity-100 px-2 py-1 text-xs text-ink-3 hover:text-rust font-serif-italic transition-all disabled:opacity-50"
                    title="Delete project"
                  >
                    {deleting === project.id ? "removing…" : "remove"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <footer className="max-w-6xl mx-auto px-10 py-10 mt-6">
        <div className="border-t border-line pt-5 flex items-baseline justify-between text-sm text-ink-3">
          <span className="font-serif-italic">
            Section &middot; the operating record for land work
          </span>
          <span className="tabular text-xs">
            {me.display_name || me.email}
          </span>
        </div>
      </footer>
    </div>
  );
}
