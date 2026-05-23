"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getActiveAnalysisJob,
  startAnalysisJob,
  waitForAnalysisJob,
  type AnalysisJob,
  type TradeMode,
} from "@/lib/api";

export function RunAnalysisButton({
  mode = "swing",
  targetDate,
  onComplete,
  onLoadingChange,
}: {
  mode?: TradeMode;
  targetDate?: string;
  onComplete?: () => void;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const getButtonLabel = () => {
    if (loading) return "Analysis running…";
    switch (mode) {
      case "intraday":
        return "Scan Intraday Signals (60m MACD)";
      case "longterm":
        return "Run Long-term Analysis (SMA 50/200)";
      case "future":
        return `Scan for Target Date (${targetDate || "Choose Date"})`;
      case "swing":
      default:
        return "Run Swing Trade Analysis";
    }
  };

  const getButtonColor = () => {
    switch (mode) {
      case "intraday":
        return "bg-sky-600 hover:bg-sky-500 shadow-sky-950/20";
      case "longterm":
        return "bg-purple-600 hover:bg-purple-500 shadow-purple-950/20";
      case "future":
        return "bg-amber-600 hover:bg-amber-500 shadow-amber-950/20";
      case "swing":
      default:
        return "bg-emerald-600 hover:bg-emerald-500 shadow-emerald-950/20";
    }
  };

  const pollJob = useCallback(
    async (jobId: string) => {
      setLoading(true);
      onLoadingChange?.(true);
      setMessage("Starting analysis…");
      try {
        const finalJob = await waitForAnalysisJob(jobId, (j) => {
          setJob(j);
          setMessage(j.message ?? "Running…");
        });
        const result = finalJob.result;
        setMessage(
          `Done — analyzed ${result?.stocks_analyzed ?? 0} stocks, ${result?.top_recommendations?.length ?? 10} buys for mode: ${mode}.`
        );
        onComplete?.();
      } catch (e) {
        setMessage(e instanceof Error ? e.message : "Analysis failed");
      } finally {
        setLoading(false);
        onLoadingChange?.(false);
        setJob(null);
      }
    },
    [onComplete, mode, onLoadingChange]
  );

  useEffect(() => {
    getActiveAnalysisJob()
      .then((active) => {
        if (active.status === "running" && active.job_id) {
          pollJob(active.job_id);
        }
      })
      .catch(() => {});
  }, [pollJob]);

  async function handleRun() {
    if (loading) return;
    if (mode === "future" && !targetDate) {
      setMessage("Please choose a target date first.");
      return;
    }
    setLoading(true);
    onLoadingChange?.(true);
    setMessage(null);
    setJob(null);
    try {
      const started = await startAnalysisJob(mode, targetDate);
      if (started.status === "completed" && started.result) {
        const result = started.result;
        setMessage(
          `Done — analyzed ${result.stocks_analyzed ?? 0} stocks, ${result.top_recommendations?.length ?? 10} buys for mode: ${mode}.`
        );
        onComplete?.();
        setLoading(false);
        onLoadingChange?.(false);
        return;
      }
      await pollJob(started.job_id);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not start analysis");
      setLoading(false);
      onLoadingChange?.(false);
    }
  }

  const progress = job?.progress ?? 0;

  return (
    <div className="flex flex-col gap-3 w-full">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={handleRun}
          disabled={loading}
          className={`rounded-lg px-5 py-2.5 text-sm font-semibold text-white shadow transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed ${getButtonColor()}`}
        >
          {getButtonLabel()}
        </button>
        {loading && (
          <span className="text-sm text-slate-400">
            ~1–3 min for 90 stocks — you can keep this tab open
          </span>
        )}
      </div>

      {loading && (
        <div className="w-full max-w-xl">
          <div className="mb-1 flex justify-between text-xs text-slate-500">
            <span>{message ?? "Working…"}</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${
                mode === "intraday"
                  ? "bg-sky-500"
                  : mode === "longterm"
                  ? "bg-purple-500"
                  : mode === "future"
                  ? "bg-amber-500"
                  : "bg-emerald-500"
              }`}
              style={{ width: `${Math.max(progress, 5)}%` }}
            />
          </div>
        </div>
      )}

      {!loading && message && (
        <p className="text-sm text-slate-400">{message}</p>
      )}
    </div>
  );
}
