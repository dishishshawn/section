"use client";

import { useEffect, useRef, useState } from "react";
import axios from "axios";

interface SearchResults {
  projects: { id: number; name: string; jurisdiction: string }[];
  documents: { id: number; filename: string; project_id: number; project_name: string }[];
  parties: { name: string; project_id: number; project_name: string }[];
  tracts: { legal_description: string; project_id: number; project_name: string }[];
}

const EMPTY: SearchResults = { projects: [], documents: [], parties: [], tracts: [] };

export type SearchTarget =
  | { view: "runsheet"; highlight: string }
  | { view: "documents"; highlight: string }
  | { view: "map"; highlight: string }
  | null;

export default function GlobalSearch({
  onOpenProject,
}: {
  onOpenProject: (projectId: number, target?: SearchTarget) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults>(EMPTY);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setResults(EMPTY);
      setErrorMsg(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const res = await axios.get(`${API_URL}/search`, { params: { q: term } });
        setResults(res.data.results || EMPTY);
        setErrorMsg(null);
      } catch (err: any) {
        setResults(EMPTY);
        const status = err?.response?.status;
        if (status === 404) {
          setErrorMsg("Search endpoint not found. Restart the backend server to pick up the new /api/search route.");
        } else if (status) {
          setErrorMsg(`Search failed (HTTP ${status}).`);
        } else {
          setErrorMsg("Can't reach the API. Is the backend running?");
        }
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(handle);
  }, [query, API_URL]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const total =
    results.projects.length +
    results.documents.length +
    results.parties.length +
    results.tracts.length;

  const pick = (projectId: number, target?: SearchTarget) => {
    setOpen(false);
    setQuery("");
    onOpenProject(projectId, target ?? null);
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="flex items-center gap-3 border border-line-strong bg-surface px-4 py-2.5 rounded-sm">
        <span aria-hidden className="text-ink-3 font-serif-italic text-sm">Search</span>
        <span className="text-line-strong">·</span>
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="project, party, tract, document…"
          className="flex-1 bg-transparent text-ink placeholder:text-ink-3 placeholder:font-serif-italic focus:outline-none text-[0.95rem]"
        />
        {loading && (
          <span className="inline-block w-3 h-3 border-2 border-line-strong border-t-ink rounded-full animate-spin" />
        )}
      </div>

      {open && query.trim().length >= 2 && (
        <div className="absolute left-0 right-0 mt-2 z-20 bg-surface border border-line-strong rounded-sm shadow-md max-h-[70vh] overflow-auto">
          {errorMsg && !loading && (
            <div className="px-4 py-4 text-sm border-l-2 border-rust bg-rust-soft/40 text-ink-2">
              <span className="font-serif-italic text-rust">Search error —</span> {errorMsg}
            </div>
          )}
          {!errorMsg && total === 0 && !loading && (
            <div className="px-4 py-4 text-sm font-serif-italic text-ink-3">
              No records match &ldquo;{query}&rdquo;.
            </div>
          )}

          {results.projects.length > 0 && (
            <ResultGroup label="Projects">
              {results.projects.map((p) => (
                <ResultRow
                  key={`proj-${p.id}`}
                  onClick={() => pick(p.id)}
                  primary={p.name}
                  secondary={p.jurisdiction}
                />
              ))}
            </ResultGroup>
          )}

          {results.parties.length > 0 && (
            <ResultGroup label="Parties">
              {results.parties.map((p, i) => (
                <ResultRow
                  key={`party-${p.project_id}-${i}`}
                  onClick={() => pick(p.project_id, { view: "runsheet", highlight: p.name })}
                  primary={p.name}
                  secondary={p.project_name}
                />
              ))}
            </ResultGroup>
          )}

          {results.tracts.length > 0 && (
            <ResultGroup label="Tracts">
              {results.tracts.map((t, i) => (
                <ResultRow
                  key={`tract-${t.project_id}-${i}`}
                  onClick={() => pick(t.project_id, { view: "map", highlight: t.legal_description })}
                  primary={t.legal_description}
                  secondary={t.project_name}
                />
              ))}
            </ResultGroup>
          )}

          {results.documents.length > 0 && (
            <ResultGroup label="Documents">
              {results.documents.map((d) => (
                <ResultRow
                  key={`doc-${d.id}`}
                  onClick={() => pick(d.project_id, { view: "documents", highlight: d.filename })}
                  primary={d.filename}
                  secondary={d.project_name}
                />
              ))}
            </ResultGroup>
          )}
        </div>
      )}
    </div>
  );
}

function ResultGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-line last:border-b-0">
      <div className="eyebrow px-4 pt-3 pb-1.5">{label}</div>
      <ul>{children}</ul>
    </div>
  );
}

function ResultRow({
  primary,
  secondary,
  onClick,
}: {
  primary: string;
  secondary: string;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="w-full text-left px-4 py-2.5 hover:bg-accent-tint transition-colors flex items-baseline justify-between gap-4"
      >
        <span className="text-ink text-[0.95rem] font-medium truncate">{primary}</span>
        <span className="font-serif-italic text-ink-3 text-xs truncate flex-shrink-0">
          {secondary}
        </span>
      </button>
    </li>
  );
}
