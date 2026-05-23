"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRecommendations,
  getSignals,
  healthCheck,
  type Recommendation,
  type TradingSignal,
  type TradeMode,
} from "@/lib/api";
import { RecommendationCard } from "./RecommendationCard";
import { RunAnalysisButton } from "./RunAnalysisButton";
import { SignalList } from "./SignalList";
import { ModeSelector } from "./ModeSelector";

export function Dashboard() {
  const [mode, setMode] = useState<TradeMode>("swing");
  const [targetDate, setTargetDate] = useState<string>(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split("T")[0];
  });
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [tradeDate, setTradeDate] = useState<string | null>(null);
  const [status, setStatus] = useState<{ supabase: boolean; huggingface: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      setSignals((sigData.signals ?? []).filter((s) => s.signal_type === "buy").slice(0, 10));
      if (health) setStatus({ supabase: health.supabase, huggingface: health.huggingface });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data — is the API running?");
    }
  }, [mode, targetDate]);

  useEffect(() => {
    load();
  }, [load]);

  const getSignalsTitle = () => {
    switch (mode) {
      case "intraday":
        return "Buy signals (plan same-day entry)";
      case "longterm":
        return "Buy signals (plan 1-6 month holds)";
      case "future":
        return `Buy signals (planned setups for ${targetDate})`;
      case "swing":
      default:
        return "Buy signals (plan for next session)";
    }
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

  return (
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

      {error && (
        <div className="mb-6 rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      <div className={`relative ${loading ? "pointer-events-none" : ""}`}>
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-slate-950/70 backdrop-blur-sm min-h-[120px]">
            <p className="text-sm text-slate-300">Updating results when analysis finishes…</p>
          </div>
        )}
        {recs.length === 0 && !error ? (
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

      <section className="mt-12">
        <h2 className="mb-4 text-xl font-semibold text-white">{getSignalsTitle()}</h2>
        <SignalList signals={signals} />
      </section>
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
