"use client";

import { useCallback, useEffect, useState } from "react";
import { getRecommendations, getSignals, healthCheck, type Recommendation, type TradingSignal } from "@/lib/api";
import { RecommendationCard } from "./RecommendationCard";
import { RunAnalysisButton } from "./RunAnalysisButton";
import { SignalList } from "./SignalList";

export function Dashboard() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [tradeDate, setTradeDate] = useState<string | null>(null);
  const [status, setStatus] = useState<{ supabase: boolean; huggingface: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [recData, sigData, health] = await Promise.all([
        getRecommendations(),
        getSignals(),
        healthCheck().catch(() => null),
      ]);
      setRecs(recData.recommendations ?? []);
      setTradeDate(recData.trade_date ?? null);
      setSignals((sigData.signals ?? []).filter((s) => s.signal_type === "buy").slice(0, 10));
      if (health) setStatus({ supabase: health.supabase, huggingface: health.huggingface });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data — is the API running?");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <section className="mb-8 flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <RunAnalysisButton onComplete={load} />
        <div className="flex flex-wrap gap-3 text-xs">
          <StatusBadge ok={status?.supabase} label="Supabase" />
          <StatusBadge ok={status?.huggingface} label="Hugging Face" />
          {tradeDate && (
            <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-400">
              Trade plan date: {tradeDate}
            </span>
          )}
        </div>
      </section>

      {error && (
        <div className="mb-6 rounded-lg border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {error}
        </div>
      )}

      {recs.length === 0 && !error ? (
        <p className="text-slate-500">
          No recommendations yet. Click &quot;Run daily analysis&quot; to score 40 stocks and get 10 buy picks.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {recs.map((rec) => (
            <RecommendationCard key={rec.id} rec={rec} />
          ))}
        </div>
      )}

      <section className="mt-12">
        <h2 className="mb-4 text-xl font-semibold text-white">Buy signals (plan for next session)</h2>
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
