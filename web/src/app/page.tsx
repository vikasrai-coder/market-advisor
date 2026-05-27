"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Dashboard } from "@/components/Dashboard";
import { Landing } from "@/components/Landing";

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      try {
        const offlineId = localStorage.getItem("offline_user_id");
        if (offlineId) {
          setIsAuthenticated(true);
          setLoading(false);
          return;
        }

        const supabase = createClient();
        const { data } = await supabase.auth.getUser();
        if (data?.user) {
          setIsAuthenticated(true);
        }
      } catch (err) {
        console.error("Auth check error:", err);
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        <p className="text-sm font-semibold tracking-wider animate-pulse">LOADING PLATFORM...</p>
      </div>
    );
  }

  if (isAuthenticated) {
    return (
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <Dashboard />
        </div>
      </main>
    );
  }

  return <Landing />;
}
