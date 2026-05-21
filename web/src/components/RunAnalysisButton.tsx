"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getActiveAnalysisJob,
  startAnalysisJob,
  waitForAnalysisJob,
  type AnalysisJob,
} from "@/lib/api";

export function RunAnalysisButton({
  onComplete,
  onLoadingChange,
}: {
  onComplete?: () => void;
  onLoadingChange?: (loading: boolean) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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
          `Done — analyzed ${result?.stocks_analyzed ?? 0} stocks, ${result?.top_recommendations?.length ?? 10} buy picks for ${result?.trade_date ?? "tomorrow"}.`
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
    [onComplete]
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
    setLoading(true);
    onLoadingChange?.(true);
    setMessage(null);
    setJob(null);
    try {
      const started = await startAnalysisJob();
      if (started.status === "completed" && started.result) {
        const result = started.result;
        setMessage(
          `Done — analyzed ${result.stocks_analyzed ?? 0} stocks, ${result.top_recommendations?.length ?? 10} buy picks for ${result.trade_date ?? "tomorrow"}.`
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
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? "Analysis running…" : "Run daily analysis"}
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
              className="h-full rounded-full bg-emerald-500 transition-all duration-500 ease-out"
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
