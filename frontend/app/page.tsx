"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import ProjectShell from "./components/ProjectShell";
import SignIn from "./components/SignIn";
import GuidedTour from "./components/GuidedTour";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface Me {
  id: number;
  email: string;
  display_name: string | null;
}

export default function Home() {
  const [me, setMe] = useState<Me | null | "loading">("loading");

  const checkSession = async () => {
    try {
      const res = await axios.get(`${API_URL}/auth/me`, { withCredentials: true });
      setMe(res.data);
    } catch {
      setMe(null);
    }
  };

  useEffect(() => {
    checkSession();
  }, []);

  if (me === "loading") {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <span className="inline-block w-4 h-4 border-2 border-ink-3/30 border-t-ink rounded-full animate-spin" />
      </div>
    );
  }

  if (!me) {
    return <SignIn onSignedIn={checkSession} />;
  }

  return (
    <>
      <ProjectShell me={me} onSignOut={() => setMe(null)} />
      {/* First-session guided tour; persists dismissal per-user in localStorage */}
      <GuidedTour userKey={me.id} />
    </>
  );
}
