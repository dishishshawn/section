import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
};

// Wire Sentry only when a DSN + auth token are present and the SDK is
// actually installed. Next 16 and @sentry/nextjs are still stabilizing their
// integration — if the wrapper throws at build time, fall back to the plain
// config so deploys don't fail. See README "Observability" for the manual
// source-map upload workaround.
let exported: NextConfig = nextConfig;
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN ?? process.env.SENTRY_DSN;
if (dsn) {
  try {
    // Dynamic require so missing package doesn't break `next build` locally.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { withSentryConfig } = require("@sentry/nextjs");
    exported = withSentryConfig(nextConfig, {
      silent: true,
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      disableLogger: true,
    });
  } catch {
    // @sentry/nextjs not installed or incompatible with this Next version —
    // skip-gate gracefully.
    exported = nextConfig;
  }
}

export default exported;
