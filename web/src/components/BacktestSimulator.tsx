import React, { useState } from "react";
import { runBacktest, BacktestResponse, TradeMode } from "../lib/api";

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

  const handleSimulate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runBacktest(currentMode, startDate, duration);
      setResponse(res);
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Simulation failed. Please try again.");
    } finally {
      setLoading(false);
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
                  <div className={`w-full rounded-lg p-2.5 flex items-center justify-center text-xs font-bold border ${
                    response.metrics.outperformance >= 0 
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
