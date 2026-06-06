"use client";

import React, { useState, useEffect } from "react";
import { adminGetPennyScans, type PennyScanItem } from "@/lib/api";

export default function PennyScans() {
  const [items, setItems] = useState<PennyScanItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadPennyScans = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminGetPennyScans();
      setItems(data.penny_scans || []);
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Failed to load admin penny scans. Make sure you are logged in as admin and API is active.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPennyScans();
  }, []);

  // Compute breakdown stats
  const intradayCount = items.filter(x => x.recommendation.toLowerCase().includes("intraday")).length;
  const swingCount = items.length - intradayCount;

  return (
    <div className="space-y-8 animate-fadeIn mb-12 mt-4">
      {/* 1. Header Hero Area */}
      <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 md:p-8 shadow-2xl relative overflow-hidden group">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-600/10 via-indigo-600/5 to-transparent pointer-events-none" />
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.5)] animate-pulse" />
              <span className="text-[10px] font-black tracking-widest text-purple-400 uppercase">Admin Proprietary Access Only</span>
            </div>
            <h2 className="text-2xl font-black text-slate-100 mt-2 tracking-wide flex items-center gap-2">
              🪙 Penny Swing & Intraday Scans
            </h2>
            <p className="text-xs text-slate-400 mt-1 max-w-xl leading-relaxed">
              Scan low-ticket equity assets priced strictly **below Rs. 150** on the NSE. Tracks volume anomalies, hourly breakout RSI cycles, and generates targeted daily profit-taking setups.
            </p>
          </div>

          <div className="flex gap-3 shrink-0">
            <button
              onClick={loadPennyScans}
              disabled={loading}
              className="h-10 px-5 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-900 text-white font-extrabold rounded-xl text-xs flex items-center justify-center gap-2 border border-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.2)] hover:shadow-[0_0_20px_rgba(168,85,247,0.35)] transition-all cursor-pointer disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Scanning NSE...</span>
                </>
              ) : (
                <>
                  <span>🔄 Re-Scan Watchlist</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Breakdown dashboard stats */}
        {!loading && items.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-slate-900/60">
            <div className="bg-slate-900/20 border border-slate-900/60 p-4 rounded-2xl">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Total Penny Assets Scanned</span>
              <span className="text-xl font-extrabold text-slate-200 mt-1 block">{items.length} Stocks</span>
            </div>
            <div className="bg-slate-900/20 border border-slate-900/60 p-4 rounded-2xl">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Intraday Scalps Today (Exit Today)</span>
              <span className="text-xl font-extrabold text-emerald-400 mt-1 block">{intradayCount} High-Momentum</span>
            </div>
            <div className="bg-slate-900/20 border border-slate-900/60 p-4 rounded-2xl">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Swing Holds (Exit Tomorrow)</span>
              <span className="text-xl font-extrabold text-purple-400 mt-1 block">{swingCount} Breakouts</span>
            </div>
          </div>
        )}
      </div>

      {/* 2. Scanning Results Grid / Table */}
      {error && (
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4 text-xs text-rose-300 animate-pulse text-center">
          ⚠️ {error}
        </div>
      )}

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center gap-4 text-slate-400 text-xs">
          <svg className="animate-spin h-8 w-8 text-purple-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="animate-pulse">Loading live indicators & pricing from NSE databases...</span>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-slate-900 bg-slate-950/40 p-12 text-center text-xs text-slate-500">
          No low-ticket stock listings found under Rs. 150.
        </div>
      ) : (
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent pointer-events-none" />
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[900px]">
              <thead>
                <tr className="border-b border-slate-900 text-slate-500 text-[10px] uppercase tracking-wider bg-slate-900/15">
                  <th className="py-3 px-4 font-bold">Stock Asset</th>
                  <th className="py-3 px-4 font-bold text-right">Live Price</th>
                  <th className="py-3 px-4 font-bold text-right">RSI (5D)</th>
                  <th className="py-3 px-4 font-bold text-right">Recommended Entry</th>
                  <th className="py-3 px-4 font-bold text-right text-emerald-400">Exit Point (Today)</th>
                  <th className="py-3 px-4 font-bold text-right text-purple-400">Exit Point (Tomorrow)</th>
                  <th className="py-3 px-4 font-bold text-right text-rose-400">Stop-Loss</th>
                  <th className="py-3 px-4 font-bold">Trade Classification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                {items.map((hold) => (
                  <React.Fragment key={hold.symbol}>
                    {/* Data Row */}
                    <tr className="hover:bg-slate-900/10 transition-colors group/row">
                      <td className="py-3.5 px-4 font-extrabold text-slate-200">
                        <div className="flex flex-col">
                          <span className="text-sm font-black text-slate-100">{hold.display_symbol}</span>
                          <span className="text-[10px] text-slate-500">{hold.name}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <span className="font-extrabold text-slate-200 block">₹{hold.price.toFixed(2)}</span>
                        <span className={`text-[9px] font-bold ${hold.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {hold.change_pct >= 0 ? "+" : ""}{hold.change_pct.toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right font-bold text-slate-400">{hold.rsi.toFixed(1)}</td>
                      <td className="py-3.5 px-4 text-right font-bold">₹{hold.entry.toFixed(2)}</td>
                      <td className="py-3.5 px-4 text-right font-black text-emerald-400/90 bg-emerald-500/5">₹{hold.exit_today.toFixed(2)}</td>
                      <td className="py-3.5 px-4 text-right font-black text-purple-400/90 bg-purple-500/5">₹{hold.exit_tomorrow.toFixed(2)}</td>
                      <td className="py-3.5 px-4 text-right font-bold text-rose-400/80">₹{hold.stop_loss.toFixed(2)}</td>
                      <td className="py-3.5 px-4">
                        {hold.recommendation.toLowerCase().includes("intraday") ? (
                          <span className="px-2 py-0.5 rounded text-[8px] font-black tracking-wide uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            ⚡ Intraday Scalp
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[8px] font-black tracking-wide uppercase bg-purple-500/10 text-purple-400 border border-purple-500/20">
                            📈 Overnight Swing
                          </span>
                        )}
                      </td>
                    </tr>
                    {/* Rationale/AI Verdict Sub-Row */}
                    <tr className="bg-slate-900/5 select-none border-b border-slate-900/40">
                      <td colSpan={8} className="py-2.5 px-6">
                        <div className="flex gap-2 items-start text-[10px] text-slate-400 max-w-4xl leading-relaxed">
                          <span className="font-extrabold uppercase text-purple-400 shrink-0 select-none">AI Verdict:</span>
                          <span>{hold.verdict}</span>
                        </div>
                      </td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. Operational Financial Disclaimer */}
      <div className="my-4 p-4 border border-rose-500/20 bg-rose-950/15 text-rose-300 rounded-2xl text-[11px] leading-relaxed shadow-[0_0_15px_rgba(239,68,68,0.05)] border-l-4 border-l-rose-500 select-none">
        <span className="font-extrabold block text-rose-400 uppercase tracking-wider mb-1">⚠️ Admin Strategic Disclaimer</span>
        All low-ticket scanners operate on standard technical indicators. Scans priced below Rs. 150 are subject to rapid price volatility, order imbalances, and sudden volume gaps. Strictly execute stops and manage risks dynamically. Recommendations are educational and do not constitute absolute guarantees.
      </div>
    </div>
  );
}
