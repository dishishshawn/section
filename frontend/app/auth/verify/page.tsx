"use client";

import { useEffect, useState } from "react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function VerifyPage() {
  const [status, setStatus] = useState<"working" | "error">("working");
  const [message, setMessage] = useState<string>("Signing you in…");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("Missing token. Request a new sign-in link.");
      return;
    }

    (async () => {
      try {
        await axios.post(
          `${API_URL}/auth/verify-complete`,
          { token },
          { withCredentials: true },
        );
        // Resume a pending invite flow if the user came from an invite link.
        const pendingInvite = sessionStorage.getItem("pending_invite_token");
        if (pendingInvite) {
          sessionStorage.removeItem("pending_invite_token");
          window.history.replaceState({}, "", "/");
          window.location.replace(`/invite/${pendingInvite}`);
        } else {
          window.history.replaceState({}, "", "/");
          window.location.replace("/");
        }
      } catch (err: any) {
        setStatus("error");
        setMessage(
          err?.response?.data?.detail ||
          "Link invalid or expired. Request a new sign-in link.",
        );
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-paper flex items-start justify-center pt-32 px-6">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <span className="brand-mark text-5xl" aria-hidden>§</span>
          <h1 className="font-display text-[2.6rem] font-medium leading-none text-ink tracking-tight mt-4">
            Section
          </h1>
        </div>
        {status === "working" ? (
          <div className="flex items-center gap-3 text-ink-2">
            <span className="inline-block w-3 h-3 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin" />
            <span className="font-serif-italic">{message}</span>
          </div>
        ) : (
          <div className="border-l-[3px] border-rust pl-5 py-2">
            <div className="font-display text-lg text-ink">Sign-in failed</div>
            <p className="mt-1 text-[0.95rem] font-serif-italic text-ink-2">{message}</p>
            <a
              href="/"
              className="mt-4 inline-block text-sm text-ink-3 font-serif-italic underline underline-offset-2 hover:text-ink transition-colors"
            >
              Back to sign in
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
