import React, { useState, useEffect, useCallback } from "react";
import {
  getUserWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  getUserPortfolio,
  buyHolding,
  sellHolding,
  syncWatchlist,
  UserWatchlistItem,
  UserPortfolioItem,
  UserPortfolioResponse,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

export default function UserWorkspace() {
  const [userId, setUserId] = useState<string>("default-trader-admin");
  const [watchlist, setWatchlist] = useState<UserWatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<UserPortfolioResponse | null>(null);
  
  // Watchlist Input
  const [newSymbol, setNewSymbol] = useState<string>("");
  const [watchlistLoading, setWatchlistLoading] = useState<boolean>(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  // Portfolio Transaction Inputs
  const [buySymbol, setBuySymbol] = useState<string>("");
  const [buyQty, setBuyQty] = useState<number>(0);
  const [buyPriceInput, setBuyPriceInput] = useState<number>(0);
  const [portfolioLoading, setPortfolioLoading] = useState<boolean>(false);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  // Sync state
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncStatus, setSyncStatus] = useState<any>(null);

  // Load user session if available
  useEffect(() => {
    async function checkUser() {
      try {
        const supabase = createClient();
        const { data } = await supabase.auth.getUser();
        if (data?.user?.id) {
          setUserId(data.user.id);
        }
      } catch (err) {
        // Fallback to default
      }
    }
    checkUser();
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [watchData, portData] = await Promise.all([
        getUserWatchlist(userId),
        getUserPortfolio(userId),
      ]);
      setWatchlist(watchData.watchlist ?? []);
      setPortfolio(portData);
    } catch (err) {
      console.error("Failed to load workspace data:", err);
    }
  }, [userId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle watchlists
  const handleAddToWatchlist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSymbol.trim()) return;
    setWatchlistLoading(true);
    setWatchlistError(null);
    try {
      await addToWatchlist(userId, newSymbol.trim().toUpperCase());
      setNewSymbol("");
      await loadData();
    } catch (err: any) {
      setWatchlistError(err?.message || "Failed to add to watchlist");
    } finally {
      setWatchlistLoading(false);
    }
  };

  const handleRemoveFromWatchlist = async (sym: string) => {
    try {
      await removeFromWatchlist(userId, sym);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  // Handle portfolio buy/sell
  const handleBuyHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!buySymbol.trim() || buyQty <= 0 || buyPriceInput <= 0) return;
    setPortfolioLoading(true);
    setPortfolioError(null);
    try {
      await buyHolding(userId, buySymbol.trim().toUpperCase(), buyQty, buyPriceInput);
      setBuySymbol("");
      setBuyQty(0);
      setBuyPriceInput(0);
      await loadData();
    } catch (err: any) {
      setPortfolioError(err?.message || "Transaction failed");
    } finally {
      setPortfolioLoading(false);
    }
  };

  const handleSellPosition = async (sym: string, qty: number) => {
    try {
      await sellHolding(userId, sym, qty);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  // Sync Watchlist CSV
  const handleSyncWatchlist = async () => {
    setSyncing(true);
    try {
      const status = await syncWatchlist();
      setSyncStatus(status);
      await loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-12 mb-12">
      {/* Dynamic Watchlist and Sync Section */}
      <div className="lg:col-span-1 flex flex-col gap-6">
        {/* 1. Official NSE Sync Section */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl">
          <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
            🔄 NSE Dynamic Index Sync
          </h3>
          <p className="text-xs text-slate-400 mt-1 mb-4 leading-relaxed">
            Dynamic Nifty 500 scanner downloading live CSV indices directly from NSE archives to classify large, mid, and small-caps.
          </p>

          <button
            onClick={handleSyncWatchlist}
            disabled={syncing}
            className="w-full h-10 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:from-emerald-800/40 disabled:to-teal-800/40 text-slate-100 font-bold rounded-xl flex items-center justify-center gap-2 border border-emerald-500/20 shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer"
          >
            {syncing ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Synchronizing official indices...</span>
              </>
            ) : (
              <span>Sync Dynamic Indices</span>
            )}
          </button>

          {syncStatus && (
            <div className="mt-4 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-xs text-slate-300 space-y-1.5">
              <div className="flex justify-between">
                <span>Large Cap (Nifty 100):</span>
                <span className="font-extrabold text-emerald-400">{syncStatus.large_count} stocks</span>
              </div>
              <div className="flex justify-between">
                <span>Mid Cap (Midcap 100):</span>
                <span className="font-extrabold text-emerald-400">{syncStatus.mid_count} stocks</span>
              </div>
              <div className="flex justify-between">
                <span>Small Cap (Smallcap 250):</span>
                <span className="font-extrabold text-emerald-400">{syncStatus.small_count} stocks</span>
              </div>
              <div className="text-[10px] text-slate-500 text-right pt-1.5 border-t border-slate-900">
                Last synced: {syncStatus.updated_at ? new Date(syncStatus.updated_at).toLocaleTimeString() : "Just now"}
              </div>
            </div>
          )}
        </div>

        {/* 2. Personal Watchlist Section */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl flex-1 flex flex-col">
          <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2 mb-4">
            👥 Personal Watchlist
          </h3>

          <form onSubmit={handleAddToWatchlist} className="flex gap-2 mb-4">
            <input
              type="text"
              placeholder="e.g. INFIBEAM.NS"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value)}
              className="flex-1 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all duration-200"
            />
            <button
              type="submit"
              disabled={watchlistLoading}
              className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-emerald-400 text-xs font-bold rounded-xl flex items-center justify-center transition-colors cursor-pointer"
            >
              Add
            </button>
          </form>

          {watchlistError && (
            <p className="text-[10px] text-rose-400 mb-3 animate-pulse">{watchlistError}</p>
          )}

          {/* Watchlist Symbol cards */}
          <div className="flex-1 overflow-y-auto space-y-3 max-h-[300px] pr-1">
            {watchlist.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500 flex flex-col items-center justify-center">
                <span>No custom watchlist items</span>
                <span className="text-[10px] text-slate-600 mt-1">Add symbols above to track indicators.</span>
              </div>
            ) : (
              watchlist.map((item) => (
                <div key={item.symbol} className="flex items-center justify-between p-3.5 bg-slate-900/30 border border-slate-900 hover:border-slate-800 rounded-2xl transition-all duration-150 group">
                  <div className="flex flex-col">
                    <span className="text-sm font-black text-slate-200 flex items-center gap-2">
                      {item.display_symbol}
                    </span>
                    <span className="text-[10px] text-slate-500 truncate max-w-[140px]">
                      {item.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <span className="text-sm font-black text-slate-200 block">
                        ₹{item.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </span>
                      <span className={`text-[10px] font-black ${item.change_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {item.change_pct >= 0 ? "+" : ""}{item.change_pct}%
                      </span>
                    </div>
                    <button
                      onClick={() => handleRemoveFromWatchlist(item.symbol)}
                      className="text-slate-600 hover:text-rose-400 p-1 rounded hover:bg-slate-900 transition-colors cursor-pointer"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Portfolio Holdings Section */}
      <div className="lg:col-span-2 rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl flex flex-col justify-between">
        <div>
          {/* Header */}
          <div className="flex justify-between items-start border-b border-slate-900/60 pb-4 mb-6">
            <div>
              <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
                💼 Share Holdings Portfolio
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time transaction tracking and evaluation of active share holdings in Indian Rupees.
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-extrabold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Live Holdings
            </span>
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-2xl relative overflow-hidden">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Total Investment
              </span>
              <span className="text-xl font-extrabold text-slate-200 mt-2 block">
                ₹{(portfolio?.summary?.total_investment ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            
            <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-2xl relative overflow-hidden">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Current Value
              </span>
              <span className="text-xl font-extrabold text-slate-200 mt-2 block">
                ₹{(portfolio?.summary?.total_current_value ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-2xl relative overflow-hidden group">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Overall Return
              </span>
              <span className={`text-xl font-black mt-2 block ${
                (portfolio?.summary?.total_profit_loss ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}>
                ₹{(portfolio?.summary?.total_profit_loss ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                <span className="text-xs font-bold ml-1.5">
                  ({(portfolio?.summary?.total_profit_loss_pct ?? 0) >= 0 ? "+" : ""}{portfolio?.summary?.total_profit_loss_pct}%)
                </span>
              </span>
            </div>
          </div>

          {/* Holdings table */}
          <div className="border border-slate-900 rounded-2xl overflow-hidden mb-6 bg-slate-900/5 shadow-inner max-h-[300px] overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-900 text-slate-500 text-[10px] uppercase tracking-wider bg-slate-900/25">
                  <th className="py-3 px-4 font-bold">Stock</th>
                  <th className="py-3 px-4 font-bold text-right">Shares</th>
                  <th className="py-3 px-4 font-bold text-right">Buy Price</th>
                  <th className="py-3 px-4 font-bold text-right">Current Price</th>
                  <th className="py-3 px-4 font-bold text-right">Profit / Loss</th>
                  <th className="py-3 px-4 font-bold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                {!portfolio?.holdings || portfolio.holdings.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-10 text-slate-500">
                      No active holdings. Record buy transactions below to begin tracking.
                    </td>
                  </tr>
                ) : (
                  portfolio.holdings.map((hold) => (
                    <tr key={hold.symbol} className="hover:bg-slate-900/10 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="font-extrabold text-slate-200">{hold.display_symbol}</span>
                          <span className="text-[9px] text-slate-500 truncate max-w-[120px]">{hold.name}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-right font-bold text-slate-300">{hold.shares_quantity}</td>
                      <td className="py-3.5 px-4 text-right">₹{hold.buy_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                      <td className="py-3.5 px-4 text-right">₹{hold.current_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                      <td className={`py-3.5 px-4 text-right font-black ${hold.profit_loss >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        <div className="flex flex-col items-end">
                          <span>₹{hold.profit_loss.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                          <span className="text-[9px]">{hold.profit_loss_pct >= 0 ? "+" : ""}{hold.profit_loss_pct}%</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <button
                          onClick={() => handleSellPosition(hold.symbol, hold.shares_quantity)}
                          className="text-rose-500/80 hover:text-rose-400 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-rose-500/5 hover:bg-rose-500/10 border border-rose-500/15 transition-all cursor-pointer"
                        >
                          Sell All
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Add trade holdings transaction */}
        <div className="border-t border-slate-900 pt-6">
          <h4 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
            📥 Add Holdings Transaction
          </h4>
          <form onSubmit={handleBuyHolding} className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Symbol</label>
              <input
                type="text"
                placeholder="e.g. TATAMOTORS.NS"
                required
                value={buySymbol}
                onChange={(e) => setBuySymbol(e.target.value)}
                className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all"
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Shares Quantity</label>
              <input
                type="number"
                min="0.01"
                step="any"
                placeholder="Shares"
                required
                value={buyQty || ""}
                onChange={(e) => setBuyQty(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Purchase Price (₹)</label>
              <input
                type="number"
                min="0.01"
                step="any"
                placeholder="Price"
                required
                value={buyPriceInput || ""}
                onChange={(e) => setBuyPriceInput(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={portfolioLoading}
              className="h-[34px] w-full bg-slate-100 hover:bg-white text-slate-900 font-extrabold rounded-xl text-xs flex items-center justify-center transition-all cursor-pointer border border-slate-200 shadow-sm"
            >
              Add Shares
            </button>
          </form>
          {portfolioError && (
            <p className="text-[10px] text-rose-400 mt-2 animate-pulse">{portfolioError}</p>
          )}
        </div>

      </div>
    </div>
  );
}
