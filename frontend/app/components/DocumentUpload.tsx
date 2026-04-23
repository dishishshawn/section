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
  if (!status) return "bg-line/40 text-ink-3";
  if (status.startsWith("skipped")) return "bg-warn-soft text-warn";
  if (status.startsWith("failed")) return "bg-danger-soft text-danger";
  if (status === "complete") return "bg-positive-soft text-positive";
  if (status === "in_progress") return "bg-info-soft text-info";
  return "bg-line/40 text-ink-3";
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
    <div className="px-8 py-10">
      <div className="mb-8">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-3 mb-1.5">
          01 — Documents
        </div>
        <h2 className="font-display text-3xl font-semibold text-ink">Project documents</h2>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`relative mb-6 rounded-xl border-2 border-dashed px-8 py-12 text-center transition-all overflow-hidden ${
          dragActive
            ? "border-accent bg-accent-tint scale-[1.005]"
            : "border-line-strong bg-surface hover:border-ink/30 hover:bg-surface-2"
        }`}
      >
        <div className="section-grid pointer-events-none absolute inset-0 opacity-30" />
        <div className="relative">
          <div className="mx-auto mb-4 inline-flex items-center justify-center w-12 h-12 rounded-xl bg-ink text-white">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>
          <p className="font-display text-lg font-semibold text-ink mb-1">
            Drop files or a folder
          </p>
          <p className="text-xs text-ink-3 mb-5 font-mono uppercase tracking-wider">
            PDF · TXT · JPG · PNG · TIFF
          </p>
          <div className="flex gap-2 justify-center">
            <button
              type="button"
              onClick={() => filesInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 rounded-lg bg-ink text-white text-sm font-medium hover:bg-accent-strong transition-colors disabled:opacity-50"
            >
              Select files
            </button>
            <button
              type="button"
              onClick={() => folderInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 rounded-lg bg-surface border border-line-strong text-ink text-sm font-medium hover:border-ink/40 hover:bg-surface-2 transition-colors disabled:opacity-50"
            >
              Select folder
            </button>
          </div>
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
        <div className="mb-6 rounded-xl border border-line bg-surface px-4 py-3">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-xs font-mono uppercase tracking-[0.16em] text-ink-2">
              {pendingCount > 0
                ? `Uploading ${pendingCount} of ${progress.length}…`
                : errorCount > 0
                  ? `Finished with ${errorCount} error${errorCount === 1 ? "" : "s"}`
                  : "Upload complete"}
            </h3>
            {pendingCount === 0 && (
              <button
                onClick={() => setProgress([])}
                className="text-xs text-ink-3 hover:text-ink transition-colors"
              >
                Dismiss
              </button>
            )}
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {progress.map((p, idx) => (
              <div key={idx} className="flex justify-between items-center text-xs gap-3 py-0.5">
                <span className="truncate flex-1 text-ink-2 font-mono">{p.filename}</span>
                {p.status === "uploading" && <span className="text-info">uploading…</span>}
                {p.status === "done" && <span className="text-positive">done</span>}
                {p.status === "duplicate" && <span className="text-warn">already in project</span>}
                {p.status === "error" && (
                  <span className="text-danger" title={p.error}>
                    failed
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3">
          <span className="text-danger font-mono text-xs mt-0.5">ERR</span>
          <span className="text-danger text-sm">{error}</span>
        </div>
      )}

      <div className="flex items-baseline justify-between mb-4">
        <h3 className="font-display text-sm font-semibold uppercase tracking-[0.18em] text-ink-3">
          Library
        </h3>
        <span className="text-xs text-ink-3 tabular">
          {documents.length} {documents.length === 1 ? "document" : "documents"}
        </span>
      </div>

      {loading && documents.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface px-6 py-12 text-center text-sm text-ink-3">
          <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
          Loading documents…
        </div>
      ) : documents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 px-6 py-12 text-center">
          <div className="font-display text-base text-ink mb-1">No documents yet</div>
          <p className="text-sm text-ink-3">Start by uploading a lease or deed.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="rounded-xl border border-line bg-surface px-4 py-3 flex justify-between items-center gap-4 hover:border-line-strong transition-colors"
            >
              <div className="min-w-0 flex-1 flex items-center gap-3">
                <span className="flex-shrink-0 w-8 h-8 rounded-md bg-paper border border-line flex items-center justify-center text-[0.6rem] font-mono uppercase text-ink-3">
                  {(doc.filename.split(".").pop() || "doc").slice(0, 4)}
                </span>
                <div className="min-w-0">
                  <p className="font-medium text-ink truncate">{doc.filename}</p>
                  <p className="text-xs text-ink-3 font-mono">{doc.mime || "unknown type"}</p>
                </div>
              </div>
              <span
                title={statusTitle(doc.extraction_status)}
                className={`px-2 py-1 text-[0.7rem] font-mono uppercase tracking-wider rounded-md whitespace-nowrap ${statusClass(doc.extraction_status)}`}
              >
                {statusLabel(doc.extraction_status)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
