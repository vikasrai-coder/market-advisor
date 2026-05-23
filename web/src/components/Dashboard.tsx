"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRecommendations,
  getSignals,
  healthCheck,
  getUserProfile,
  type Recommendation,
  type TradingSignal,
  type TradeMode,
} from "@/lib/api";
import { RecommendationCard } from "./RecommendationCard";
import { RunAnalysisButton } from "./RunAnalysisButton";
import { SignalList } from "./SignalList";
import { ModeSelector } from "./ModeSelector";
import { SectorHeatmap } from "./SectorHeatmap";
import BacktestSimulator from "./BacktestSimulator";
import UserWorkspace from "./UserWorkspace";
import AdminDashboard from "./AdminDashboard";
import { createClient } from "@/lib/supabase/client";

export function Dashboard() {
  const [mode, setMode] = useState<TradeMode>("swing");
  const [targetDate, setTargetDate] = useState<string>(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split("T")[0];
  });
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [allSignals, setAllSignals] = useState<TradingSignal[]>([]);
  const [signalTypeFilter, setSignalTypeFilter] = useState<"buy" | "sell">("buy");
  const [tradeDate, setTradeDate] = useState<string | null>(null);
  const [status, setStatus] = useState<{ supabase: boolean; huggingface: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Master Admin & Permissions states
  const [sessionUser, setSessionUser] = useState<{ id: string; email: string; role: string } | null>(null);
  const [permissions, setPermissions] = useState<any>({
    can_view_charts: true,
    can_view_recommendations: true,
    can_view_heatmap: true,
    can_view_signals: true,
    can_backtest: true,
    can_use_portfolio: true,
  });
  const [activeTab, setActiveTab] = useState<"scans" | "signals" | "backtest" | "portfolio" | "admin">("scans");

  // Impersonation state
  const [impersonatedEmail, setImpersonatedEmail] = useState<string | null>(null);
  const [impersonatedId, setImpersonatedId] = useState<string | null>(null);

  // Load session and permissions on startup
  useEffect(() => {
    async function loadSession() {
      try {
        let userId = "";
        let email = "";
        let role = "user";
        
        // 1. Check offline localStorage session first
        const offlineId = localStorage.getItem("offline_user_id");
        const offlineEmail = localStorage.getItem("offline_user_email");
        const offlineRole = localStorage.getItem("offline_user_role");
        
        if (offlineId && offlineEmail) {
          userId = offlineId;
          email = offlineEmail;
          role = offlineRole || "user";
        } else {
          // 2. Fallback to Supabase Auth
          const supabase = createClient();
          const { data } = await supabase.auth.getUser();
          if (data?.user) {
            userId = data.user.id;
            email = data.user.email ?? "";
          }
        }
        
        if (userId) {
          // Fetch backend roles permissions profile
          const profile = await getUserProfile(userId, email || undefined);
          setSessionUser({
            id: userId,
            email: email || profile.email,
            role: profile.role,
          });
          
          // Only use custom profile permissions if not impersonating
          const sessionImpersonatedEmail = sessionStorage.getItem("impersonated_email");
          const sessionImpersonatedId = sessionStorage.getItem("impersonated_id");
          const sessionImpersonatedPermissions = sessionStorage.getItem("impersonated_permissions");
          
          if (sessionImpersonatedEmail && sessionImpersonatedId && sessionImpersonatedPermissions) {
            setImpersonatedEmail(sessionImpersonatedEmail);
            setImpersonatedId(sessionImpersonatedId);
            setPermissions(JSON.parse(sessionImpersonatedPermissions));
          } else {
            setPermissions(profile.permissions);
          }
        }
      } catch (err) {
        console.error("Failed to load user session permissions:", err);
      }
    }
    loadSession();
  }, []);

  const handleImpersonateUser = (email: string, id: string, userPermissions: any) => {
    setImpersonatedEmail(email);
    setImpersonatedId(id);
    setPermissions(userPermissions);
    sessionStorage.setItem("impersonated_email", email);
    sessionStorage.setItem("impersonated_id", id);
    sessionStorage.setItem("impersonated_permissions", JSON.stringify(userPermissions));
    setActiveTab("scans");
  };

  const handleExitImpersonation = () => {
    setImpersonatedEmail(null);
    setImpersonatedId(null);
    sessionStorage.removeItem("impersonated_email");
    sessionStorage.removeItem("impersonated_id");
    sessionStorage.removeItem("impersonated_permissions");
    
    // Restore master admin credentials
    if (sessionUser) {
      window.location.reload();
    }
  };

  const load = useCallback(async () => {
    setError(null);
    try {
      const filterDate = mode === "future" ? targetDate : undefined;
      const [recData, sigData, health] = await Promise.all([
        getRecommendations(filterDate, mode),
        getSignals(filterDate, undefined, mode),
        healthCheck().catch(() => null),
      ]);
      setRecs(recData.recommendations ?? []);
      setTradeDate(recData.trade_date ?? null);
      setAllSignals(sigData.signals ?? []);
      if (health) setStatus({ supabase: health.supabase, huggingface: health.huggingface });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data — is the API running?");
    }
  }, [mode, targetDate]);

  useEffect(() => {
    load();
  }, [load]);

  const getSignalsTitle = () => {
    const timeLabel =
      mode === "intraday"
        ? "same-day"
        : mode === "future"
        ? `setup for ${targetDate}`
        : "next session";
    const dirLabel = signalTypeFilter === "buy" ? "Bullish Momentum Buys" : "Bearish Breakdown Shorts";
    return `${dirLabel} (${timeLabel})`;
  };

  const getEmptyStateText = () => {
    switch (mode) {
      case "intraday":
        return "No intraday recommendations yet. Click 'Scan Intraday Signals' to generate same-day buy picks.";
      case "longterm":
        return "No long-term recommendations yet. Click 'Run Long-term Analysis' to find multi-month buy picks.";
      case "future":
        return `No recommendations found for target date ${targetDate}. Choose a date and run analysis.`;
      case "swing":
      default:
        return "No recommendations yet. Click 'Run Swing Trade Analysis' to score stocks and get 10 buy picks.";
    }
  };

  const filteredSignals = allSignals.filter((s) => s.signal_type === signalTypeFilter).slice(0, 15);

  return (
    <>
      {/* 1. Floating active user impersonation banner */}
      {impersonatedEmail && (
        <div className="fixed top-0 left-0 right-0 z-50 bg-gradient-to-r from-amber-600 to-yellow-600 text-slate-900 font-extrabold px-4 py-3 text-center text-xs shadow-lg flex items-center justify-center gap-3">
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-slate-900 animate-ping" />
            ⚠️ Active Impersonation: View-only simulation for <span className="underline font-black">{impersonatedEmail}</span>
          </span>
          <button
            onClick={handleExitImpersonation}
            className="px-2.5 py-0.5 rounded bg-slate-950 text-amber-400 font-extrabold text-[10px] uppercase border border-amber-400 hover:bg-slate-900 transition-all cursor-pointer"
          >
            Exit Impersonation
          </button>
        </div>
      )}

      {/* 2. Premium sticky glassmorphic navigation tabs */}
      <div className="mb-8 flex flex-wrap gap-2.5 border-b border-slate-900 pb-5 items-center">
        <button
          onClick={() => setActiveTab("scans")}
          className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer border flex items-center gap-1.5 ${
            activeTab === "scans"
              ? "bg-slate-100 text-slate-900 border-slate-200 shadow-md"
              : "bg-slate-950 text-slate-500 border-slate-900 hover:text-slate-300"
          }`}
        >
          🎯 Scans & Recs
        </button>

        <button
          onClick={() => {
            if (permissions.can_view_signals !== false) {
              setActiveTab("signals");
            }
          }}
          disabled={permissions.can_view_signals === false}
          className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer border flex items-center gap-1.5 ${
            permissions.can_view_signals === false ? "opacity-45 cursor-not-allowed" : ""
          } ${
            activeTab === "signals"
              ? "bg-slate-100 text-slate-900 border-slate-200 shadow-md"
              : "bg-slate-950 text-slate-500 border-slate-900 hover:text-slate-300"
          }`}
        >
          ⚡ Momentum Signals {permissions.can_view_signals === false && "🔒"}
        </button>

        <button
          onClick={() => {
            if (permissions.can_backtest !== false) {
              setActiveTab("backtest");
            }
          }}
          disabled={permissions.can_backtest === false}
          className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer border flex items-center gap-1.5 ${
            permissions.can_backtest === false ? "opacity-45 cursor-not-allowed" : ""
          } ${
            activeTab === "backtest"
              ? "bg-slate-100 text-slate-900 border-slate-200 shadow-md"
              : "bg-slate-950 text-slate-500 border-slate-900 hover:text-slate-300"
          }`}
        >
          🧪 Backtest Labs {permissions.can_backtest === false && "🔒"}
        </button>

        <button
          onClick={() => {
            if (permissions.can_use_portfolio !== false) {
              setActiveTab("portfolio");
            }
          }}
          disabled={permissions.can_use_portfolio === false}
          className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer border flex items-center gap-1.5 ${
            permissions.can_use_portfolio === false ? "opacity-45 cursor-not-allowed" : ""
          } ${
            activeTab === "portfolio"
              ? "bg-slate-100 text-slate-900 border-slate-200 shadow-md"
              : "bg-slate-950 text-slate-500 border-slate-900 hover:text-slate-300"
          }`}
        >
          💼 My Portfolio {permissions.can_use_portfolio === false && "🔒"}
        </button>

        {sessionUser?.role === "admin" && !impersonatedEmail && (
          <button
            onClick={() => setActiveTab("admin")}
            className={`px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer border flex items-center gap-1.5 sm:ml-auto ${
              activeTab === "admin"
                ? "bg-purple-600 text-white border-purple-500 shadow-[0_0_15px_rgba(168,85,247,0.3)]"
                : "bg-slate-950 text-purple-400 border-slate-900/60 hover:text-purple-300 hover:bg-slate-900/10"
            }`}
          >
            🛡️ Admin Control Center
          </button>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      {/* Render active tab content */}
      {activeTab === "admin" && sessionUser?.role === "admin" && !impersonatedEmail ? (
        <AdminDashboard onImpersonate={handleImpersonateUser} />
      ) : activeTab === "scans" ? (
        <>
          {permissions.can_view_recommendations === false ? (
            <div className="mb-6 p-6 rounded-2xl border border-rose-500/20 bg-rose-500/5 text-rose-400 text-sm text-center font-bold">
              🔒 Access Restricted: Scanner Recommendations are locked by Administrator Vikas Rai.
            </div>
          ) : (
            <>
              <section className="mb-6 flex flex-col gap-6 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                <h2 className="text-base font-semibold text-slate-300">Choose Analysis Mode</h2>
                <ModeSelector
                  activeMode={mode}
                  onChangeMode={setMode}
                  targetDate={targetDate}
                  onChangeTargetDate={setTargetDate}
                />
              </section>

              <section className="mb-8 flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                <RunAnalysisButton
                  mode={mode}
                  targetDate={mode === "future" ? targetDate : undefined}
                  onComplete={load}
                  onLoadingChange={setLoading}
                />
                <div className="flex flex-wrap gap-3 text-xs">
                  <StatusBadge ok={status?.supabase} label="Supabase" />
                  <StatusBadge ok={status?.huggingface} label="Hugging Face" />
                  {tradeDate && (
                    <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-400">
                      Active Trade Date: {tradeDate}
                    </span>
                  )}
                </div>
              </section>

              {permissions.can_view_heatmap !== false && !loading && recs.length > 0 && (
                <SectorHeatmap recs={recs} />
              )}

              <div className={`relative ${loading ? "pointer-events-none" : ""}`}>
                {loading && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-950/70 backdrop-blur-sm min-h-[120px]">
                    <p className="text-sm text-slate-300">Updating results when analysis finishes…</p>
                  </div>
                )}
                {recs.length === 0 ? (
                  <p className="text-slate-500 py-6">
                    {getEmptyStateText()}
                  </p>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {recs.map((rec) => (
                      <RecommendationCard
                        key={rec.id ?? `${rec.symbol}-${rec.rank}-${rec.trade_date}`}
                        rec={rec}
                      />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </>
      ) : activeTab === "signals" ? (
        <>
          {permissions.can_view_signals === false ? (
            <div className="p-6 rounded-2xl border border-slate-900 bg-slate-950/20 text-slate-500 text-xs text-center font-bold">
              🔒 Momentum Breakdowns signals list are restricted on your profile.
            </div>
          ) : (
            <section className="rounded-xl border border-slate-800 bg-slate-900/25 p-6">
              <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800/80 pb-4">
                <h2 className="text-xl font-bold tracking-tight text-white">{getSignalsTitle()}</h2>
                <div className="flex items-center gap-1.5 rounded-lg bg-slate-950 p-1 border border-slate-800">
                  <button
                    type="button"
                    onClick={() => setSignalTypeFilter("buy")}
                    className={`rounded px-3 py-1.5 text-xs font-bold transition-all cursor-pointer ${
                      signalTypeFilter === "buy"
                        ? "bg-emerald-950 text-emerald-300 shadow-md border border-emerald-500/20"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    📈 Bullish momentum
                  </button>
                  <button
                    type="button"
                    onClick={() => setSignalTypeFilter("sell")}
                    className={`rounded px-3 py-1.5 text-xs font-bold transition-all cursor-pointer ${
                      signalTypeFilter === "sell"
                        ? "bg-red-950 text-red-300 shadow-md border border-red-500/20"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    📉 Bearish breakdown
                  </button>
                </div>
              </div>
              <SignalList signals={filteredSignals} />
            </section>
          )}
        </>
      ) : activeTab === "backtest" ? (
        <>
          {permissions.can_backtest === false ? (
            <div className="p-6 rounded-2xl border border-slate-900 bg-slate-950/20 text-slate-500 text-xs text-center font-bold">
              🔒 Backtest Labs are deactivated on your user account by admin.
            </div>
          ) : (
            <BacktestSimulator currentMode={mode} />
          )}
        </>
      ) : (
        <>
          {permissions.can_use_portfolio === false ? (
            <div className="p-6 rounded-2xl border border-slate-900 bg-slate-950/20 text-slate-500 text-xs text-center font-bold">
              🔒 Portfolio & Watchlists Labs are locked by the administrator.
            </div>
          ) : (
            <UserWorkspace
              userId={impersonatedId || sessionUser?.id || undefined}
              userEmail={impersonatedEmail || sessionUser?.email || undefined}
            />
          )}
        </>
      )}
    </>
  );
}

function StatusBadge({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 ${
        ok ? "bg-emerald-900/40 text-emerald-300" : "bg-slate-800 text-slate-500"
      }`}
    >
      {label}: {ok ? "connected" : "not configured"}
    </span>
  );
}
