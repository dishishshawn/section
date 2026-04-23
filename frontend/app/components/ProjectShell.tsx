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
      return <ProjectDetail projectId={selected.id} projectName={selected.name} jurisdiction={selected.jurisdiction} onBack={() => setSelectedProjectId(null)} />;
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="bg-slate-900 text-white p-6">
        <h1 className="text-3xl font-bold">Section</h1>
        <p className="text-slate-400">Land Graph Operating Layer</p>
      </header>

      <div className="max-w-4xl mx-auto p-6">
        <form onSubmit={createProject} className="mb-8 p-4 bg-slate-50 rounded-lg">
          <h2 className="text-xl font-bold mb-4">New Project</h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <input
              type="text"
              placeholder="Project name"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              required
              className="p-2 border border-slate-300 rounded"
            />
            <select
              value={newProjectJurisdiction}
              onChange={(e) => setNewProjectJurisdiction(e.target.value)}
              className="p-2 border border-slate-300 rounded"
            >
              <option value="Oklahoma">Oklahoma</option>
              <option value="Texas">Texas</option>
              <option value="New Mexico">New Mexico</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {submitting ? "Creating..." : "Create Project"}
          </button>
        </form>

        {error && <div className="p-4 bg-red-50 text-red-700 rounded mb-4">{error}</div>}
        {success && <div className="p-4 bg-green-50 text-green-700 rounded mb-4">{success}</div>}

        {loading ? (
          <div className="text-center p-8">Loading projects...</div>
        ) : (
          <div>
            <h2 className="text-2xl font-bold mb-4">Projects</h2>
            {projects.length === 0 ? (
              <p className="text-slate-500">No projects yet. Create one above.</p>
            ) : (
              <div className="grid gap-4">
                {projects.map((project) => (
                  <div
                    key={project.id}
                    className="p-4 border border-slate-200 rounded-lg hover:bg-slate-50 flex justify-between items-start"
                  >
                    <div
                      onClick={() => setSelectedProjectId(project.id)}
                      className="flex-1 cursor-pointer"
                    >
                      <h3 className="font-bold text-lg">{project.name}</h3>
                      <p className="text-sm text-slate-600">{project.jurisdiction}</p>
                      <p className="text-xs text-slate-400">Created: {new Date(project.created_at).toLocaleDateString()}</p>
                    </div>
                    <button
                      onClick={() => deleteProject(project.id)}
                      disabled={deleting === project.id}
                      className="ml-4 px-3 py-1 text-sm bg-red-600 hover:bg-red-700 text-white rounded disabled:bg-gray-400"
                    >
                      {deleting === project.id ? "Deleting..." : "Delete"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
