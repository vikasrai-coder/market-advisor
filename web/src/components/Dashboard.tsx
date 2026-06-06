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
import ChatbotAdvisor from "./ChatbotAdvisor";
import PennyScans from "./PennyScans";
import AlphaAlerts from "./AlphaAlerts";
import InstitutionalScanner from "./InstitutionalScanner";
import { KPIDashboard } from "./KPIDashboard";
import { ModuleNavigation } from "./ModuleNavigation";
import { createClient } from "@/lib/supabase/client";
import { BuyStockModal } from "./BuyStockModal";

type PermissionSet = {
  can_view_charts: boolean;
  can_view_recommendations: boolean;
  can_view_heatmap: boolean;
  can_view_signals: boolean;
  can_backtest: boolean;
  can_use_portfolio: boolean;
  can_use_chatbot: boolean;
};

type SessionUser = { id: string; email: string; role: string };
type DashboardTab = "scans" | "signals" | "backtest" | "portfolio" | "admin" | "chatbot" | "pennyscans" | "alpha" | "institutional" | "mindmap";

const DEFAULT_PERMISSIONS: PermissionSet = {
  can_view_charts: false,
  can_view_recommendations: false,
  can_view_heatmap: false,
  can_view_signals: false,
  can_backtest: false,
  can_use_portfolio: false,
  can_use_chatbot: false,
};

type ChatbotPrefill =
  | {
      type: "single";
      holding: { symbol: string; shares: number; buyPrice: number };
    }
  | {
      type: "portfolio";
      holdings: { symbol: string; shares: number; buyPrice: number }[];
    };

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
  const [sessionUser, setSessionUser] = useState<SessionUser | null>(null);
  const [permissions, setPermissions] = useState<PermissionSet>(DEFAULT_PERMISSIONS);
  const [activeTab, setActiveTab] = useState<DashboardTab>("scans");
  const [chatbotPrefill, setChatbotPrefill] = useState<ChatbotPrefill | null>(null);
  const [impersonatedEmail, setImpersonatedEmail] = useState<string | null>(null);
  const [impersonatedId, setImpersonatedId] = useState<string | null>(null);

  // Buy Modal State for Signals
  const [buyModalOpen, setBuyModalOpen] = useState(false);
  const [buyModalSymbol, setBuyModalSymbol] = useState("");
  const [buyModalPrice, setBuyModalPrice] = useState(0);
  const [buyModalTarget, setBuyModalTarget] = useState<number | null>(null);
  const [buyModalStop, setBuyModalStop] = useState<number | null>(null);

  const handleBuyFromSignal = (symbol: string, price: number, target: number | null, stop: number | null) => {
    setBuyModalSymbol(symbol);
    setBuyModalPrice(price);
    setBuyModalTarget(target);
    setBuyModalStop(stop);
    setBuyModalOpen(true);
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get("tab") as DashboardTab;
      if (tab && ["scans", "signals", "backtest", "portfolio", "chatbot", "pennyscans", "alpha", "institutional", "admin", "mindmap"].includes(tab)) {
        setActiveTab(tab);
      }

      const storedPrefill = sessionStorage.getItem("chatbot_prefill");
      if (storedPrefill) {
        try {
          setChatbotPrefill(JSON.parse(storedPrefill));
          sessionStorage.removeItem("chatbot_prefill");
        } catch (e) {
          console.error("Failed to parse chatbot prefill:", e);
        }
      }
    }
  }, []);

  useEffect(() => {
    async function loadSession() {
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
        } else {
          try {
            const supabase = createClient();
            const { data } = await supabase.auth.getUser();
            if (data?.user) {
              userId = data.user.id;
              email = data.user.email ?? "";
            }
          } catch {
            // Offline mode can still use cached local credentials.
          }
        }

        if (!userId) return;

        setSessionUser({ id: userId, email, role });

        try {
          const profile = await getUserProfile(userId, email || undefined);
          setSessionUser({ id: userId, email: email || profile.email, role: profile.role });

          const storedEmail = sessionStorage.getItem("impersonated_email");
          const storedId = sessionStorage.getItem("impersonated_id");
          const storedPermissions = sessionStorage.getItem("impersonated_permissions");

          if (storedEmail && storedId && storedPermissions) {
            setImpersonatedEmail(storedEmail);
            setImpersonatedId(storedId);
            setPermissions(normalizePermissions(JSON.parse(storedPermissions)));
          } else {
            setPermissions(normalizePermissions(profile.permissions));
          }
        } catch (profileErr) {
          console.warn("Could not fetch user profile from API, using defaults:", profileErr);
          if (role === "admin" || offlineId === "admin-vikas-id") {
            setSessionUser({ id: userId, email, role: "admin" });
          }
        }
      } catch (err) {
        console.error("Failed to load user session:", err);
      }
    }

    loadSession();
  }, []);

  const handleImpersonateUser = (email: string, id: string, userPermissions: PermissionSet) => {
    setImpersonatedEmail(email);
    setImpersonatedId(id);
    setPermissions(userPermissions);
    sessionStorage.setItem("impersonated_email", email);
    sessionStorage.setItem("impersonated_id", id);
    sessionStorage.setItem("impersonated_permissions", JSON.stringify(userPermissions));
    setActiveTab("scans");
  };

  const handleExitImpersonation = async () => {
    setImpersonatedEmail(null);
    setImpersonatedId(null);
    sessionStorage.removeItem("impersonated_email");
    sessionStorage.removeItem("impersonated_id");
    sessionStorage.removeItem("impersonated_permissions");

    if (!sessionUser) {
      setPermissions(DEFAULT_PERMISSIONS);
      setActiveTab("scans");
      return;
    }

    try {
      const profile = await getUserProfile(sessionUser.id, sessionUser.email || undefined);
      setSessionUser({ id: sessionUser.id, email: sessionUser.email || profile.email, role: profile.role });
      setPermissions(normalizePermissions(profile.permissions));
    } catch {
      setPermissions(sessionUser.role === "admin" ? DEFAULT_PERMISSIONS : permissions);
    }
    setActiveTab("scans");
  };

  const handleAnalyzeHoldingFromPortfolio = (symbol: string, shares: number, buyPrice: number) => {
    setChatbotPrefill({ type: "single", holding: { symbol, shares, buyPrice } });
    setActiveTab("chatbot");
  };

  const handleAnalyzeEntirePortfolioFromPortfolio = (
    holdings: { symbol: string; shares: number; buyPrice: number }[]
  ) => {
    setChatbotPrefill({ type: "portfolio", holdings });
    setActiveTab("chatbot");
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
      setError(e instanceof Error ? e.message : "Could not load data. Is the API running?");
    }
  }, [mode, targetDate]);

  useEffect(() => {
    // Initial dashboard hydration depends on API state, so it belongs in an effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const getSignalsTitle = () => {
    const timeLabel =
      mode === "intraday" ? "same-day" : mode === "future" ? `setup for ${targetDate}` : "next session";
    const dirLabel = signalTypeFilter === "buy" ? "Bullish Momentum Buys" : "Bearish Breakdown Shorts";
    return `${dirLabel} (${timeLabel})`;
  };

  const getEmptyStateText = () => {
    switch (mode) {
      case "intraday":
        return "No intraday recommendations yet. Run an intraday scan to generate same-day buy picks.";
      case "longterm":
        return "No long-term recommendations yet. Run long-term analysis to find multi-month setups.";
      case "future":
        return `No recommendations found for ${targetDate}. Choose another date or run a new scan.`;
      case "swing":
      default:
        return "No recommendations yet. Run swing trade analysis to score stocks and generate buy picks.";
    }
  };

  const filteredSignals = allSignals.filter((s) => s.signal_type === signalTypeFilter).slice(0, 15);
  const avgScore = recs.length
    ? Math.round(recs.reduce((sum, rec) => sum + Number(rec.composite_score || 0), 0) / recs.length)
    : 0;
  const visibleTabs = buildTabs({ permissions, sessionUser, impersonatedEmail, onSelect: setActiveTab });

  return (
    <>
      {impersonatedEmail && (
        <div className="fixed inset-x-0 top-0 z-50 border-b border-amber-400/40 bg-amber-400 px-3 py-2 text-slate-950 shadow-lg">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 text-xs font-bold sm:flex-row sm:items-center sm:justify-between">
            <span className="truncate">
              Viewing as <span className="underline">{impersonatedEmail}</span>
            </span>
            <button
              onClick={handleExitImpersonation}
              className="rounded border border-slate-950/25 bg-slate-950 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-amber-300 transition hover:bg-slate-900"
            >
              Exit View
            </button>
          </div>
        </div>
      )}

      {/* Premium KPI Dashboard */}
      <KPIDashboard 
        recommendationsCount={recs.length}
        averageScore={avgScore}
        signalsLoaded={allSignals.length}
        isLive={status?.supabase || false}
      />

      {/* Module Navigation */}
      <ModuleNavigation 
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isAdminMode={sessionUser?.role === "admin"}
      />

      {error && (
        <div className="mb-6 rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      {activeTab === "admin" && sessionUser?.role === "admin" && !impersonatedEmail ? (
        <AdminDashboard onImpersonate={handleImpersonateUser} />
      ) : activeTab === "alpha" && sessionUser?.role === "admin" && !impersonatedEmail ? (
        <AlphaAlerts userId={impersonatedId || sessionUser?.id || "default-trader-admin"} />
      ) : activeTab === "pennyscans" && sessionUser?.role === "admin" && !impersonatedEmail ? (
        <PennyScans />
      ) : activeTab === "mindmap" && sessionUser?.role === "admin" && !impersonatedEmail ? (
        <div className="w-full rounded-xl border border-slate-800 bg-slate-900/35 overflow-hidden shadow-2xl" style={{ height: "calc(100vh - 240px)", minHeight: "650px" }}>
          <iframe 
            src="/market_advisor_mindmap.html" 
            className="w-full h-full border-none"
            title="System Architecture Mind Map"
          />
        </div>
      ) : activeTab === "institutional" ? (
        <InstitutionalScanner />
      ) : activeTab === "scans" ? (
        permissions.can_view_recommendations === false ? (
          <LockedPanel title="Scanner Recommendations Locked" detail="Admin access rules hide recommendations for this profile." />
        ) : (
          <ScanWorkspace
            mode={mode}
            targetDate={targetDate}
            tradeDate={tradeDate}
            status={status}
            loading={loading}
            recs={recs}
            canViewHeatmap={permissions.can_view_heatmap !== false}
            emptyText={getEmptyStateText()}
            onChangeMode={setMode}
            onChangeTargetDate={setTargetDate}
            onComplete={load}
            onLoadingChange={setLoading}
            userId={impersonatedId || sessionUser?.id || "default-trader-admin"}
          />
        )
      ) : activeTab === "signals" ? (
        permissions.can_view_signals === false ? (
          <LockedPanel title="Signals Locked" detail="Momentum signals are disabled for this profile." />
        ) : (
          <section className="rounded-lg border border-slate-800 bg-slate-900/25 p-4 sm:p-5">
            <div className="mb-5 flex flex-col gap-4 border-b border-slate-800/80 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-lg font-bold tracking-tight text-white">{getSignalsTitle()}</h2>
              <div className="grid grid-cols-2 gap-1 rounded-md border border-slate-800 bg-slate-950 p-1">
                <SegmentButton active={signalTypeFilter === "buy"} onClick={() => setSignalTypeFilter("buy")}>
                  Buy
                </SegmentButton>
                <SegmentButton active={signalTypeFilter === "sell"} tone="red" onClick={() => setSignalTypeFilter("sell")}>
                  Sell
                </SegmentButton>
              </div>
            </div>
            <SignalList signals={filteredSignals} onBuyClick={handleBuyFromSignal} />
          </section>
        )
      ) : activeTab === "backtest" ? (
        permissions.can_backtest === false ? (
          <LockedPanel title="Backtest Locked" detail="Backtest Labs are disabled for this account." />
        ) : (
          <BacktestSimulator currentMode={mode} />
        )
      ) : activeTab === "chatbot" ? (
        permissions.can_use_chatbot !== true ? (
          <LockedPanel title="AI Advisor Locked" detail="AI portfolio advice is disabled by administrator rules." />
        ) : (
          <ChatbotAdvisor prefill={chatbotPrefill} onClearPrefill={() => setChatbotPrefill(null)} />
        )
      ) : permissions.can_use_portfolio === false ? (
        <LockedPanel title="Portfolio Locked" detail="Portfolio and watchlist tools are disabled for this account." />
      ) : (
        <UserWorkspace
          userId={impersonatedId || sessionUser?.id || undefined}
          userEmail={impersonatedEmail || sessionUser?.email || undefined}
          onAnalyzeHolding={handleAnalyzeHoldingFromPortfolio}
          onAnalyzeEntirePortfolio={handleAnalyzeEntirePortfolioFromPortfolio}
          canUseChatbot={permissions.can_use_chatbot === true}
        />
      )}

      {buyModalSymbol && (
        <BuyStockModal
          open={buyModalOpen}
          onCancel={() => setBuyModalOpen(false)}
          onSuccess={() => setBuyModalOpen(false)}
          symbol={buyModalSymbol}
          displaySymbol={buyModalSymbol.replace(".NS", "").replace(".BO", "")}
          defaultPrice={buyModalPrice}
          defaultTarget={buyModalTarget}
          defaultStopLoss={buyModalStop}
          userId={impersonatedId || sessionUser?.id || "default-trader-admin"}
        />
      )}
    </>
  );
}

function ScanWorkspace({
  mode,
  targetDate,
  tradeDate,
  status,
  loading,
  recs,
  canViewHeatmap,
  emptyText,
  onChangeMode,
  onChangeTargetDate,
  onComplete,
  onLoadingChange,
  userId,
}: {
  mode: TradeMode;
  targetDate: string;
  tradeDate: string | null;
  status: { supabase: boolean; huggingface: boolean } | null;
  loading: boolean;
  recs: Recommendation[];
  canViewHeatmap: boolean;
  emptyText: string;
  onChangeMode: (mode: TradeMode) => void;
  onChangeTargetDate: (date: string) => void;
  onComplete: () => void;
  onLoadingChange: (loading: boolean) => void;
  userId?: string;
}) {
  return (
    <>
      <section className="mb-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Analysis Mode</h2>
            <p className="text-sm text-slate-500">Pick horizon first. Results, signals, and backtests follow the same mode.</p>
          </div>
          {tradeDate && (
            <span className="text-xs font-medium text-slate-400">
              Trade date: <span className="text-slate-200">{tradeDate}</span>
            </span>
          )}
        </div>
        <ModeSelector
          activeMode={mode}
          onChangeMode={onChangeMode}
          targetDate={targetDate}
          onChangeTargetDate={onChangeTargetDate}
        />
      </section>

      <section className="mb-6 rounded-lg border border-slate-800 bg-slate-900/40 p-4 sm:p-5">
        <RunAnalysisButton
          mode={mode}
          targetDate={mode === "future" ? targetDate : undefined}
          onComplete={onComplete}
          onLoadingChange={onLoadingChange}
        />
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <StatusBadge ok={status?.supabase} label="Supabase" />
          <StatusBadge ok={status?.huggingface} label="Hugging Face" />
        </div>
      </section>

      {canViewHeatmap && !loading && recs.length > 0 && <SectorHeatmap recs={recs} />}

      <div className={`relative ${loading ? "pointer-events-none" : ""}`}>
        {loading && (
          <div className="absolute inset-0 z-10 flex min-h-[140px] items-center justify-center rounded-lg bg-slate-950/75 px-4 text-center backdrop-blur-sm">
            <p className="text-sm text-slate-300">Updating results when analysis finishes...</p>
          </div>
        )}
        {recs.length === 0 ? (
          <EmptyState title="No Picks Yet" detail={emptyText} />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {recs.map((rec) => (
              <RecommendationCard
                key={rec.id ?? `${rec.symbol}-${rec.rank}-${rec.trade_date}`}
                rec={rec}
                userId={userId}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function buildTabs({
  permissions,
  sessionUser,
  impersonatedEmail,
  onSelect,
}: {
  permissions: PermissionSet;
  sessionUser: SessionUser | null;
  impersonatedEmail: string | null;
  onSelect: (tab: DashboardTab) => void;
}) {
  const tabs: {
    id: DashboardTab;
    label: string;
    disabled?: boolean;
    activeClass: string;
    onSelect: (tab: DashboardTab) => void;
  }[] = [
    { id: "scans", label: "Scans", activeClass: "border-slate-200 bg-slate-100 text-slate-950", onSelect },
    {
      id: "signals",
      label: "Signals",
      disabled: permissions.can_view_signals === false,
      activeClass: "border-emerald-400/60 bg-emerald-950/70 text-emerald-200",
      onSelect,
    },
    {
      id: "backtest",
      label: "Backtest",
      disabled: permissions.can_backtest === false,
      activeClass: "border-sky-400/60 bg-sky-950/70 text-sky-200",
      onSelect,
    },
    {
      id: "portfolio",
      label: "Portfolio",
      disabled: permissions.can_use_portfolio === false,
      activeClass: "border-indigo-400/60 bg-indigo-950/70 text-indigo-200",
      onSelect,
    },
    {
      id: "chatbot",
      label: "AI Advisor",
      disabled: permissions.can_use_chatbot !== true,
      activeClass: "border-cyan-400/60 bg-cyan-950/70 text-cyan-100",
      onSelect,
    },
  ];

  if (sessionUser?.role === "admin" && !impersonatedEmail) {
    tabs.push(
      {
        id: "alpha",
        label: "⚡ Alpha",
        activeClass: "border-amber-400/70 bg-gradient-to-r from-amber-600 to-orange-600 text-white",
        onSelect,
      },
      {
        id: "pennyscans",
        label: "Penny Scans",
        activeClass: "border-amber-400/70 bg-amber-500 text-slate-950",
        onSelect,
      },
      {
        id: "mindmap",
        label: "Mind Map",
        activeClass: "border-violet-400/60 bg-violet-950/70 text-violet-100",
        onSelect,
      },
      {
        id: "admin",
        label: "Admin",
        activeClass: "border-fuchsia-400/60 bg-fuchsia-950/70 text-fuchsia-100",
        onSelect,
      }
    );
  }

  return tabs;
}

function normalizePermissions(value: Partial<PermissionSet> | null | undefined): PermissionSet {
  return { ...DEFAULT_PERMISSIONS, ...(value ?? {}) };
}

function SegmentButton({
  active,
  tone = "emerald",
  onClick,
  children,
}: {
  active: boolean;
  tone?: "emerald" | "red";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const activeClass = tone === "red" ? "bg-red-900/70 text-red-200" : "bg-emerald-900/70 text-emerald-200";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-3 py-2 text-xs font-bold transition ${
        active ? activeClass : "text-slate-500 hover:text-slate-300"
      }`}
    >
      {children}
    </button>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/45 px-4 py-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-black tracking-tight text-white">{value}</p>
    </div>
  );
}

function LockedPanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/35 p-6 text-center">
      <h2 className="text-base font-bold text-slate-200">{title}</h2>
      <p className="mt-2 text-sm text-slate-500">{detail}</p>
    </div>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-800 bg-slate-900/25 p-6">
      <h2 className="text-base font-bold text-slate-200">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{detail}</p>
    </div>
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
