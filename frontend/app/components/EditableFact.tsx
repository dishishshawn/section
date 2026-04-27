"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

type EntityType = "instrument" | "interest" | "party" | "obligation";

interface ReviewMeta {
  new_value: string;
  old_value: string | null;
  user_display: string | null;
  changed_at: string | null;
  reason: string | null;
}

interface EditableFactProps {
  entityType: EntityType;
  entityId: number;
  field: string;
  value: string;
  /** Quote from source document to show while editing, for context */
  sourceQuote?: string | null;
  /** If already reviewed, pass the review metadata for the badge */
  reviewMeta?: ReviewMeta | null;
  /** Called after a successful save with the new value */
  onSave?: (newValue: string) => void;
  /** Render the display value — defaults to plain text */
  renderValue?: (value: string) => React.ReactNode;
  className?: string;
}

export default function EditableFact({
  entityType,
  entityId,
  field,
  value,
  sourceQuote,
  reviewMeta,
  onSave,
  renderValue,
  className = "",
}: EditableFactProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  // Keep draft in sync if parent value changes (e.g. after optimistic update)
  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  const save = async () => {
    if (draft === value) { setEditing(false); return; }
    setSaving(true);
    setError(null);
    try {
      await axios.patch(
        `${API_URL}/${entityType}s/${entityId}/fields/${field}`,
        { new_value: draft, reason: reason || null },
        { withCredentials: true },
      );
      onSave?.(draft);
      setEditing(false);
      setReason("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(value);
    setReason("");
    setError(null);
    setEditing(false);
  };

  if (editing) {
    return (
      <span className={`inline-block ${className}`}>
        <span className="inline-flex flex-col gap-1.5">
          {sourceQuote && (
            <span className="block text-[0.8rem] font-serif-italic text-ink-3 border-l-2 border-line-strong pl-2 max-w-xs truncate" title={sourceQuote}>
              Source: "{sourceQuote}"
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 flex-wrap">
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") save();
                if (e.key === "Escape") cancel();
              }}
              className="font-inherit text-[inherit] bg-accent-tint border border-accent px-2 py-0.5 rounded-sm focus:outline-none min-w-0 w-48"
            />
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason (optional)"
              className="text-sm text-ink-2 bg-surface border border-line px-2 py-0.5 rounded-sm focus:outline-none w-36"
            />
            <button
              onClick={save}
              disabled={saving}
              className="text-sm px-2.5 py-0.5 bg-ink text-paper rounded-sm hover:bg-accent transition-colors disabled:opacity-50"
            >
              {saving ? "…" : "Save"}
            </button>
            <button
              onClick={cancel}
              className="text-sm text-ink-3 font-serif-italic hover:text-ink transition-colors"
            >
              Cancel
            </button>
          </span>
          {error && <span className="text-xs font-serif-italic text-rust">{error}</span>}
        </span>
      </span>
    );
  }

  return (
    <span
      className={`group/fact inline-flex items-baseline gap-1.5 ${className}`}
    >
      <span>{renderValue ? renderValue(value) : value}</span>
      <button
        onClick={() => setEditing(true)}
        title="Edit this fact"
        className="opacity-0 group-hover/fact:opacity-100 transition-opacity text-ink-3 hover:text-accent text-[0.75rem] leading-none translate-y-[-1px]"
        aria-label={`Edit ${field}`}
      >
        ✎
      </button>
    </span>
  );
}
