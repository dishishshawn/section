"use client";

import { ReactNode } from "react";

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  primaryAction?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  /** Optional className applied to outer wrapper to allow size tweaks */
  className?: string;
}

/**
 * Reusable empty-state panel.
 *
 * Matches the newspaper/register aesthetic used throughout Section: dashed
 * border, surface-2 background, display title, serif-italic body, ink CTA.
 */
export default function EmptyState({
  icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      data-testid="empty-state"
      className={
        "border border-dashed border-line-strong bg-surface-2 px-6 py-14 text-center " +
        (className ?? "")
      }
    >
      {icon ? (
        <div className="mb-3 flex justify-center text-ink-3" aria-hidden>
          {icon}
        </div>
      ) : (
        <div
          className="mb-3 flex justify-center text-ink-3 font-display text-3xl"
          aria-hidden
        >
          §
        </div>
      )}
      <div className="font-display text-xl text-ink mb-1">{title}</div>
      {description && (
        <p className="text-sm text-ink-3 max-w-md mx-auto font-serif-italic">
          {description}
        </p>
      )}
      {(primaryAction || secondaryAction) && (
        <div className="mt-5 flex items-center justify-center gap-3">
          {primaryAction && (
            <button
              type="button"
              onClick={primaryAction.onClick}
              className="inline-flex items-center gap-2 bg-ink text-paper px-5 py-2.5 text-sm font-medium hover:bg-accent transition-colors"
            >
              <span>{primaryAction.label}</span>
              <span aria-hidden>→</span>
            </button>
          )}
          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="text-sm font-serif-italic text-ink-3 hover:text-ink transition-colors underline underline-offset-4"
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
