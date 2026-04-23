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
      <span className="inline-flex items-center gap-1 text-xs text-ink-4 font-serif-italic">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        no source
      </span>
    );
  }

  const fileUrl = `${API_URL}/documents/${source.document_id}/file`;
  const shortName =
    source.filename.length > 40 ? source.filename.slice(0, 37) + "…" : source.filename;

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-baseline gap-1.5 text-sm text-accent hover:text-accent-strong transition-colors font-serif-italic"
      >
        <span className="text-[0.7rem] not-italic" aria-hidden>§</span>
        <span className="truncate max-w-[260px] underline underline-offset-2 decoration-accent/40 hover:decoration-accent">
          {shortName}
        </span>
      </button>

      {open && (
        <>
          {/* click-away backdrop */}
          <div
            className="fixed inset-0 z-20"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="absolute z-30 mt-2 right-0 w-[26rem] bg-surface border border-rule shadow-[0_10px_30px_-10px_rgba(29,38,53,0.2)]">
            {/* top double rule — document affordance */}
            <div className="border-b-[2.5px] border-rule" />
            <div className="border-b border-rule" />

            <div className="px-5 py-4">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0">
                  <div className="eyebrow mb-0.5">Source of record</div>
                  <div className="font-display text-[1rem] text-ink truncate leading-tight">
                    {source.filename}
                  </div>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="text-ink-3 hover:text-ink text-lg leading-none -mt-1"
                  aria-label="Close"
                >
                  ×
                </button>
              </div>

              {source.quote ? (
                <figure className="mb-4">
                  <div className="eyebrow mb-1.5">Extracted from</div>
                  <blockquote className="border-l-[2.5px] border-accent pl-4 py-1 font-serif-italic text-ink-2 text-[0.98rem] leading-relaxed">
                    &ldquo;{source.quote}&rdquo;
                  </blockquote>
                </figure>
              ) : (
                <div className="text-sm text-ink-3 font-serif-italic mb-4">
                  No verbatim quote was stored for this field.
                </div>
              )}

              <a
                href={fileUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-baseline gap-1.5 text-sm text-accent hover:text-accent-strong font-serif-italic"
              >
                Open source document
                <span className="not-italic text-xs" aria-hidden>↗</span>
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
