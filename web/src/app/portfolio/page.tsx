"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { getUserProfile } from "@/lib/api";
import UserWorkspace from "@/components/UserWorkspace";
import Link from "next/link";
import { ArrowLeftOutlined } from "@ant-design/icons";

type SessionUser = { id: string; email: string; role: string };

export default function PortfolioPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sessionUser, setSessionUser] = useState<SessionUser | null>(null);
  const [canUseChatbot, setCanUseChatbot] = useState(false);

  useEffect(() => {
    async function checkAuth() {
      try {
        let userId = "";
        let email = "";
        let role = "user";

        const offlineId = localStorage.getItem("offline_user_id");
        const offlineEmail = localStorage.getItem("offline_user_email");
        const offlineRole = localStorage.getItem("offline_user_role");

        if (offlineId && offlineEmail) {
          userId = offlineId;
          email = offlineEmail;
          role = offlineRole || "user";
          setIsAuthenticated(true);
        } else {
          const supabase = createClient();
          const { data } = await supabase.auth.getUser();
          if (data?.user) {
            userId = data.user.id;
            email = data.user.email ?? "";
            setIsAuthenticated(true);
          }
        }

        if (userId) {
          setSessionUser({ id: userId, email, role });
          try {
            const profile = await getUserProfile(userId, email || undefined);
            setSessionUser({ id: userId, email: email || profile.email, role: profile.role });
            setCanUseChatbot(profile.permissions?.can_use_chatbot === true);
          } catch (profileErr) {
            console.warn("Could not fetch user profile:", profileErr);
            if (role === "admin" || offlineId === "admin-vikas-id") {
              setSessionUser({ id: userId, email, role: "admin" });
            }
          }
        } else {
          router.push("/login");
        }
      } catch (err) {
        console.error("Auth check error:", err);
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, [router]);

  const handleAnalyzeHolding = (symbol: string, shares: number, buyPrice: number) => {
    const prefill = { type: "single", holding: { symbol, shares, buyPrice } };
    sessionStorage.setItem("chatbot_prefill", JSON.stringify(prefill));
    router.push("/?tab=chatbot");
  };

  const handleAnalyzeEntirePortfolio = (holdings: { symbol: string; shares: number; buyPrice: number }[]) => {
    const prefill = { type: "portfolio", holdings };
    sessionStorage.setItem("chatbot_prefill", JSON.stringify(prefill));
    router.push("/?tab=chatbot");
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        <p className="text-sm font-semibold tracking-wider animate-pulse">LOADING PORTFOLIO...</p>
      </div>
    );
  }

  if (!isAuthenticated || !sessionUser) {
    return null;
  }

  return (
    <main className="flex-1 bg-slate-950 min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Navigation & Header */}
        <div className="mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-sm text-[#10B981] hover:text-[#059669] font-semibold transition">
            <ArrowLeftOutlined />
            <span>Back to Dashboard</span>
          </Link>
          <div className="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-black tracking-tight text-white">My Portfolio Hub</h1>
              <p className="text-sm text-slate-400 mt-1">
                Your dedicated trading ledger to track active share holdings, targets, and completed transaction logs.
              </p>
            </div>
          </div>
        </div>

        {/* UserWorkspace Component */}
        <div className="border border-slate-900 rounded-3xl bg-slate-900/10 p-1">
          <UserWorkspace
            userId={sessionUser.id}
            userEmail={sessionUser.email}
            onAnalyzeHolding={handleAnalyzeHolding}
            onAnalyzeEntirePortfolio={handleAnalyzeEntirePortfolio}
            canUseChatbot={canUseChatbot}
          />
        </div>
      </div>
    </main>
  );
}
