"use client";

import { useEffect, useRef, useState } from "react";

export const TOUR_STORAGE_KEY = "section_tour_completed";

export interface GuidedTourProps {
  /** Force-open the tour regardless of localStorage. */
  open?: boolean;
  /** Called when the user finishes or skips. */
  onClose?: () => void;
  /** Optional per-user scoping — e.g. user id or email */
  userKey?: string | number | null;
}

interface TourStep {
  title: string;
  body: string;
}

const STEPS: TourStep[] = [
  {
    title: "1. Create a project",
    body: "Open a new file from the dashboard — one project per tract or prospect. Every document you upload lives inside a project.",
  },
  {
    title: "2. Upload a deed",
    body: "Drop recorded instruments into the Documents tab. Section extracts grantors, grantees, legal descriptions, and obligations automatically, with a page-level citation on every fact.",
  },
  {
    title: "3. Edit an extracted fact",
    body: "Every extracted value is editable. Click the pencil next to any fact to correct it — your override is recorded in the audit trail with the original OCR reading preserved.",
  },
  {
    title: "4. Export a title opinion",
    body: "When the file is ready, use Export to produce a runsheet, ownership table, or full title opinion packet as PDF or DOCX — each citation links back to the page.",
  },
];

function storageKeyFor(userKey: string | number | null | undefined): string {
  if (userKey == null || userKey === "") return TOUR_STORAGE_KEY;
  return `${TOUR_STORAGE_KEY}:${userKey}`;
}

/**
 * First-session 4-step guided tour. Renders as a dismissable overlay.
 * Persists completion in localStorage (per-user if `userKey` is supplied).
 */
export default function GuidedTour({ open, onClose, userKey }: GuidedTourProps) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const cardRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setMounted(true);
    if (typeof window === "undefined") return;
    if (open === true) {
      setVisible(true);
      return;
    }
    if (open === false) {
      setVisible(false);
      return;
    }
    // auto-detect on first load
    try {
      const done = window.localStorage.getItem(storageKeyFor(userKey));
      if (!done) setVisible(true);
    } catch {
      // localStorage may be unavailable — default to not showing
    }
  }, [open, userKey]);

  const persistDismissal = () => {
    try {
      if (typeof window !== "undefined") {
        window.localStorage.setItem(storageKeyFor(userKey), "1");
      }
    } catch {
      /* ignore */
    }
  };

  // Esc to close + focus management
  useEffect(() => {
    if (!visible) return;
    previousFocusRef.current = document.activeElement as HTMLElement;
    cardRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previousFocusRef.current?.focus();
    };
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist + close (Skip / Finish / backdrop-after-explicit-intent)
  const close = () => {
    persistDismissal();
    setVisible(false);
    onClose?.();
  };

  // Temporary dismiss without persisting (backdrop misclick)
  const dismiss = () => {
    setVisible(false);
    onClose?.();
  };

  const next = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      close();
    }
  };

  if (!mounted || !visible) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Section guided tour"
      data-testid="guided-tour"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
    >
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
        onClick={dismiss}
        aria-hidden
      />

      {/* card */}
      <div
        ref={cardRef}
        tabIndex={-1}
        className="relative w-full max-w-lg bg-paper border border-line-strong shadow-xl outline-none"
      >
        <div className="px-8 pt-7 pb-3 border-b border-line">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow mb-1">Guided tour</div>
              <h2 className="font-display text-2xl font-medium text-ink leading-tight">
                {current.title}
              </h2>
            </div>
            <span className="tabular text-sm text-ink-3 mt-1" aria-hidden>
              {step + 1} / {STEPS.length}
            </span>
          </div>
        </div>

        <div className="px-8 py-6">
          <p className="text-[1rem] text-ink-2 leading-[1.55] oldstyle">
            {current.body}
          </p>
        </div>

        {/* progress dots */}
        <div className="px-8 pb-5 flex items-center gap-1.5">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all ${
                i === step ? "w-6 bg-accent" : "w-1.5 bg-line-strong"
              }`}
              aria-hidden
            />
          ))}
        </div>

        <div className="px-8 pb-7 flex items-center justify-between">
          <button
            type="button"
            onClick={close}
            className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors underline underline-offset-4"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-3">
            {step > 0 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="text-sm text-ink-2 hover:text-ink transition-colors"
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={next}
              className="inline-flex items-center gap-2 bg-ink text-paper px-5 py-2.5 text-sm font-medium hover:bg-accent transition-colors"
            >
              <span>{isLast ? "Finish" : "Next"}</span>
              <span aria-hidden>→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
