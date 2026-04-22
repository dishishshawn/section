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
      className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
    >
      {exporting ? "Generating PDF..." : "📄 Export Report"}
    </button>
  );
}
