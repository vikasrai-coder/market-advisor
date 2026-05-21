"use client";

import { useState } from "react";
import { runAnalysis } from "@/lib/api";

export function RunAnalysisButton({ onComplete }: { onComplete?: () => void }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setMessage(null);
    try {
      const result = await runAnalysis();
      setMessage(
        `Analyzed ${result.stocks_analyzed} stocks — ${(result.top_recommendations as unknown[])?.length ?? 10} buy picks for ${result.trade_date}.`
      );
      onComplete?.();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <button
        type="button"
        onClick={handleRun}
        disabled={loading}
        className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-60"
      >
        {loading ? "Running AI analysis…" : "Run daily analysis"}
      </button>
      {message && <p className="text-sm text-slate-400">{message}</p>}
    </div>
  );
}
