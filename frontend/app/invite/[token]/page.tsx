"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface InviteInfo {
  org_id: number;
  org_name: string;
  invited_email: string;
  role: string;
}

type PageState = "loading" | "preview" | "accepting" | "accepted" | "error" | "expired";

export default function InviteAcceptPage() {
  const params = useParams();
  const token = params?.token as string;

  const [state, setState] = useState<PageState>("loading");
  const [invite, setInvite] = useState<InviteInfo | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [me, setMe] = useState<{ id: number; email: string } | null>(null);

  useEffect(() => {
    if (!token) return;
    loadInvite();
    checkSession();
  }, [token]);

  const checkSession = async () => {
    try {
      const res = await axios.get(`${API_URL}/auth/me`, { withCredentials: true });
      setMe(res.data);
    } catch {
      setMe(null);
    }
  };

  const loadInvite = async () => {
    try {
      const res = await axios.get(`${API_URL}/orgs/invites/${token}`, {
        withCredentials: true,
      });
      setInvite(res.data);
      setState("preview");
    } catch (err: any) {
      const detail = err.response?.data?.detail || "";
      if (detail.includes("expired")) {
        setState("expired");
      } else {
        setState("error");
        setErrorMsg(detail || "This invite link is invalid or has already been used.");
      }
    }
  };

  const acceptInvite = async () => {
    setState("accepting");
    try {
      await axios.post(
        `${API_URL}/orgs/invites/${token}/accept`,
        {},
        { withCredentials: true }
      );
      setState("accepted");
    } catch (err: any) {
      setState("error");
      setErrorMsg(err.response?.data?.detail || "Failed to accept invite");
    }
  };

  const signInFirst = () => {
    // Redirect to home which shows sign-in; store token in sessionStorage to resume
    sessionStorage.setItem("pending_invite_token", token);
    window.location.href = "/";
  };

  return (
    <div className="min-h-screen bg-paper flex items-start justify-center pt-32 px-6">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <span className="brand-mark text-5xl" aria-hidden>§</span>
          <h1 className="font-display text-[2.6rem] font-medium leading-none text-ink tracking-tight mt-4">
            Section
          </h1>
        </div>

        {state === "loading" && (
          <div className="flex items-center gap-3 text-ink-3">
            <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin" />
            <span className="font-serif-italic">Loading invite…</span>
          </div>
        )}

        {state === "preview" && invite && (
          <div>
            <div className="border-l-[3px] border-accent pl-5 py-3 mb-8">
              <p className="text-sm text-ink-2 font-serif-italic">
                You've been invited to join
              </p>
              <h2 className="font-display text-2xl font-medium text-ink mt-1">
                {invite.org_name}
              </h2>
              <p className="text-sm text-ink-3 font-serif-italic mt-1">
                as <strong className="text-ink">{invite.role}</strong> — sent to{" "}
                <strong className="text-ink">{invite.invited_email}</strong>
              </p>
            </div>

            {!me ? (
              <div className="space-y-4">
                <p className="text-sm text-ink-2 font-serif-italic">
                  Sign in to accept this invitation.
                </p>
                <button
                  onClick={signInFirst}
                  className="w-full px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors text-sm"
                >
                  Sign in to accept →
                </button>
              </div>
            ) : me.email !== invite.invited_email ? (
              <div className="space-y-4">
                <div className="border-l-2 border-rust pl-4 py-2">
                  <p className="text-sm text-ink-2 font-serif-italic">
                    You're signed in as <strong>{me.email}</strong>, but this invite
                    was sent to <strong>{invite.invited_email}</strong>.
                  </p>
                </div>
                <p className="text-xs text-ink-3 font-serif-italic">
                  Sign out and sign in with the correct email to accept.
                </p>
              </div>
            ) : (
              <button
                onClick={acceptInvite}
                className="w-full px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors text-sm"
              >
                Accept invitation →
              </button>
            )}
          </div>
        )}

        {state === "accepting" && (
          <div className="flex items-center gap-3 text-ink-3">
            <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin" />
            <span className="font-serif-italic">Accepting invite…</span>
          </div>
        )}

        {state === "accepted" && (
          <div>
            <div className="border-l-[3px] border-positive pl-5 py-3 mb-8">
              <div className="font-display text-xl text-ink">You're in.</div>
              <p className="mt-1 text-sm font-serif-italic text-ink-2">
                You've joined <strong>{invite?.org_name}</strong> as{" "}
                <strong>{invite?.role}</strong>.
              </p>
            </div>
            <a
              href="/"
              className="block w-full px-6 py-4 bg-ink text-paper font-medium hover:bg-accent transition-colors text-sm text-center"
            >
              Open Section →
            </a>
          </div>
        )}

        {state === "expired" && (
          <div>
            <div className="border-l-[3px] border-rust pl-5 py-3 mb-6">
              <div className="font-display text-xl text-ink">Invite expired</div>
              <p className="mt-1 text-sm font-serif-italic text-ink-2">
                This invite link has expired. Ask the workspace owner to send a new one.
              </p>
            </div>
            <a
              href="/"
              className="block w-full px-6 py-4 bg-surface border border-line-strong text-ink font-medium hover:bg-surface-2 transition-colors text-sm text-center"
            >
              Go to Section
            </a>
          </div>
        )}

        {state === "error" && (
          <div>
            <div className="border-l-[3px] border-rust pl-5 py-3 mb-6">
              <div className="font-display text-xl text-ink">Something went wrong</div>
              <p className="mt-1 text-sm font-serif-italic text-ink-2">{errorMsg}</p>
            </div>
            <a
              href="/"
              className="block w-full px-6 py-4 bg-surface border border-line-strong text-ink font-medium hover:bg-surface-2 transition-colors text-sm text-center"
            >
              Go to Section
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
