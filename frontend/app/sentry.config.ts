/**
 * Sentry client + server initialization for the Next.js app.
 *
 * Gated on NEXT_PUBLIC_SENTRY_DSN — when the env var is unset (dev, tests,
 * local CI) init is a no-op and Sentry never ships a single byte.
 *
 * @sentry/nextjs v8 does not yet support Next 16 (peer dep is 13/14/15).
 * We treat it as an optional dependency and load it dynamically so the app
 * still builds when it's absent. See README "Observability" for the
 * workaround (downgrade Next or wait for @sentry/nextjs v9).
 *
 * Release tag comes from NEXT_PUBLIC_GIT_SHA. PII is off by default.
 */

const DSN =
  process.env.NEXT_PUBLIC_SENTRY_DSN ?? process.env.SENTRY_DSN ?? "";

export async function initSentry(): Promise<void> {
  if (!DSN) return;
  try {
    // Dynamic import so a missing optional dep doesn't break the bundle.
    const Sentry = await import("@sentry/nextjs").catch(() => null);
    if (!Sentry) return;
    Sentry.init({
      dsn: DSN,
      release: process.env.NEXT_PUBLIC_GIT_SHA ?? "dev",
      environment: process.env.NEXT_PUBLIC_ENV ?? "development",
      tracesSampleRate: Number(
        process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1"
      ),
      sendDefaultPii: false,
    });
  } catch {
    // Swallow — observability must never crash the app.
  }
}

// Fire-and-forget init on import.
if (DSN) {
  void initSentry();
}
