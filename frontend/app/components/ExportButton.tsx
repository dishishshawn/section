"use client";

import { useState } from "react";
import axios from "axios";

export default function ExportButton({ projectId, projectName }: { projectId: number; projectName: string }) {
  const [exporting, setExporting] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

  const handleExport = async () => {
    try {
      setExporting(true);
      const response = await axios.get(`${API_URL}/projects/${projectId}/export/ownership`, {
        responseType: "blob",
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `${projectName}_Ownership_Report.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      console.error("Export failed:", error);
    } finally {
      setExporting(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={exporting}
      className="group inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-ink text-white text-sm font-medium hover:bg-accent-strong transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {exporting ? (
        <>
          <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          Generating PDF
        </>
      ) : (
        <>
          <span className="font-mono text-xs uppercase tracking-wider text-zinc-300 group-hover:text-accent-soft transition-colors">
            PDF
          </span>
          <span className="w-px h-3 bg-zinc-600 group-hover:bg-accent/50 transition-colors" />
          Export report
        </>
      )}
    </button>
  );
}
