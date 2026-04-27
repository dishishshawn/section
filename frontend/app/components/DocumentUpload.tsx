"use client";

import { useState, useEffect, useRef, Fragment } from "react";
import axios from "axios";
import EmptyState from "./EmptyState";

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
  highlight?: string | null;
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
  if (!status) return "text-ink-3";
  if (status.startsWith("skipped")) return "text-warn";
  if (status.startsWith("failed")) return "text-danger";
  if (status === "complete") return "text-positive";
  if (status === "in_progress") return "text-info";
  return "text-ink-3";
}

export default function DocumentUpload({ projectId, onExtractionComplete, highlight }: DocumentUploadProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const filesInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const docRefs = useRef<Record<number, HTMLLIElement | null>>({});
  const [flashId, setFlashId] = useState<number | null>(null);
  const [contribDoc, setContribDoc] = useState<Document | null>(null);
  const [contribData, setContribData] = useState<any | null>(null);
  const [contribLoading, setContribLoading] = useState(false);
  const [contribError, setContribError] = useState<string | null>(null);

  const openContributions = async (doc: Document) => {
    setContribDoc(doc);
    setContribData(null);
    setContribError(null);
    setContribLoading(true);
    try {
      const res = await axios.get(`${API_URL}/documents/${doc.id}/contributions`, {
        withCredentials: true,
      });
      setContribData(res.data);
    } catch (err: any) {
      setContribError(err.response?.data?.detail || err.message || "Failed to load contributions");
    } finally {
      setContribLoading(false);
    }
  };

  const closeContributions = () => {
    setContribDoc(null);
    setContribData(null);
    setContribError(null);
  };

  useEffect(() => {
    if (!highlight || documents.length === 0) return;
    const needle = highlight.toLowerCase();
    const match = documents.find((d) => d.filename.toLowerCase().includes(needle));
    if (!match) return;
    const el = docRefs.current[match.id];
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashId(match.id);
    const t = setTimeout(() => setFlashId(null), 2200);
    return () => clearTimeout(t);
  }, [highlight, documents]);

  useEffect(() => {
    fetchDocuments();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [projectId]);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_URL}/projects/${projectId}/documents`, { withCredentials: true });
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
          const res = await axios.get(`${API_URL}/projects/${projectId}/documents`, { withCredentials: true });
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

  const uploadOne = async (
    file: File,
    force: boolean = false,
  ): Promise<{ ok: boolean; duplicate?: boolean; error?: string }> => {
    try {
      const formData = new FormData();
      const bareName = file.name.split(/[\\/]/).pop() || file.name;
      formData.append("file", file, bareName);
      const url = `${API_URL}/projects/${projectId}/documents${force ? "?force=true" : ""}`;
      const res = await axios.post(url, formData, { withCredentials: true });
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
          let result = await uploadOne(file);
          if (result.ok && result.duplicate) {
            const replace = window.confirm(
              `"${file.name}" is already on file in this project. Re-upload and re-process it?`,
            );
            if (replace) {
              result = await uploadOne(file, true);
            }
          }
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
    <div className="px-10 py-12">
      <div className="mb-8">
        <div className="eyebrow mb-2">Section I</div>
        <h2 className="font-display text-[2.4rem] font-medium leading-none text-ink tracking-tight">
          Documents
        </h2>
        <p className="mt-3 font-serif-italic text-ink-2 text-[1.02rem] max-w-2xl">
          Drop recorded instruments here. Every upload is extracted, cited, and filed.
        </p>
      </div>

      {/* Drop zone — a proper "file drawer" feel */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        className={`relative mb-10 border-[1.5px] border-dashed px-10 py-14 text-center transition-all ${
          dragActive
            ? "border-accent bg-accent-tint"
            : "border-line-strong bg-surface-2 hover:bg-surface"
        }`}
      >
        <div className="relative">
          <p className="font-display text-2xl font-medium text-ink mb-1 leading-none">
            Drop files here
          </p>
          <p className="font-serif-italic text-ink-2 mb-6">
            or select from your computer — a folder works too
          </p>
          <div className="flex gap-3 justify-center">
            <button
              type="button"
              onClick={() => filesInputRef.current?.click()}
              disabled={uploading}
              className="px-5 py-2.5 bg-ink text-paper text-[0.95rem] font-medium hover:bg-accent transition-colors disabled:opacity-50"
            >
              Select files
            </button>
            <button
              type="button"
              onClick={() => folderInputRef.current?.click()}
              disabled={uploading}
              className="px-5 py-2.5 bg-surface border border-line-strong text-ink text-[0.95rem] font-medium hover:border-ink/40 hover:bg-surface-2 transition-colors disabled:opacity-50"
            >
              Select folder
            </button>
          </div>
          <p className="mt-6 text-xs text-ink-3 font-serif-italic">
            Accepts PDF, TXT, JPG, PNG, TIFF
          </p>
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
        <div className="mb-8 border-l-2 border-accent pl-5 py-2">
          <div className="flex justify-between items-baseline mb-2">
            <div>
              <div className="eyebrow">In progress</div>
              <div className="font-display text-lg text-ink mt-0.5">
                {pendingCount > 0
                  ? `Uploading ${pendingCount} of ${progress.length}…`
                  : errorCount > 0
                    ? `Finished with ${errorCount} error${errorCount === 1 ? "" : "s"}`
                    : "Upload complete"}
              </div>
            </div>
            {pendingCount === 0 && (
              <button
                onClick={() => setProgress([])}
                className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors"
              >
                dismiss
              </button>
            )}
          </div>
          <ul className="divide-y divide-line max-h-40 overflow-y-auto">
            {progress.map((p, idx) => (
              <li key={idx} className="flex justify-between items-center text-sm gap-3 py-1.5">
                <span className="truncate flex-1 text-ink-2 oldstyle">{p.filename}</span>
                {p.status === "uploading" && (
                  <span className="text-info font-serif-italic">uploading…</span>
                )}
                {p.status === "done" && (
                  <span className="text-positive font-serif-italic">filed</span>
                )}
                {p.status === "duplicate" && (
                  <span className="text-warn font-serif-italic">already on file</span>
                )}
                {p.status === "error" && (
                  <span className="text-rust font-serif-italic" title={p.error}>
                    failed
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="mb-6 border-l-2 border-rust bg-rust-soft/30 px-4 py-3">
          <span className="font-serif-italic text-rust mr-2">Error —</span>
          <span className="text-ink-2 text-sm">{error}</span>
        </div>
      )}

      <div className="flex items-baseline justify-between mb-4 pb-3 rule-hairline">
        <h3 className="font-display text-xl font-medium text-ink">
          Document library
        </h3>
        <span className="text-sm font-serif-italic text-ink-3 tabular">
          {documents.length} on file
        </span>
      </div>

      {loading && documents.length === 0 ? (
        <div className="px-6 py-12 text-center text-sm text-ink-3">
          <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin mr-2 align-middle" />
          <span className="font-serif-italic">Loading documents…</span>
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          title="No documents uploaded"
          description="Drop a deed or lease above — Section will OCR, extract, and cite every fact back to its source page."
        />
      ) : (
        <ul className="divide-y divide-line">
          {documents.map((doc) => (
            <li
              key={doc.id}
              ref={(el) => { docRefs.current[doc.id] = el; }}
              className={`py-4 flex justify-between items-center gap-4 -mx-4 px-4 transition-colors duration-700 ${
                flashId === doc.id ? "bg-accent-tint" : "hover:bg-surface-2"
              }`}
            >
              <div className="min-w-0 flex-1 flex items-baseline gap-4">
                <span className="flex-shrink-0 eyebrow text-[0.65rem] tabular">
                  {(doc.filename.split(".").pop() || "doc").toUpperCase().slice(0, 4)}
                </span>
                <div className="min-w-0">
                  <p className="font-display text-[1.05rem] text-ink truncate leading-tight">
                    {doc.filename}
                  </p>
                  <p className="text-xs text-ink-3 font-serif-italic mt-0.5">
                    {doc.mime || "unknown type"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4 whitespace-nowrap">
                {doc.extraction_status === "complete" && (
                  <button
                    onClick={() => openContributions(doc)}
                    className="text-sm font-serif-italic text-accent-strong hover:underline"
                  >
                    See contributions
                  </button>
                )}
                <span
                  title={statusTitle(doc.extraction_status)}
                  className={`font-serif-italic text-sm ${statusClass(doc.extraction_status)}`}
                >
                  {statusLabel(doc.extraction_status)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {contribDoc && (
        <div
          className="fixed inset-0 z-50 bg-ink/40 flex items-start justify-center p-6 overflow-y-auto"
          onClick={closeContributions}
        >
          <div
            className="bg-surface w-full max-w-3xl mt-12 mb-12 shadow-xl border border-line"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-7 py-5 border-b border-line flex items-baseline justify-between gap-4">
              <div className="min-w-0">
                <div className="eyebrow mb-1">Contributions</div>
                <h3 className="font-display text-xl text-ink truncate">{contribDoc.filename}</h3>
              </div>
              <button
                onClick={closeContributions}
                className="text-ink-3 hover:text-ink font-serif-italic text-sm"
              >
                close
              </button>
            </div>
            <div className="px-7 py-6">
              {contribLoading && (
                <div className="text-sm text-ink-3 font-serif-italic">Loading…</div>
              )}
              {contribError && (
                <div className="text-sm text-rust font-serif-italic">{contribError}</div>
              )}
              {contribData && !contribLoading && (
                <ContributionsView data={contribData} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ContributionsView({ data }: { data: any }) {
  const instruments: any[] = data.instruments || [];
  const obligations: any[] = data.obligations || [];

  if (instruments.length === 0 && obligations.length === 0) {
    return (
      <div className="text-sm text-ink-2 font-serif-italic">
        No structured data was extracted from this document.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {instruments.length > 0 && (
        <section>
          <div className="eyebrow mb-3">Instruments ({instruments.length})</div>
          <ul className="divide-y divide-line">
            {instruments.map((inst) => (
              <li key={inst.id} className="py-4">
                <div className="flex items-baseline justify-between gap-4 mb-2">
                  <span className="font-display text-base text-ink capitalize">
                    {inst.type || "instrument"}
                  </span>
                  {inst.recorded_at && (
                    <span className="text-xs text-ink-3 font-serif-italic">
                      recorded {inst.recorded_at.slice(0, 10)}
                    </span>
                  )}
                </div>
                <ExtractedFields fields={inst.extracted_data} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {obligations.length > 0 && (
        <section>
          <div className="eyebrow mb-3">Obligations ({obligations.length})</div>
          <ul className="divide-y divide-line">
            {obligations.map((ob) => (
              <li key={ob.id} className="py-3 flex justify-between items-baseline gap-4">
                <div>
                  <span className="font-display text-sm text-ink capitalize">
                    {(ob.type || "").replace(/_/g, " ")}
                  </span>
                  {ob.params && Object.keys(ob.params).length > 0 && (
                    <ExtractedFields fields={ob.params} compact />
                  )}
                </div>
                {ob.due_date && (
                  <span className="text-xs text-ink-3 font-serif-italic tabular">
                    due {ob.due_date.slice(0, 10)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function tryParseJsonObject(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function renderFieldValue(v: unknown): React.ReactNode {
  if (v === null || v === undefined) return null;

  const nested = tryParseJsonObject(v);
  if (nested) return <ExtractedFields fields={nested} compact />;

  if (Array.isArray(v)) {
    return (
      <ul className="list-disc pl-4 space-y-0.5">
        {v.map((item, i) => (
          <li key={i}>{renderFieldValue(item)}</li>
        ))}
      </ul>
    );
  }

  if (typeof v === "object") {
    return <ExtractedFields fields={v as Record<string, unknown>} compact />;
  }

  return String(v);
}

function tryParsePages(value: unknown): Record<string, unknown> | null {
  if (!value) return null;
  if (typeof value === "object" && !Array.isArray(value)) return value as Record<string, unknown>;
  return tryParseJsonObject(value);
}

function ExtractedFields({
  fields,
  compact = false,
  pages,
}: {
  fields: any;
  compact?: boolean;
  pages?: Record<string, unknown> | null;
}) {
  if (!fields || typeof fields !== "object") return null;

  // Pages may travel alongside quotes in the parent record. Pull them out
  // so we can annotate quote rows with their source page.
  const localPages = tryParsePages(fields.source_pages) ?? null;
  const childPages = pages ?? localPages;

  const isUsefulValue = (v: unknown): boolean => {
    if (v === null || v === undefined || v === "") return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === "object") {
      const inner = Object.values(v as Record<string, unknown>).filter(isUsefulValue);
      return inner.length > 0;
    }
    const nested = tryParseJsonObject(v);
    if (nested) {
      return Object.values(nested).filter(isUsefulValue).length > 0;
    }
    return true;
  };

  const entries = Object.entries(fields)
    .filter(([k]) => k !== "source_pages")
    .filter(([, v]) => isUsefulValue(v));

  if (entries.length === 0) {
    return <div className="text-xs text-ink-3 font-serif-italic">No fields extracted.</div>;
  }

  return (
    <dl className={`grid grid-cols-[max-content_1fr] gap-x-5 ${compact ? "gap-y-0.5 mt-1" : "gap-y-1.5"} text-sm`}>
      {entries.map(([k, v]) => {
        const nested = tryParseJsonObject(v);
        const isQuotesGroup = k === "source_quotes" && nested;
        const pageForKey = childPages && k in childPages ? childPages[k] : undefined;

        return (
          <Fragment key={k}>
            <dt className="text-ink-3 font-serif-italic capitalize self-start">
              {k.replace(/_/g, " ")}
              {pageForKey != null && pageForKey !== "" && (
                <span className="ml-1.5 text-ink-3/70 tabular text-xs">p. {String(pageForKey)}</span>
              )}
            </dt>
            <dd className="text-ink break-words">
              {isQuotesGroup ? (
                <ExtractedFields fields={nested!} compact pages={localPages} />
              ) : (
                renderFieldValue(v)
              )}
            </dd>
          </Fragment>
        );
      })}
    </dl>
  );
}
