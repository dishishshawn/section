"use client";

import { useState, useEffect, useRef } from "react";
import axios from "axios";

interface Document {
  id: number;
  s3_key: string;
  filename: string;
  mime: string;
  ocr_status: string;
  extraction_status: string;
  created_at: string | null;
}

interface UploadProgress {
  filename: string;
  status: "uploading" | "done" | "duplicate" | "error";
  error?: string;
}

interface DocumentUploadProps {
  projectId: number;
  onExtractionComplete?: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

const ACCEPTED_EXT = /\.(pdf|txt|jpe?g|png|tiff?)$/i;

const statusStyles: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  in_progress: "bg-blue-100 text-blue-700",
  complete: "bg-green-100 text-green-700",
  pending: "bg-slate-100 text-slate-700",
};

function statusLabel(status: string): string {
  if (!status) return "pending";
  if (status.startsWith("skipped")) return "Skipped";
  if (status.startsWith("failed")) return "No text";
  return status.replace(/_/g, " ");
}

function statusTitle(status: string): string {
  if (!status) return "";
  if (status.startsWith("skipped: unfilled form template"))
    return "This PDF is a blank form template - no data to extract. Upload an executed/filled copy.";
  if (status.startsWith("failed: no text extracted"))
    return "PDF has no text layer (likely scanned image). OCR required to process scanned documents.";
  if (status.startsWith("failed")) return status.replace(/^failed:\s*/, "");
  return "";
}

function statusClass(status: string): string {
  if (!status) return "bg-slate-100 text-slate-700";
  if (status.startsWith("skipped")) return "bg-amber-100 text-amber-800";
  if (status.startsWith("failed")) return "bg-red-100 text-red-700";
  return statusStyles[status] || "bg-slate-100 text-slate-700";
}

export default function DocumentUpload({ projectId, onExtractionComplete }: DocumentUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const filesInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchDocuments();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [projectId]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/projects/${projectId}/documents`);
      setDocuments(res.data);
      managePolling(res.data);
    } catch {
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  };

  const managePolling = (docs: Document[]) => {
    const hasPending = docs.some((d) => d.extraction_status === "queued" || d.extraction_status === "in_progress");
    if (hasPending && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await axios.get(`${API_URL}/projects/${projectId}/documents`);
          setDocuments(res.data);
          const stillPending = res.data.some(
            (d: Document) => d.extraction_status === "queued" || d.extraction_status === "in_progress"
          );
          if (!stillPending) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            onExtractionComplete?.();
          }
        } catch {}
      }, 2000);
    } else if (!hasPending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const uploadOne = async (file: File): Promise<{ ok: boolean; duplicate?: boolean; error?: string }> => {
    try {
      const formData = new FormData();
      const bareName = file.name.split(/[\\/]/).pop() || file.name;
      formData.append("file", file, bareName);
      const res = await axios.post(`${API_URL}/projects/${projectId}/documents`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return { ok: true, duplicate: res.data?.status === "duplicate" };
    } catch (err: any) {
      return { ok: false, error: err.response?.data?.detail || err.message || "Upload failed" };
    }
  };

  const uploadFiles = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList).filter((f) => ACCEPTED_EXT.test(f.name));
    if (files.length === 0) {
      setError("No supported files found (pdf, txt, jpg, png, tiff)");
      return;
    }

    setError(null);
    setUploading(true);
    setProgress(files.map((f) => ({ filename: f.name, status: "uploading" })));

    const CONCURRENCY = 3;
    let cursor = 0;
    const results: UploadProgress[] = files.map((f) => ({ filename: f.name, status: "uploading" }));

    await Promise.all(
      Array.from({ length: Math.min(CONCURRENCY, files.length) }).map(async () => {
        while (cursor < files.length) {
          const idx = cursor++;
          const file = files[idx];
          const result = await uploadOne(file);
          if (result.ok) {
            results[idx] = {
              filename: file.name,
              status: result.duplicate ? "duplicate" : "done",
            };
          } else {
            results[idx] = { filename: file.name, status: "error", error: result.error };
          }
          setProgress([...results]);
        }
      })
    );

    setUploading(false);
    await fetchDocuments();

    setTimeout(() => {
      const failed = results.some((r) => r.status === "error");
      if (!failed) setProgress([]);
    }, 3000);
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    await uploadFiles(files);
    e.target.value = "";
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const items = e.dataTransfer.items;

    if (items && items.length > 0 && typeof items[0].webkitGetAsEntry === "function") {
      const allFiles: File[] = [];
      const traverse = async (entry: any): Promise<void> => {
        if (entry.isFile) {
          await new Promise<void>((resolve) => {
            entry.file((f: File) => {
              allFiles.push(f);
              resolve();
            });
          });
        } else if (entry.isDirectory) {
          const reader = entry.createReader();
          const readAll = (): Promise<any[]> =>
            new Promise((resolve) => {
              reader.readEntries((entries: any[]) => {
                if (entries.length === 0) resolve([]);
                else readAll().then((rest) => resolve(entries.concat(rest)));
              });
            });
          const entries = await readAll();
          for (const child of entries) await traverse(child);
        }
      };

      const rootEntries: any[] = [];
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry();
        if (entry) rootEntries.push(entry);
      }
      for (const entry of rootEntries) await traverse(entry);

      if (allFiles.length > 0) {
        await uploadFiles(allFiles);
        return;
      }
    }

    await uploadFiles(e.dataTransfer.files);
  };

  const pendingCount = progress.filter((p) => p.status === "uploading").length;
  const errorCount = progress.filter((p) => p.status === "error").length;

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-6">Project Documents</h2>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`mb-6 p-8 border-2 border-dashed rounded-lg text-center transition-colors ${
          dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-white"
        }`}
      >
        <svg className="mx-auto w-10 h-10 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-slate-700 font-medium mb-1">
          Drop files or a folder here
        </p>
        <p className="text-xs text-slate-400 mb-4">PDF, TXT, or scanned images — multiple at once</p>
        <div className="flex gap-3 justify-center">
          <button
            type="button"
            onClick={() => filesInputRef.current?.click()}
            disabled={uploading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm disabled:bg-gray-400"
          >
            Select files
          </button>
          <button
            type="button"
            onClick={() => folderInputRef.current?.click()}
            disabled={uploading}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded text-sm disabled:bg-gray-400"
          >
            Select folder
          </button>
        </div>
        <input
          ref={filesInputRef}
          type="file"
          multiple
          onChange={handleFileInput}
          className="hidden"
          accept=".pdf,.txt,.jpg,.jpeg,.png,.tif,.tiff"
        />
        <input
          ref={folderInputRef}
          type="file"
          // @ts-expect-error webkitdirectory is non-standard
          webkitdirectory=""
          directory=""
          multiple
          onChange={handleFileInput}
          className="hidden"
        />
      </div>

      {progress.length > 0 && (
        <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-semibold text-sm">
              {pendingCount > 0
                ? `Uploading ${pendingCount} of ${progress.length}...`
                : errorCount > 0
                  ? `Finished with ${errorCount} error${errorCount === 1 ? "" : "s"}`
                  : "Upload complete"}
            </h3>
            {pendingCount === 0 && (
              <button
                onClick={() => setProgress([])}
                className="text-xs text-slate-500 hover:text-slate-700"
              >
                Dismiss
              </button>
            )}
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {progress.map((p, idx) => (
              <div key={idx} className="flex justify-between items-center text-xs">
                <span className="truncate flex-1 mr-2">{p.filename}</span>
                {p.status === "uploading" && <span className="text-blue-600">uploading...</span>}
                {p.status === "done" && <span className="text-green-600">done</span>}
                {p.status === "duplicate" && <span className="text-amber-600">already in project</span>}
                {p.status === "error" && <span className="text-red-600" title={p.error}>failed</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <div className="p-4 bg-red-50 text-red-700 rounded mb-4">{error}</div>}

      {loading && documents.length === 0 ? (
        <div className="text-center text-slate-500">Loading documents...</div>
      ) : documents.length === 0 ? (
        <div className="text-center text-slate-500 py-8">
          No documents uploaded yet. Start by uploading a lease or deed.
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => (
            <div key={doc.id} className="p-4 border border-slate-200 rounded-lg flex justify-between items-start">
              <div className="min-w-0 flex-1">
                <p className="font-semibold truncate">{doc.filename}</p>
                <p className="text-sm text-slate-600">{doc.mime || "unknown type"}</p>
              </div>
              <span
                title={statusTitle(doc.extraction_status)}
                className={`ml-4 px-2 py-1 text-xs rounded-full whitespace-nowrap ${statusClass(doc.extraction_status)}`}
              >
                {statusLabel(doc.extraction_status)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
