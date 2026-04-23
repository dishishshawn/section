"use client";

import { useState } from "react";

export interface SourceRef {
  document_id: number;
  filename: string;
  quote: string | null;
}

interface SourceBadgeProps {
  source: SourceRef | null | undefined;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function SourceBadge({ source }: SourceBadgeProps) {
  const [open, setOpen] = useState(false);

  if (!source) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-400">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        no source
      </span>
    );
  }

  const fileUrl = `${API_URL}/documents/${source.document_id}/file`;
  const shortName = source.filename.length > 35
    ? source.filename.slice(0, 32) + "..."
    : source.filename;

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span className="truncate max-w-[240px]">{shortName}</span>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 right-0 w-96 p-3 bg-white border border-slate-200 rounded-lg shadow-lg">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="text-xs font-semibold text-slate-700 truncate flex-1">
              {source.filename}
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-400 hover:text-slate-600 text-sm leading-none"
              aria-label="Close"
            >
              ×
            </button>
          </div>
          {source.quote ? (
            <>
              <div className="text-xs text-slate-500 mb-1">Extracted from:</div>
              <blockquote className="text-xs text-slate-700 italic border-l-2 border-slate-300 pl-2 mb-3">
                &ldquo;{source.quote}&rdquo;
              </blockquote>
            </>
          ) : (
            <div className="text-xs text-slate-500 italic mb-3">
              No verbatim quote stored for this field.
            </div>
          )}
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            Open source document
          </a>
        </div>
      )}
    </div>
  );
}
