import React, { useState, useEffect, useCallback } from "react";
import {
  getUserWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  getUserPortfolio,
  buyHolding,
  sellHolding,
  syncWatchlist,
  getUserPassbook,
  reconcilePortfolioTriggers,
  updatePortfolioThresholds,
  UserWatchlistItem,
  UserPortfolioResponse,
  PassbookItem,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Modal, InputNumber, Button, ConfigProvider, theme } from "antd";

interface UserWorkspaceProps {
  userId?: string;
  userEmail?: string;
  onAnalyzeHolding?: (symbol: string, shares: number, buyPrice: number) => void;
  onAnalyzeEntirePortfolio?: (holdings: { symbol: string; shares: number; buyPrice: number }[]) => void;
  canUseChatbot?: boolean;
}

type SyncStatus =
  | {
      success: true;
      large_count: number;
      mid_count: number;
      small_count: number;
      updated_at: string;
    }
  | {
      success: false;
      message: string;
    };

function getErrorMessage(err: unknown, fallback: string) {
  if (err instanceof TypeError && err.message === "Failed to fetch") {
    return "API server is offline. Start the backend on port 8000, then refresh this workspace.";
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export default function UserWorkspace({
  userId: propUserId,
  userEmail: propUserEmail,
  onAnalyzeHolding,
  onAnalyzeEntirePortfolio,
  canUseChatbot = false,
}: UserWorkspaceProps = {}) {
  const [sessionUserId, setSessionUserId] = useState<string>("");
  const [watchlist, setWatchlist] = useState<UserWatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<UserPortfolioResponse | null>(null);
  const [activeTab, setActiveTab] = useState<"holdings" | "passbook">("holdings");
  const [passbook, setPassbook] = useState<PassbookItem[]>([]);
  
  // Watchlist Input
  const [newSymbol, setNewSymbol] = useState<string>("");
  const [watchlistLoading, setWatchlistLoading] = useState<boolean>(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  // Portfolio Transaction Inputs
  const [buySymbol, setBuySymbol] = useState<string>("");
  const [buyQty, setBuyQty] = useState<number>(0);
  const [buyPriceInput, setBuyPriceInput] = useState<number>(0);
  const [buyTargetInput, setBuyTargetInput] = useState<number>(0);
  const [buyStopInput, setBuyStopInput] = useState<number>(0);
  const [portfolioLoading, setPortfolioLoading] = useState<boolean>(false);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);

  // Edit Triggers Modal State
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editSymbol, setEditSymbol] = useState("");
  const [editTarget, setEditTarget] = useState<number>(0);
  const [editStop, setEditStop] = useState<number>(0);
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  // Sync state
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const effectiveUserId = propUserId || sessionUserId || "default-trader-admin";

  useEffect(() => {
    if (propUserId) return;
    
    async function checkUser() {
      try {
        const supabase = createClient();
        const { data } = await supabase.auth.getUser();
        if (data?.user?.id) {
          setSessionUserId(data.user.id);
        }
      } catch {
        setSessionUserId("");
      }
    }
    void checkUser();
  }, [propUserId]);

  const loadData = useCallback(async () => {
    try {
      // Auto-reconcile portfolio triggers on load
      try {
        await reconcilePortfolioTriggers(effectiveUserId);
      } catch (recErr) {
        console.error("Auto-reconcile triggers failed:", recErr);
      }

      const [watchData, portData, passbookData] = await Promise.all([
        getUserWatchlist(effectiveUserId),
        getUserPortfolio(effectiveUserId),
        getUserPassbook(effectiveUserId),
      ]);
      setWatchlist(watchData.watchlist ?? []);
      setPortfolio(portData);
      setPassbook(passbookData.passbook ?? []);
      setApiConnected(true);
    } catch (err) {
      setApiConnected(false);
      setWatchlistError(getErrorMessage(err, "Could not load watchlist."));
      setPortfolioError(getErrorMessage(err, "Could not load portfolio."));
    }
  }, [effectiveUserId]);

  useEffect(() => {
    // Workspace hydration is an API synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  // Handle watchlists
  const handleAddToWatchlist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSymbol.trim()) return;
    setWatchlistLoading(true);
    setWatchlistError(null);
    try {
      await addToWatchlist(effectiveUserId, newSymbol.trim().toUpperCase());
      setNewSymbol("");
      await loadData();
    } catch (err) {
      setWatchlistError(getErrorMessage(err, "Failed to add to watchlist"));
    } finally {
      setWatchlistLoading(false);
    }
  };

  const handleRemoveFromWatchlist = async (sym: string) => {
    setWatchlistError(null);
    try {
      await removeFromWatchlist(effectiveUserId, sym);
      await loadData();
    } catch (err) {
      setWatchlistError(getErrorMessage(err, "Failed to remove from watchlist"));
    }
  };

  // Handle portfolio buy/sell
  const handleBuyHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!buySymbol.trim() || buyQty <= 0 || buyPriceInput <= 0) return;
    setPortfolioLoading(true);
    setPortfolioError(null);
    try {
      await buyHolding(
        effectiveUserId,
        buySymbol.trim().toUpperCase(),
        buyQty,
        buyPriceInput,
        buyTargetInput > 0 ? buyTargetInput : null,
        buyStopInput > 0 ? buyStopInput : null
      );
      setBuySymbol("");
      setBuyQty(0);
      setBuyPriceInput(0);
      setBuyTargetInput(0);
      setBuyStopInput(0);
      await loadData();
    } catch (err) {
      setPortfolioError(getErrorMessage(err, "Transaction failed"));
    } finally {
      setPortfolioLoading(false);
    }
  };

  const handleSellPosition = async (sym: string, qty: number) => {
    setPortfolioError(null);
    try {
      await sellHolding(effectiveUserId, sym, qty);
      await loadData();
    } catch (err) {
      setPortfolioError(getErrorMessage(err, "Sell transaction failed"));
    }
  };

  const handleAnalyzeEntirePortfolio = () => {
    if (!portfolio?.holdings || portfolio.holdings.length === 0) return;
    const items = portfolio.holdings.map(h => ({
      symbol: h.symbol,
      shares: h.shares_quantity,
      buyPrice: h.buy_price
    }));
    if (onAnalyzeEntirePortfolio) {
      onAnalyzeEntirePortfolio(items);
    }
  };

  // Sync Watchlist CSV
  const handleSyncWatchlist = async () => {
    setSyncing(true);
    setSyncStatus(null);
    try {
      const status = await syncWatchlist();
      setSyncStatus({ ...status, success: true });
      await loadData();
    } catch (err) {
      setSyncStatus({ success: false, message: getErrorMessage(err, "Sync failed") });
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
          {apiConnected === false && (
            <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs leading-relaxed text-amber-200">
              API server is offline. Portfolio and watchlist actions need the backend at localhost:8000.
            </div>
          )}

          <button
            onClick={handleSyncWatchlist}
            disabled={syncing || apiConnected === false}
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
            syncStatus.success ? (
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
            ) : (
              <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-200">
                {syncStatus.message}
              </div>
            )
          )}
        </div>

        {/* 2. Personal Watchlist Section */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl flex-1 flex flex-col">
          <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2 mb-4">
            👥 Personal Watchlist {propUserEmail && <span className="text-slate-400 font-normal">({propUserEmail})</span>}
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
              disabled={watchlistLoading || apiConnected === false}
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
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-900/60 pb-4 mb-6 gap-4">
            <div>
              <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
                💼 Share Holdings Portfolio {propUserEmail && <span className="text-slate-400 font-normal">({propUserEmail})</span>}
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time transaction tracking and evaluation of active share holdings in Indian Rupees.
              </p>
            </div>
            <div className="flex items-center gap-2.5 self-stretch sm:self-auto justify-end">
              {portfolio?.holdings && portfolio.holdings.length > 0 && (
                canUseChatbot ? (
                  <button
                    onClick={handleAnalyzeEntirePortfolio}
                    className="h-8 px-3 rounded bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-[10px] font-black uppercase tracking-wider border border-purple-500/20 hover:border-purple-500/40 hover:shadow-[0_0_15px_rgba(168,85,247,0.25)] transition-all cursor-pointer flex items-center gap-1.5 shrink-0"
                  >
                    🤖 AI Analyze Portfolio
                  </button>
                ) : (
                  <button
                    onClick={() => alert("🔒 Chatbot Advisor is currently locked on your profile. Please ask an admin to enable the Chatbot permission in the Admin Control Center.")}
                    className="h-8 px-3 rounded bg-slate-900 border border-slate-800 text-slate-500 text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer flex items-center gap-1.5 shrink-0"
                  >
                    🔒 AI Analyze Portfolio
                  </button>
                )
              )}
              <span className="px-2 py-1.5 rounded text-[10px] font-extrabold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                Live Holdings
              </span>
            </div>
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

          {/* Tab Selection */}
          <div className="flex gap-2 mb-6 border-b border-slate-900 pb-2">
            <button
              onClick={() => setActiveTab("holdings")}
              className={`pb-2 px-4 text-xs font-black uppercase tracking-wider transition-all relative cursor-pointer ${
                activeTab === "holdings"
                  ? "text-emerald-400 border-b-2 border-emerald-500"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📦 Active Holdings ({portfolio?.holdings?.length ?? 0})
            </button>
            <button
              onClick={() => setActiveTab("passbook")}
              className={`pb-2 px-4 text-xs font-black uppercase tracking-wider transition-all relative cursor-pointer ${
                activeTab === "passbook"
                  ? "text-emerald-400 border-b-2 border-emerald-500"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📖 Transaction Passbook ({passbook.length})
            </button>
          </div>

          {activeTab === "holdings" ? (
            /* Holdings table */
            <div className="border border-slate-900 rounded-2xl overflow-hidden mb-6 bg-slate-900/5 shadow-inner max-h-[300px] overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-900 text-slate-500 text-[10px] uppercase tracking-wider bg-slate-900/25">
                    <th className="py-3 px-4 font-bold">Stock</th>
                    <th className="py-3 px-4 font-bold text-right">Shares</th>
                    <th className="py-3 px-4 font-bold text-right">Buy Price</th>
                    <th className="py-3 px-4 font-bold text-right">Current Price</th>
                    <th className="py-3 px-4 font-bold text-right">Target</th>
                    <th className="py-3 px-4 font-bold text-right">Stop Loss</th>
                    <th className="py-3 px-4 font-bold text-right">Profit / Loss</th>
                    <th className="py-3 px-4 font-bold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                  {!portfolio?.holdings || portfolio.holdings.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center py-10 text-slate-500">
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
                        <td className="py-3.5 px-4 text-right font-medium text-emerald-400">
                          {hold.target_price ? `₹${hold.target_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}` : "—"}
                        </td>
                        <td className="py-3.5 px-4 text-right font-medium text-rose-400">
                          {hold.stop_loss ? `₹${hold.stop_loss.toLocaleString("en-IN", { minimumFractionDigits: 2 })}` : "—"}
                        </td>
                        <td className={`py-3.5 px-4 text-right font-black ${hold.profit_loss >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          <div className="flex flex-col items-end">
                            <span>₹{hold.profit_loss.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                            <span className="text-[9px]">{hold.profit_loss_pct >= 0 ? "+" : ""}{hold.profit_loss_pct}%</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex gap-2">
                            {canUseChatbot ? (
                              <button
                                onClick={() => onAnalyzeHolding && onAnalyzeHolding(hold.symbol, hold.shares_quantity, hold.buy_price)}
                                className="text-purple-400 hover:text-purple-300 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 hover:border-purple-500/45 hover:shadow-[0_0_10px_rgba(168,85,247,0.15)] transition-all cursor-pointer shrink-0"
                              >
                                🤖 AI Analyze
                              </button>
                            ) : (
                              <button
                                onClick={() => alert("🔒 Chatbot Advisor is currently locked on your profile. Please ask an admin to enable the Chatbot permission in the Admin Control Center.")}
                                className="text-slate-500 hover:text-slate-400 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-slate-900 border border-slate-800 transition-all cursor-pointer shrink-0"
                              >
                                🔒 AI Analyze
                              </button>
                            )}
                            <button
                              onClick={() => {
                                setEditSymbol(hold.symbol);
                                setEditTarget(hold.target_price || 0);
                                setEditStop(hold.stop_loss || 0);
                                setEditError(null);
                                setEditModalOpen(true);
                              }}
                              className="text-amber-400 hover:text-amber-300 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 transition-all cursor-pointer shrink-0"
                            >
                              ✏️ Edit Triggers
                            </button>
                            <button
                              onClick={() => handleSellPosition(hold.symbol, hold.shares_quantity)}
                              disabled={apiConnected === false}
                              className="text-rose-500/80 hover:text-rose-400 text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-rose-500/5 hover:bg-rose-500/10 border border-rose-500/15 transition-all cursor-pointer shrink-0"
                            >
                              Sell All
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            /* Passbook History table */
            <div className="border border-slate-900 rounded-2xl overflow-hidden mb-6 bg-slate-900/5 shadow-inner max-h-[300px] overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-900 text-slate-500 text-[10px] uppercase tracking-wider bg-slate-900/25">
                    <th className="py-3 px-4 font-bold">Transaction Date</th>
                    <th className="py-3 px-4 font-bold">Stock</th>
                    <th className="py-3 px-4 font-bold text-right">Shares</th>
                    <th className="py-3 px-4 font-bold text-right">Buy Price</th>
                    <th className="py-3 px-4 font-bold text-right">Sell Price</th>
                    <th className="py-3 px-4 font-bold text-right">Realized Return</th>
                    <th className="py-3 px-4 font-bold">Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                  {passbook.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-10 text-slate-500">
                        No transactions recorded in passbook.
                      </td>
                    </tr>
                  ) : (
                    passbook.map((item) => (
                      <tr key={item.id || `${item.symbol}-${item.created_at}`} className="hover:bg-slate-900/10 transition-colors">
                        <td className="py-3.5 px-4 text-slate-500 font-mono text-[10px]">
                          {new Date(item.created_at).toLocaleString("en-IN", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex flex-col">
                            <span className="font-extrabold text-slate-200">{item.display_symbol}</span>
                            <span className="text-[9px] text-slate-500 uppercase font-bold">{item.symbol}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-right font-bold text-slate-300">{item.shares_quantity}</td>
                        <td className="py-3.5 px-4 text-right">₹{item.buy_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                        <td className="py-3.5 px-4 text-right font-bold text-slate-200">₹{item.sell_price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                        <td className={`py-3.5 px-4 text-right font-black ${item.profit_loss >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          <div className="flex flex-col items-end">
                            <span>₹{item.profit_loss.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                            <span className="text-[9px]">{item.profit_loss_pct >= 0 ? "+" : ""}{item.profit_loss_pct}%</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider border ${
                            item.execution_type === "target_trigger"
                              ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/25"
                              : item.execution_type === "stop_loss_trigger"
                              ? "bg-rose-950/40 text-rose-400 border-rose-500/25"
                              : "bg-slate-900/60 text-slate-400 border-slate-700/40"
                          }`}>
                            {item.execution_type === "target_trigger"
                              ? "🎯 Target Hit"
                              : item.execution_type === "stop_loss_trigger"
                              ? "🛡️ Stop Loss"
                              : "Manual"}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Add trade holdings transaction */}
        {activeTab === "holdings" && (
          <div className="border-t border-slate-900 pt-6">
            <h4 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
              📥 Add Holdings Transaction
            </h4>
            <form onSubmit={handleBuyHolding} className="grid grid-cols-1 sm:grid-cols-3 md:grid-cols-6 gap-4 items-end">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Symbol</label>
                <input
                  type="text"
                  placeholder="TATAMOTORS.NS"
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

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Target Price (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  placeholder="Optional"
                  value={buyTargetInput || ""}
                  onChange={(e) => setBuyTargetInput(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Stop Loss (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="any"
                  placeholder="Optional"
                  value={buyStopInput || ""}
                  onChange={(e) => setBuyStopInput(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={portfolioLoading || apiConnected === false}
                className="h-[34px] w-full bg-slate-100 hover:bg-white text-slate-900 font-extrabold rounded-xl text-xs flex items-center justify-center transition-all cursor-pointer border border-slate-200 shadow-sm"
              >
                Add Shares
              </button>
            </form>
            {portfolioError && (
              <p className="text-[10px] text-rose-400 mt-2 animate-pulse">{portfolioError}</p>
            )}
          </div>
        )}

      </div>

      {editSymbol && (
        <ConfigProvider
          theme={{
            algorithm: theme.darkAlgorithm,
            token: {
              colorPrimary: "#10B981",
              colorBgBase: "#090d16",
              colorTextBase: "#f3f4f6",
              borderRadius: 12,
            },
          }}
        >
          <Modal
            open={editModalOpen}
            onCancel={() => setEditModalOpen(false)}
            footer={null}
            centered
            title={
              <div className="flex items-center gap-2 text-white border-b border-slate-800 pb-3">
                <span className="text-xl">✏️</span>
                <span className="font-extrabold text-lg">Modify Active Triggers</span>
              </div>
            }
            className="border border-slate-800 rounded-2xl overflow-hidden shadow-2xl"
            styles={{
              body: { backgroundColor: "#090d16", padding: "16px 4px 4px 4px" },
              mask: { backdropFilter: "blur(4px)" }
            }}
          >
            <div className="space-y-5 text-slate-300">
              <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800/80 shadow-inner">
                <h4 className="text-white text-lg font-black tracking-tight">{editSymbol.replace(".NS", "").replace(".BO", "")}</h4>
                <p className="text-[#9CA3AF] text-[10px] font-bold uppercase tracking-wider">Mid-Trade Trigger Adjustment</p>
              </div>

              <div className="space-y-2">
                <label className="block text-slate-400 text-xs font-semibold uppercase tracking-wider">Target Price (₹) — Auto Sell</label>
                <InputNumber
                  min={0}
                  value={editTarget || null}
                  onChange={(val) => setEditTarget(val || 0)}
                  formatter={(value) => `₹ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                  parser={(value) => value ? parseFloat(value.replace(/₹\s?|(,*)/g, "")) : 0}
                  className="w-full font-bold"
                  size="large"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-slate-400 text-xs font-semibold uppercase tracking-wider">Stop Loss (₹) — Auto Sell</label>
                <InputNumber
                  min={0}
                  value={editStop || null}
                  onChange={(val) => setEditStop(val || 0)}
                  formatter={(value) => `₹ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                  parser={(value) => value ? parseFloat(value.replace(/₹\s?|(,*)/g, "")) : 0}
                  className="w-full font-bold"
                  size="large"
                />
              </div>

              {editError && (
                <p className="text-xs text-rose-400 font-medium animate-pulse">{editError}</p>
              )}

              <div className="flex gap-3 pt-3">
                <Button
                  onClick={() => setEditModalOpen(false)}
                  className="flex-1 !bg-slate-900/40 !border-slate-800 !text-slate-400 hover:!text-white hover:!bg-slate-800/40 hover:!border-slate-700 transition-all duration-200"
                  size="large"
                >
                  Cancel
                </Button>
                <Button
                  type="primary"
                  onClick={async () => {
                    setEditLoading(true);
                    setEditError(null);
                    try {
                      const success = await updatePortfolioThresholds(
                        effectiveUserId,
                        editSymbol,
                        editTarget > 0 ? editTarget : null,
                        editStop > 0 ? editStop : null
                      );
                      if (success) {
                        setEditModalOpen(false);
                        await loadData();
                      } else {
                        setEditError("Failed to update thresholds.");
                      }
                    } catch (err: any) {
                      setEditError(err.message || "Failed to update thresholds.");
                    } finally {
                      setEditLoading(false);
                    }
                  }}
                  loading={editLoading}
                  className="flex-1 !bg-gradient-to-r !from-emerald-500 !to-teal-600 hover:!from-emerald-400 hover:!to-teal-500 !border-none !font-black !text-white tracking-wide shadow-lg hover:shadow-emerald-500/20 transition-all duration-200"
                  size="large"
                >
                  SAVE TRIGGERS 💾
                </Button>
              </div>
            </div>
          </Modal>
        </ConfigProvider>
      )}
    </div>
  );
}
