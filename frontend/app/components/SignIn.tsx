"use client";

import { useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

type Step = "email" | "code";

export default function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const formatRetry = (err: any): string => {
    const retryAfter = Number(err.response?.headers?.["retry-after"]);
    const detail = err.response?.data?.detail;
    const waitMsg =
      Number.isFinite(retryAfter) && retryAfter > 0
        ? ` Try again in ${
            retryAfter >= 60
              ? `${Math.ceil(retryAfter / 60)} min`
              : `${retryAfter}s`
          }.`
        : "";
    return (detail || "Too many attempts.") + waitMsg;
  };

  const requestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await axios.post(
        `${API_URL}/auth/request-code`,
        { email: email.trim().toLowerCase() },
        { withCredentials: true },
      );
      // Dev mode: backend echoes the code so we can prefill it for testing.
      if (res.data?.dev_code) {
        setCode(res.data.dev_code);
      }
      setStep("code");
    } catch (err: any) {
      setError(
        err.response?.status === 429
          ? formatRetry(err)
          : err.response?.data?.detail || "Failed to send code",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const verifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await axios.post(
        `${API_URL}/auth/verify-code`,
        { email: email.trim().toLowerCase(), code: code.trim() },
        { withCredentials: true },
      );
      // Resume a pending invite flow if the user came from an invite link.
      const pendingInvite = sessionStorage.getItem("pending_invite_token");
      if (pendingInvite) {
        sessionStorage.removeItem("pending_invite_token");
        window.location.href = `/invite/${pendingInvite}`;
        return;
      }
      onSignedIn();
    } catch (err: any) {
      setError(
        err.response?.status === 429
          ? formatRetry(err)
          : err.response?.data?.detail || "Invalid code",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper flex items-start justify-center pt-32 px-6">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <span className="brand-mark text-5xl" aria-hidden>§</span>
          <h1 className="font-display text-[2.6rem] font-medium leading-none text-ink tracking-tight mt-4">
            Section
          </h1>
          <p className="mt-2 font-serif-italic text-ink-2">
            The operating record for upstream land work.
          </p>
        </div>

        {step === "email" ? (
          <form onSubmit={requestCode}>
            <div className="border border-line-strong bg-surface rounded-sm overflow-hidden">
              <div className="grid grid-cols-[1fr_auto] divide-x divide-line-strong">
                <input
                  type="email"
                  placeholder="your@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  className="px-5 py-4 bg-surface text-ink placeholder:text-ink-3 placeholder:font-serif-italic focus:outline-none focus:bg-accent-tint transition-colors text-[1rem]"
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors disabled:bg-ink-3 disabled:cursor-not-allowed text-sm whitespace-nowrap"
                >
                  {submitting ? "Sending…" : "Send code →"}
                </button>
              </div>
            </div>
            {error && (
              <p className="mt-3 text-sm font-serif-italic text-rust">{error}</p>
            )}
            <p className="mt-4 text-xs font-serif-italic text-ink-3">
              No password. We email a 6-digit code — valid for 10 minutes.
            </p>
          </form>
        ) : (
          <form onSubmit={verifyCode}>
            <p className="mb-3 text-sm font-serif-italic text-ink-2">
              Code sent to <strong className="text-ink">{email}</strong>
            </p>
            <div className="border border-line-strong bg-surface rounded-sm overflow-hidden">
              <div className="grid grid-cols-[1fr_auto] divide-x divide-line-strong">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  placeholder="000000"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  required
                  autoFocus
                  className="px-5 py-4 bg-surface text-ink placeholder:text-ink-3 focus:outline-none focus:bg-accent-tint transition-colors text-[1.4rem] tracking-[0.4em] font-mono"
                />
                <button
                  type="submit"
                  disabled={submitting || code.length !== 6}
                  className="px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors disabled:bg-ink-3 disabled:cursor-not-allowed text-sm whitespace-nowrap"
                >
                  {submitting ? "Verifying…" : "Sign in →"}
                </button>
              </div>
            </div>
            {error && (
              <p className="mt-3 text-sm font-serif-italic text-rust">{error}</p>
            )}
            <button
              type="button"
              onClick={() => { setStep("email"); setCode(""); setError(null); }}
              className="mt-4 text-sm text-ink-3 font-serif-italic underline underline-offset-2 hover:text-ink transition-colors"
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
