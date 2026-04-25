"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const EXPORTS = [
  { label: "Title opinion",     endpoint: "title-opinion",  filename: "Title_Opinion.pdf"    },
  { label: "Runsheet",          endpoint: "runsheet",       filename: "Runsheet.pdf"         },
  { label: "Ownership report",  endpoint: "ownership",      filename: "Ownership_Report.pdf" },
  { label: "Stipulations memo", endpoint: "stipulations",   filename: "Stipulations.pdf"     },
] as const;

export default function ExportButton({ projectId, projectName }: { projectId: number; projectName: string }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const download = async (endpoint: string, filename: string) => {
    setLoading(endpoint);
    setOpen(false);
    try {
      const res = await axios.get(
        `${API_URL}/projects/${projectId}/export/${endpoint}`,
        { responseType: "blob", withCredentials: true },
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${projectName}_${filename}`;
      document.body.appendChild(a);
      a.click();
      a.parentNode?.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={!!loading}
        className="inline-flex items-baseline gap-2 px-4 py-2 border border-rule text-ink text-[0.95rem] font-serif-italic hover:bg-ink hover:text-paper transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <span className="inline-block w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin not-italic" />
            Generating…
          </>
        ) : (
          <>
            Export
            <span className="text-xs not-italic" aria-hidden>{open ? "▲" : "▼"}</span>
          </>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 z-30 w-52 bg-surface border border-rule shadow-[0_8px_24px_-8px_rgba(29,38,53,0.2)]">
          <div className="border-b-[2px] border-rule" />
          <div className="border-b border-rule mt-[2px]" />
          <ul>
            {EXPORTS.map(({ label, endpoint, filename }) => (
              <li key={endpoint}>
                <button
                  onClick={() => download(endpoint, filename)}
                  className="w-full text-left px-4 py-3 text-sm font-serif-italic text-ink-2 hover:bg-surface-2 hover:text-ink transition-colors"
                >
                  {label}
                  <span className="float-right text-xs text-ink-3 not-italic">PDF ↓</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
