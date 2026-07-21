import React, { useState, useEffect } from "react";
import { runBacktest, BacktestResponse, TradeMode } from "../lib/api";
import { createClient } from "../lib/supabase/client";

interface SavedRun {
  id: string;
  timestamp: string;
  mode: TradeMode;
  startDate: string;
  duration: number;
  winRate: number;
  metrics: any;
  response?: BacktestResponse;
}

interface BacktestSimulatorProps {
  currentMode: TradeMode;
}

export default function BacktestSimulator({ currentMode }: BacktestSimulatorProps) {
  const [startDate, setStartDate] = useState<string>(() => {
    // Default to 10 days ago
    const d = new Date();
    d.setDate(d.getDate() - 10);
    return d.toISOString().split("T")[0];
  });
  const [duration, setDuration] = useState<number>(5);
  const [loading, setLoading] = useState<boolean>(false);
  const [response, setResponse] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const [history, setHistory] = useState<SavedRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  // Load history from Supabase on mount
  useEffect(() => {
    async function fetchHistory() {
      try {
        const supabase = createClient();
        const { data: runs, error: runsError } = await supabase
          .from("backtest_runs")
          .select("*")
          .order("created_at", { ascending: false });

        if (runsError) throw runsError;

        if (runs && runs.length > 0) {
          const formattedHistory: SavedRun[] = runs.map(run => ({
            id: run.id,
            timestamp: new Date(run.created_at).toLocaleString("en-IN"),
            mode: run.mode as TradeMode,
            startDate: run.start_date,
            duration: run.check_days,
            winRate: parseFloat(run.win_rate),
            metrics: {
              win_rate: parseFloat(run.win_rate),
              avg_return: parseFloat(run.avg_return),
              total_picks: run.total_picks,
              target_hits: run.target_hits,
              stop_hits: run.stop_hits,
              held: run.held,
              index_return: parseFloat(run.index_return),
              outperformance: parseFloat(run.outperformance)
            }
          }));

          setHistory(formattedHistory);
        } else {
          // Fallback to backend API
          const { getBacktestHistory } = await import("../lib/api");
          const apiRes = await getBacktestHistory(10);
          if (apiRes.history && apiRes.history.length > 0) {
            setHistory(apiRes.history.map(run => ({
              id: run.id,
              timestamp: new Date(run.created_at).toLocaleString("en-IN"),
              mode: run.mode,
              startDate: run.start_date,
              duration: run.check_days,
              winRate: run.win_rate,
              metrics: {
                win_rate: run.win_rate,
                avg_return: run.avg_return_pct,
                total_picks: run.total_picks,
                target_hits: run.target_hits,
                stop_hits: run.stopped_outs,
                held: 0,
                index_return: 0,
                outperformance: 0
              }
            })));
          }
        }
      } catch (err) {
        console.error("Failed to load backtest history:", err);
      }
    }
    fetchHistory();
  }, []);

  async function handleSelectRun(run: SavedRun) {
    setActiveRunId(run.id);
    setStartDate(run.startDate);
    setDuration(run.duration);

    if (run.response) {
      setResponse(run.response);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data: results, error: resultsError } = await supabase
        .from("backtest_results")
        .select("*")
        .eq("run_id", run.id)
        .order("rank", { ascending: true });

      if (resultsError) throw resultsError;

      const fullResponse: BacktestResponse = {
        mode: run.mode,
        start_date: run.startDate,
        check_days: run.duration,
        metrics: run.metrics,
        results: (results || []).map(r => ({
          rank: r.rank,
          symbol: r.symbol,
          display_symbol: r.symbol.replace(".NS", ""),
          name: r.name,
          sector: r.sector,
          is_undervalued: r.is_undervalued,
          composite_score: parseFloat(r.composite_score),
          rsi: r.rsi ? parseFloat(r.rsi) : null,
          macd: r.macd ? parseFloat(r.macd) : null,
          entry_price: parseFloat(r.entry_price),
          target_price: parseFloat(r.target_price),
          stop_loss: parseFloat(r.stop_loss),
          exit_price: parseFloat(r.exit_price),
          exit_date: r.exit_date,
          return_pct: parseFloat(r.return_pct),
          outcome: r.outcome as any
        })),
        errors: []
      };

      setHistory(prev => prev.map(item => item.id === run.id ? { ...item, response: fullResponse } : item));
      setResponse(fullResponse);
    } catch (err: any) {
      console.error("Failed to load details from Supabase:", err);
      setError("Failed to load details for the selected run.");
    } finally {
      setLoading(false);
    }
  }

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runBacktest(currentMode, startDate, duration);
      setResponse(res);

      const supabase = createClient();

      // Check if a run with the exact same parameters already exists.
      // If yes, delete it first to save and replace/overwrite.
      const { data: existingRuns } = await supabase
        .from("backtest_runs")
        .select("id")
        .eq("mode", currentMode)
        .eq("start_date", startDate)
        .eq("check_days", duration);

      if (existingRuns && existingRuns.length > 0) {
        const idsToDelete = existingRuns.map(r => r.id);
        await supabase
          .from("backtest_runs")
          .delete()
          .in("id", idsToDelete);

        // Remove from local history state
        setHistory(prev => prev.filter(item => !idsToDelete.includes(item.id)));
      }

      // 1. Insert the main run record
      const { data: runData, error: runError } = await supabase
        .from("backtest_runs")
        .insert({
          mode: currentMode,
          start_date: startDate,
          check_days: duration,
          win_rate: res.metrics.win_rate,
          avg_return: res.metrics.avg_return,
          total_picks: res.metrics.total_picks,
          target_hits: res.metrics.target_hits,
          stop_hits: res.metrics.stop_hits,
          held: res.metrics.held,
          index_return: res.metrics.index_return,
          outperformance: res.metrics.outperformance
        })
        .select()
        .single();

      if (runError) throw runError;

      // 2. Insert the sub-records of simulated stock trades
      if (runData && res.results.length > 0) {
        const resultsToInsert = res.results.map(stock => ({
          run_id: runData.id,
          rank: stock.rank,
          symbol: stock.symbol,
          name: stock.name,
          sector: stock.sector,
          is_undervalued: stock.is_undervalued,
          composite_score: stock.composite_score,
          rsi: stock.rsi || 50,
          macd: stock.macd || 0,
          entry_price: stock.entry_price,
          target_price: stock.target_price,
          stop_loss: stock.stop_loss,
          exit_price: stock.exit_price,
          exit_date: stock.exit_date,
          return_pct: stock.return_pct,
          outcome: stock.outcome
        }));

        const { error: resultsError } = await supabase
          .from("backtest_results")
          .insert(resultsToInsert);

        if (resultsError) throw resultsError;

        // Append this run to local active state
        const newRun: SavedRun = {
          id: runData.id,
          timestamp: new Date(runData.created_at).toLocaleString("en-IN"),
          mode: currentMode,
          startDate,
          duration,
          winRate: res.metrics.win_rate,
          metrics: res.metrics,
          response: res
        };

        setHistory(prev => [newRun, ...prev]);
        setActiveRunId(runData.id);
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Simulation failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteRun = async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this simulation run from database?")) return;
    try {
      const supabase = createClient();
      const { error: deleteError } = await supabase
        .from("backtest_runs")
        .delete()
        .eq("id", runId);

      if (deleteError) throw deleteError;

      const nextHistory = history.filter(r => r.id !== runId);
      setHistory(nextHistory);
      if (activeRunId === runId) {
        if (nextHistory.length > 0) {
          handleSelectRun(nextHistory[0]);
        } else {
          setActiveRunId(null);
          setResponse(null);
        }
      }
    } catch (err) {
      console.error("Failed to delete run from Supabase:", err);
      alert("Failed to delete simulation run.");
    }
  };

  const handleClearAll = async () => {
    if (!confirm("Are you sure you want to clear all simulation history from database?")) return;
    try {
      const supabase = createClient();
      const { error: clearError } = await supabase
        .from("backtest_runs")
        .delete()
        .neq("id", "00000000-0000-0000-0000-000000000000");

      if (clearError) throw clearError;

      setHistory([]);
      setActiveRunId(null);
      setResponse(null);
    } catch (err) {
      console.error("Failed to clear history from Supabase:", err);
      alert("Failed to clear simulation history.");
    }
  };

  const todayStr = new Date().toISOString().split("T")[0];

  // Helper for win rate colors
  const getWinRateColor = (winRate: number) => {
    if (winRate >= 70) return "text-emerald-400";
    if (winRate >= 50) return "text-amber-400";
    return "text-rose-400";
  };

  const getWinRateStrokeColor = (winRate: number) => {
    if (winRate >= 70) return "#34d399"; // emerald-400
    if (winRate >= 50) return "#fbbf24"; // amber-400
    return "#f87171"; // rose-400
  };

  // Radial progress calculations
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const winRate = response?.metrics.win_rate ?? 0;
  const strokeDashoffset = circumference - (winRate / 100) * circumference;

  return (
    <div className="w-full mb-8 rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl shadow-2xl overflow-hidden transition-all duration-300">
      {/* Header */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between p-6 cursor-pointer border-b border-slate-900/60 hover:bg-slate-900/20 transition-all duration-200"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/25 shadow-[0_0_15px_rgba(168,85,247,0.15)]">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 10.44l-1.205 1.253a.75.75 0 000 1.071l4.07 4.207a.75.75 0 001.07 0l9.263-9.588a.75.75 0 000-1.07L21 5.07a.75.75 0 00-1.07 0L11.5 13.56l-2.5-2.5-1.205-1.253a.75.75 0 00-1.07 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100 tracking-wide flex items-center gap-2">
              📊 Quantitative Backtest Simulator
              <span className="px-2 py-0.5 text-xs font-semibold uppercase tracking-wider rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                Labs
              </span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Test historical scanning algorithms relative to past starting dates & evaluate target / stop-loss win rates.
            </p>
          </div>
        </div>
        <button className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded-lg bg-slate-900/40 hover:bg-slate-900 border border-slate-800">
          <svg
            className={`w-5 h-5 transform transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Expanded simulator control panel */}
      {isExpanded && (
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-end border-b border-slate-900/60 pb-6 mb-6">
            {/* Start date selection */}
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                📅 Backtest Start Date
              </label>
              <input
                type="date"
                max={todayStr}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:ring-1 focus:ring-purple-500/50 transition-all duration-200"
              />
            </div>

            {/* Hold duration slider */}
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  ⏳ Hold Duration
                </label>
                <span className="text-xs font-semibold text-purple-400">
                  {duration} Trading Days
                </span>
              </div>
              <div className="flex items-center gap-4 bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2 h-[42px]">
                <input
                  type="range"
                  min="5"
                  max="20"
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value))}
                  className="flex-1 accent-purple-500 bg-slate-800 h-1 rounded-lg cursor-pointer"
                />
                <span className="text-xs text-slate-400 w-4 text-right">{duration}d</span>
              </div>
            </div>

            {/* Action button */}
            <button
              onClick={handleSimulate}
              disabled={loading}
              className="w-full h-[42px] bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:from-purple-800/40 disabled:to-indigo-800/40 text-slate-100 hover:text-white font-bold rounded-xl flex items-center justify-center gap-2 border border-purple-500/20 shadow-[0_4px_20px_rgba(168,85,247,0.25)] hover:shadow-[0_4px_25px_rgba(168,85,247,0.4)] disabled:shadow-none transition-all duration-200"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Crunching historical data...</span>
                </>
              ) : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25v13.5m-7.5-13.5v13.5" />
                  </svg>
                  <span>Simulate Historical Scan</span>
                </>
              )}
            </button>
          </div>

          {/* History Panel */}
          {history.length > 0 && (
            <div className="mb-6 p-4 rounded-2xl border border-slate-900 bg-slate-900/10">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  📚 Saved Simulations History ({history.length})
                </span>
                <button
                  onClick={handleClearAll}
                  className="text-[10px] text-rose-400 hover:text-rose-300 font-bold uppercase tracking-wider transition-colors"
                >
                  Clear All
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[160px] overflow-y-auto pr-1">
                {history.map((run) => {
                  const isActive = activeRunId === run.id;
                  const runWinRate = run.winRate;
                  return (
                    <div
                      key={run.id}
                      onClick={() => handleSelectRun(run)}
                      className={`relative flex items-center justify-between p-3 rounded-xl border cursor-pointer transition-all duration-200 group ${isActive
                          ? "bg-purple-500/10 border-purple-500/40 text-slate-100 shadow-[0_0_12px_rgba(168,85,247,0.1)]"
                          : "bg-slate-900/40 border-slate-900/60 hover:bg-slate-900/80 hover:border-slate-800 text-slate-300"
                        }`}
                    >
                      <div className="flex flex-col gap-0.5 select-none text-left">
                        <span className="text-xs font-bold tracking-wide flex items-center gap-1.5">
                          {run.startDate} ({run.duration}d)
                          <span className={`text-[10px] font-black ${runWinRate >= 70 ? "text-emerald-400" : runWinRate >= 50 ? "text-amber-400" : "text-rose-400"
                            }`}>
                            {runWinRate}%
                          </span>
                        </span>
                        <span className="text-[9px] text-slate-500">
                          {run.timestamp} • {run.mode}
                        </span>
                      </div>

                      <button
                        onClick={(e) => handleDeleteRun(e, run.id)}
                        className="p-1 rounded-md text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-150"
                        title="Delete run"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-400 text-sm flex items-center gap-3 animate-pulse">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 flex-shrink-0">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {/* Results dashboard block */}
          {response && !loading && (
            <div className="space-y-8 animate-fadeIn">
              {/* Scoreboard metric grid */}
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

                {/* 1. Win Rate Radial Ring */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-6 flex flex-col items-center justify-center relative overflow-hidden group">
                  <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent pointer-events-none" />
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 z-10">
                    🏆 Simulation Win Rate
                  </span>
                  <div className="relative flex items-center justify-center z-10">
                    <svg className="w-32 h-32 transform -rotate-90">
                      {/* Background circle */}
                      <circle
                        cx="64"
                        cy="64"
                        r={radius}
                        className="text-slate-800"
                        strokeWidth="10"
                        fill="transparent"
                        stroke="currentColor"
                      />
                      {/* Glowing Ring */}
                      <circle
                        cx="64"
                        cy="64"
                        r={radius}
                        stroke={getWinRateStrokeColor(winRate)}
                        strokeWidth="10"
                        fill="transparent"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        strokeLinecap="round"
                        style={{ transition: "stroke-dashoffset 0.8s ease" }}
                      />
                    </svg>
                    <div className="absolute flex flex-col items-center">
                      <span className={`text-2xl font-black ${getWinRateColor(winRate)} tracking-tight`}>
                        {winRate}%
                      </span>
                      <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wide">
                        Win rate
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. Average Return */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden group">
                  <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent pointer-events-none" />
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      📈 Average Return
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Performance
                    </span>
                  </div>
                  <div className="my-4">
                    <span className={`text-4xl font-extrabold tracking-tight ${response.metrics.avg_return >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {response.metrics.avg_return >= 0 ? "+" : ""}{response.metrics.avg_return}%
                    </span>
                    <p className="text-xs text-slate-500 mt-2 font-medium">
                      Mean return across top picks evaluated over subsequent {duration} trading sessions.
                    </p>
                  </div>
                  <div className="w-full bg-slate-950/80 rounded-lg p-2 flex justify-between text-xs border border-slate-900/50">
                    <span className="text-slate-400 font-medium">Total Picks:</span>
                    <span className="text-slate-200 font-bold">{response.metrics.total_picks} stocks</span>
                  </div>
                </div>

                {/* 3. Outcomes Tally */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent pointer-events-none" />
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      📊 Outcomes Breakdown
                    </span>
                    <div className="space-y-3 my-4">
                      {/* Target Hits */}
                      <div className="flex justify-between items-center text-sm border-b border-slate-900/40 pb-2">
                        <span className="flex items-center gap-2 text-slate-300 font-medium">
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]" />
                          Target Hits
                        </span>
                        <span className="font-bold text-emerald-400">{response.metrics.target_hits}</span>
                      </div>
                      {/* Stop Hits */}
                      <div className="flex justify-between items-center text-sm border-b border-slate-900/40 pb-2">
                        <span className="flex items-center gap-2 text-slate-300 font-medium">
                          <span className="w-2.5 h-2.5 rounded-full bg-rose-400 shadow-[0_0_10px_rgba(248,113,113,0.5)]" />
                          Stop Hits
                        </span>
                        <span className="font-bold text-rose-400">{response.metrics.stop_hits}</span>
                      </div>
                      {/* Active/Held */}
                      <div className="flex justify-between items-center text-sm">
                        <span className="flex items-center gap-2 text-slate-300 font-medium">
                          <span className="w-2.5 h-2.5 rounded-full bg-slate-500" />
                          Held at End
                        </span>
                        <span className="font-bold text-slate-300">{response.metrics.held}</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-[10px] text-slate-500 leading-tight">
                    *Stop Hits are evaluated conservatively (hit stops before targets if both occur).
                  </div>
                </div>

                {/* 4. Index Benchmarking */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-2xl p-6 flex flex-col justify-between relative overflow-hidden group">
                  <div className="absolute inset-0 bg-gradient-to-br from-yellow-500/5 to-transparent pointer-events-none" />
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      ⚖️ vs Nifty 50 Index
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                      Benchmark
                    </span>
                  </div>
                  <div className="my-4">
                    <span className={`text-4xl font-extrabold tracking-tight ${response.metrics.outperformance >= 0 ? "text-amber-400" : "text-rose-400"}`}>
                      {response.metrics.outperformance >= 0 ? "+" : ""}{response.metrics.outperformance}%
                    </span>
                    <p className="text-xs text-slate-500 mt-2 font-medium">
                      Simulated outperformance compared against Nifty 50 Index return of {response.metrics.index_return}% over the same period.
                    </p>
                  </div>
                  <div className={`w-full rounded-lg p-2.5 flex items-center justify-center text-xs font-bold border ${response.metrics.outperformance >= 0
                      ? "bg-amber-500/10 border-amber-500/25 text-amber-400"
                      : "bg-rose-500/10 border-rose-500/25 text-rose-400"
                    }`}>
                    {response.metrics.outperformance >= 0 ? "🔥 Outperforming Benchmark" : "⚠️ Lagging Benchmark"}
                  </div>
                </div>

              </div>

              {/* Simulated Stocks Outcomes table */}
              <div className="bg-slate-900/10 border border-slate-900 rounded-2xl overflow-hidden shadow-xl">
                <div className="p-5 border-b border-slate-900/60 bg-slate-900/25">
                  <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                    📈 Simulated Recommendation Trades & Outcomes
                  </h4>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-900 text-slate-400 text-xs uppercase tracking-wider bg-slate-900/10">
                        <th className="py-4 px-5 font-bold">Rank</th>
                        <th className="py-4 px-5 font-bold">Symbol</th>
                        <th className="py-4 px-5 font-bold">Entry Price</th>
                        <th className="py-4 px-5 font-bold">Target / Stop</th>
                        <th className="py-4 px-5 font-bold">Exit Price / Date</th>
                        <th className="py-4 px-5 font-bold">Status</th>
                        <th className="py-4 px-5 font-bold text-right">Return (%)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/40 text-slate-300 text-sm">
                      {response.results.map((res) => (
                        <tr key={res.symbol} className="hover:bg-slate-900/20 transition-all duration-150">
                          <td className="py-4 px-5 font-bold text-slate-400">#{res.rank}</td>
                          <td className="py-4 px-5">
                            <div className="flex flex-col">
                              <span className="font-extrabold text-slate-100 flex items-center gap-1.5">
                                {res.display_symbol}
                                {res.is_undervalued && (
                                  <span className="px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 shadow-[0_0_8px_rgba(234,179,8,0.15)] animate-pulse">
                                    🔥 UnderValued
                                  </span>
                                )}
                              </span>
                              <span className="text-[10px] text-slate-500 truncate max-w-[160px]">
                                {res.name} • {res.sector || "Unclassified"}
                              </span>
                            </div>
                          </td>
                          <td className="py-4 px-5 font-extrabold text-slate-200">
                            ₹{res.entry_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-4 px-5">
                            <div className="flex flex-col text-xs space-y-0.5">
                              <span className="text-emerald-400 font-bold">
                                T: ₹{res.target_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                              </span>
                              <span className="text-rose-400 font-bold">
                                S: ₹{res.stop_loss.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                          </td>
                          <td className="py-4 px-5">
                            <div className="flex flex-col">
                              <span className="font-bold text-slate-200">
                                ₹{res.exit_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                              </span>
                              {res.exit_date && (
                                <span className="text-[10px] text-slate-500 font-medium">
                                  {res.exit_date}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-4 px-5">
                            {res.outcome === "target_hit" && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-black uppercase tracking-wide rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 shadow-[0_0_12px_rgba(52,211,153,0.15)]">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                                Target Hit
                              </span>
                            )}
                            {res.outcome === "stopped_out" && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-black uppercase tracking-wide rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/25 shadow-[0_0_12px_rgba(248,113,113,0.15)]">
                                <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                                Stopped Out
                              </span>
                            )}
                            {res.outcome === "held" && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-black uppercase tracking-wide rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/25">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                                Held {duration}d
                              </span>
                            )}
                            {res.outcome === "insufficient_data" && (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-black uppercase tracking-wide rounded-full bg-slate-800 text-slate-500 border border-slate-700/50">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                                Pending
                              </span>
                            )}
                          </td>
                          <td className={`py-4 px-5 text-right font-black ${res.return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                            {res.return_pct >= 0 ? "+" : ""}{res.return_pct}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Empty State when no response loaded */}
          {!response && !loading && (
            <div className="py-12 border border-dashed border-slate-900 rounded-2xl flex flex-col items-center justify-center text-center">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10 text-slate-600 mb-3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />
              </svg>
              <h5 className="text-sm font-bold text-slate-400">No simulation data loaded</h5>
              <p className="text-xs text-slate-500 max-w-sm mt-1">
                Select a start date in the past and duration to run the historical indicator performance simulation.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
