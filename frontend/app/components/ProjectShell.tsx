"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import ProjectDetail from "./ProjectDetail";

interface Project {
  id: number;
  name: string;
  jurisdiction: string;
  created_at: string;
}

export default function ProjectShell() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectJurisdiction, setNewProjectJurisdiction] = useState("Oklahoma");
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/projects`);
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
      const res = await axios.post(`${API_URL}/projects`, {
        name: newProjectName,
        jurisdiction: newProjectJurisdiction,
        owner_org: "Demo",
      });
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
      await axios.delete(`${API_URL}/projects/${projectId}`);
      setProjects(projects.filter((p) => p.id !== projectId));
      setError(null);
    } catch (err: any) {
      console.error("Delete error:", err);
      setError("Failed to delete project");
    } finally {
      setDeleting(null);
    }
  };

  if (selectedProjectId !== null) {
    const selected = projects.find((p) => p.id === selectedProjectId);
    if (selected) {
      return (
        <ProjectDetail
          projectId={selected.id}
          projectName={selected.name}
          jurisdiction={selected.jurisdiction}
          onBack={() => setSelectedProjectId(null)}
        />
      );
    }
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="relative overflow-hidden border-b border-line-strong bg-ink text-white">
        <div className="section-grid pointer-events-none absolute inset-0 opacity-40" />
        <div className="absolute inset-y-0 right-0 w-1/2 bg-gradient-to-l from-accent/20 via-transparent to-transparent pointer-events-none" />
        <div className="relative max-w-6xl mx-auto px-8 py-10">
          <div className="flex items-center gap-3 mb-6">
            <span className="brand-mark">S§</span>
            <span className="text-xs uppercase tracking-[0.2em] text-zinc-400 font-mono">
              Section / v0.1
            </span>
          </div>
          <h1 className="font-display text-5xl font-semibold leading-[1.05]">
            Land work,
            <span className="text-accent-soft"> structured.</span>
          </h1>
          <p className="mt-3 max-w-xl text-zinc-300 text-base leading-relaxed">
            Title chains, fractional ownership, obligations, and risk —
            extracted from raw documents into a single graph your team can act on.
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-8 py-10">
        <section className="mb-10">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink-3">
              Start a project
            </h2>
            <span className="text-xs text-ink-3">
              <kbd className="kbd">Enter</kbd> to create
            </span>
          </div>
          <form
            onSubmit={createProject}
            className="rounded-xl border border-line bg-surface shadow-[0_1px_0_rgba(24,24,27,0.04)] overflow-hidden"
          >
            <div className="grid md:grid-cols-[1fr_220px_auto] gap-px bg-line">
              <input
                type="text"
                placeholder="Garfield County 640 — STACK area"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                required
                className="px-4 py-4 bg-surface text-ink placeholder:text-ink-3 focus:outline-none focus:bg-accent-tint transition-colors"
              />
              <select
                value={newProjectJurisdiction}
                onChange={(e) => setNewProjectJurisdiction(e.target.value)}
                className="px-4 py-4 bg-surface text-ink focus:outline-none focus:bg-accent-tint transition-colors appearance-none"
              >
                <option value="Oklahoma">Oklahoma</option>
                <option value="Texas">Texas</option>
                <option value="New Mexico">New Mexico</option>
              </select>
              <button
                type="submit"
                disabled={submitting}
                className="px-6 py-4 bg-ink text-white font-medium hover:bg-accent-strong transition-colors disabled:bg-ink-3 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {submitting ? (
                  <>
                    <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Creating
                  </>
                ) : (
                  <>
                    Create project
                    <span aria-hidden>→</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </section>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3">
            <span className="text-danger font-mono text-xs mt-0.5">ERR</span>
            <span className="text-danger text-sm">{error}</span>
          </div>
        )}
        {success && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-positive/30 bg-positive-soft px-4 py-3">
            <span className="text-positive font-mono text-xs mt-0.5">OK</span>
            <span className="text-positive text-sm">{success}</span>
          </div>
        )}

        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink-3">
              Projects
            </h2>
            <span className="text-xs text-ink-3 tabular">
              {projects.length} {projects.length === 1 ? "project" : "projects"}
            </span>
          </div>

          {loading ? (
            <div className="rounded-xl border border-line bg-surface px-6 py-16 text-center text-ink-3 text-sm">
              <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
              Loading projects…
            </div>
          ) : projects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-16 text-center">
              <div className="font-display text-lg text-ink mb-1">No projects yet</div>
              <p className="text-sm text-ink-3">
                Create your first project above to start ingesting documents.
              </p>
            </div>
          ) : (
            <ul className="grid gap-3">
              {projects.map((project) => (
                <li
                  key={project.id}
                  className="group relative rounded-xl border border-line bg-surface hover:border-ink/20 hover:shadow-[0_4px_16px_rgba(24,24,27,0.06)] transition-all"
                >
                  <button
                    onClick={() => setSelectedProjectId(project.id)}
                    className="w-full text-left px-5 py-4 flex items-center gap-5"
                  >
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-accent-tint border border-accent/20 flex items-center justify-center text-accent-strong font-mono text-xs font-semibold tabular">
                      #{project.id}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-display text-lg font-semibold text-ink truncate group-hover:text-accent-strong transition-colors">
                        {project.name}
                      </div>
                      <div className="mt-1 flex items-center gap-3 text-xs text-ink-3">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                          {project.jurisdiction}
                        </span>
                        <span className="text-line-strong">·</span>
                        <span className="tabular">
                          {new Date(project.created_at).toLocaleDateString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          })}
                        </span>
                      </div>
                    </div>
                    <span className="text-ink-3 group-hover:text-accent group-hover:translate-x-0.5 transition-all" aria-hidden>
                      →
                    </span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteProject(project.id);
                    }}
                    disabled={deleting === project.id}
                    className="absolute top-3 right-12 opacity-0 group-hover:opacity-100 px-2 py-1 text-xs text-ink-3 hover:text-danger transition-all disabled:opacity-50"
                    title="Delete project"
                  >
                    {deleting === project.id ? "Deleting…" : "Delete"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>

      <footer className="max-w-6xl mx-auto px-8 py-10 mt-10 border-t border-line">
        <div className="flex items-center justify-between text-xs text-ink-3 font-mono">
          <span>Section · land graph operating layer</span>
          <span>Built for land teams who ship.</span>
        </div>
      </footer>
    </div>
  );
}
