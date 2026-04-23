"use client";

import { useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const requestLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await axios.post(
        `${API_URL}/auth/request-link`,
        { email: email.trim().toLowerCase() },
        { withCredentials: true }
      );
      if (res.data?.dev_link) {
        // Dev mode: backend returned the link — navigate in this tab
        window.location.href = res.data.dev_link;
        return;
      }
      setSent(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to send link");
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

        {sent ? (
          <div className="border-l-[3px] border-positive pl-5 py-2">
            <div className="font-display text-lg text-ink">Check your email</div>
            <p className="mt-1 text-[0.95rem] font-serif-italic text-ink-2">
              Link sent to <strong>{email}</strong>. Opens in this tab.
            </p>
            <button
              className="mt-4 text-sm text-ink-3 font-serif-italic underline underline-offset-2 hover:text-ink transition-colors"
              onClick={() => { setSent(false); setEmail(""); }}
            >
              Use a different address
            </button>
          </div>
        ) : (
          <form onSubmit={requestLink}>
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
                  {submitting ? "Sending…" : "Send link →"}
                </button>
              </div>
            </div>
            {error && (
              <p className="mt-3 text-sm font-serif-italic text-rust">{error}</p>
            )}
            <p className="mt-4 text-xs font-serif-italic text-ink-3">
              No password. A sign-in link is sent to your email — valid for 15 minutes.
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
