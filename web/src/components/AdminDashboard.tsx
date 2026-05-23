import React, { useState, useEffect } from "react";
import {
  adminGetUsers,
  adminCreateUser,
  adminSetPermissions,
  adminGetTrades,
  adminBuyTrade,
  adminSellTrade,
  UserRoleProfile,
  AdminTrade,
} from "@/lib/api";

interface AdminDashboardProps {
  onImpersonate: (userEmail: string, userId: string, permissions: any) => void;
}

export default function AdminDashboard({ onImpersonate }: AdminDashboardProps) {
  // User Management
  const [users, setUsers] = useState<UserRoleProfile[]>([]);
  const [newEmail, setNewEmail] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [userLoading, setUserLoading] = useState<boolean>(false);
  const [userError, setUserError] = useState<string | null>(null);

  // Private Trading Board
  const [trades, setTrades] = useState<AdminTrade[]>([]);
  const [tradeSymbol, setTradeSymbol] = useState<string>("");
  const [tradeQty, setTradeQty] = useState<number>(0);
  const [tradeBuyPrice, setTradeBuyPrice] = useState<number>(0);
  const [tradeLoading, setTradeLoading] = useState<boolean>(false);
  const [tradeError, setTradeError] = useState<string | null>(null);
  
  // Close transaction state
  const [closingTradeId, setClosingTradeId] = useState<string | null>(null);
  const [sellPriceInput, setSellPriceInput] = useState<number>(0);

  const loadData = async () => {
    try {
      const [usersData, tradesData] = await Promise.all([
        adminGetUsers(),
        adminGetTrades(),
      ]);
      setUsers(usersData.users ?? []);
      setTrades(tradesData.trades ?? []);
    } catch (err) {
      console.error("Failed to load admin controls:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Handle user creation
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim() || !newPassword) return;
    setUserLoading(true);
    setUserError(null);
    try {
      await adminCreateUser(newEmail.trim(), newPassword);
      setNewEmail("");
      setNewPassword("");
      await loadData();
    } catch (err: any) {
      setUserError(err?.message || "Failed to register user");
    } finally {
      setUserLoading(false);
    }
  };

  // Handle permission toggle
  const handlePermissionToggle = async (
    user: UserRoleProfile,
    permissionKey: keyof UserRoleProfile["permissions"]
  ) => {
    const updatedPermissions = {
      ...user.permissions,
      [permissionKey]: !user.permissions[permissionKey],
    };
    try {
      // Optmistically update state
      setUsers(
        users.map((u) =>
          u.user_id === user.user_id ? { ...u, permissions: updatedPermissions } : u
        )
      );
      await adminSetPermissions(user.user_id, updatedPermissions);
    } catch (err) {
      console.error("Failed to update user permissions:", err);
      loadData(); // Revert on failure
    }
  };

  // Handle trade buy
  const handleBuyTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tradeSymbol.trim() || tradeQty <= 0 || tradeBuyPrice <= 0) return;
    setTradeLoading(true);
    setTradeError(null);
    try {
      await adminBuyTrade(tradeSymbol.trim().toUpperCase(), tradeQty, tradeBuyPrice);
      setTradeSymbol("");
      setTradeQty(0);
      setTradeBuyPrice(0);
      await loadData();
    } catch (err: any) {
      setTradeError(err?.message || "Trade record failed");
    } finally {
      setTradeLoading(false);
    }
  };

  // Handle trade close
  const handleCloseTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!closingTradeId || sellPriceInput <= 0) return;
    try {
      await adminSellTrade(closingTradeId, sellPriceInput);
      setClosingTradeId(null);
      setSellPriceInput(0);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  // Profit calculations
  const totalClosedProfit = trades
    .filter((t) => t.trade_status === "closed" && t.profit_loss !== null)
    .reduce((acc, curr) => acc + (curr.profit_loss ?? 0), 0);

  const totalInvestedCapital = trades
    .filter((t) => t.trade_status === "open")
    .reduce((acc, curr) => acc + curr.shares_quantity * curr.buy_price, 0);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 mt-6 mb-12">
      {/* Impersonator & Permissions Control Section */}
      <div className="xl:col-span-2 flex flex-col gap-6">
        
        {/* User Management and Register Panel */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl">
          <div className="flex justify-between items-start border-b border-slate-900/60 pb-4 mb-6">
            <div>
              <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
                🛡️ User Permissions Control Center
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Set and configure precise feature permissions, register custom users, or impersonate active sessions.
              </p>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-extrabold tracking-wider uppercase bg-purple-500/10 text-purple-400 border border-purple-500/20">
              Admin Master RLS
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6 items-end">
            <form onSubmit={handleCreateUser} className="lg:col-span-3 flex flex-wrap gap-4 items-end bg-slate-900/15 border border-slate-900 p-4 rounded-2xl">
              <div className="flex-1 min-w-[200px] space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">User Email</label>
                <input
                  type="email"
                  placeholder="e.g. user@advisor.in"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-purple-500/50 transition-all"
                />
              </div>

              <div className="flex-1 min-w-[200px] space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">User Password</label>
                <input
                  type="password"
                  placeholder="Password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-purple-500/50 transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={userLoading}
                className="h-[34px] px-6 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white font-extrabold rounded-xl text-xs flex items-center justify-center transition-all cursor-pointer border border-purple-500/20 shadow-md"
              >
                Register User
              </button>
            </form>
            {userError && (
              <p className="text-[10px] text-rose-400 lg:col-span-3 animate-pulse">{userError}</p>
            )}
          </div>

          {/* User Impersonation & Permissions Checkbox Table */}
          <div className="border border-slate-900 rounded-2xl overflow-hidden bg-slate-900/5 shadow-inner overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[700px]">
              <thead>
                <tr className="border-b border-slate-900 text-slate-500 text-[10px] uppercase tracking-wider bg-slate-900/25">
                  <th className="py-3.5 px-4 font-bold">User Profile</th>
                  <th className="py-3.5 px-4 font-bold text-center">Charts</th>
                  <th className="py-3.5 px-4 font-bold text-center">Buys</th>
                  <th className="py-3.5 px-4 font-bold text-center">Heatmap</th>
                  <th className="py-3.5 px-4 font-bold text-center">Signals</th>
                  <th className="py-3.5 px-4 font-bold text-center">Backtest</th>
                  <th className="py-3.5 px-4 font-bold text-center">Portfolio</th>
                  <th className="py-3.5 px-4 font-bold">Impersonate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-10 text-slate-500">
                      No active users loaded.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.user_id} className="hover:bg-slate-900/10 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="font-extrabold text-slate-200">{u.email}</span>
                          <span className="text-[9px] text-slate-500 capitalize">
                            Role: {u.role} {u.offline_password ? `• PW: ${u.offline_password}` : ""}
                          </span>
                        </div>
                      </td>
                      {/* Permission Checklist Matrix */}
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_view_charts !== false}
                          onChange={() => handlePermissionToggle(u, "can_view_charts")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_view_recommendations !== false}
                          onChange={() => handlePermissionToggle(u, "can_view_recommendations")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_view_heatmap !== false}
                          onChange={() => handlePermissionToggle(u, "can_view_heatmap")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_view_signals !== false}
                          onChange={() => handlePermissionToggle(u, "can_view_signals")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_backtest !== false}
                          onChange={() => handlePermissionToggle(u, "can_backtest")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <input
                          type="checkbox"
                          checked={u.permissions?.can_use_portfolio !== false}
                          onChange={() => handlePermissionToggle(u, "can_use_portfolio")}
                          className="accent-purple-500 h-4 w-4 bg-slate-900 border-slate-800 rounded cursor-pointer"
                        />
                      </td>
                      <td className="py-3.5 px-4">
                        <button
                          onClick={() => onImpersonate(u.email, u.user_id, u.permissions)}
                          className="text-purple-400 hover:text-white text-[10px] font-bold uppercase tracking-wider px-2 py-1.5 rounded bg-purple-500/10 hover:bg-purple-600 border border-purple-500/20 hover:border-purple-500 transition-all cursor-pointer shadow-[0_0_10px_rgba(168,85,247,0.1)] hover:shadow-[0_0_15px_rgba(168,85,247,0.25)]"
                        >
                          👤 Impersonate
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {/* Admin Separate Trading Dashboard */}
      <div className="xl:col-span-1 flex flex-col gap-6">
        
        <div className="rounded-3xl border border-slate-800 bg-slate-950/60 backdrop-blur-xl p-6 shadow-2xl flex flex-col justify-between h-full">
          <div>
            {/* Header */}
            <div className="flex justify-between items-start border-b border-slate-900/60 pb-4 mb-6">
              <div>
                <h3 className="text-md font-extrabold text-slate-100 tracking-wide flex items-center gap-2">
                  📈 Admin Private Trading
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Record personal trading positions secluded from basic user watchlists.
                </p>
              </div>
            </div>

            {/* Admin Stats grid */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-slate-900/20 border border-slate-900 p-3.5 rounded-2xl">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  Invested Capital
                </span>
                <span className="text-md font-black text-slate-200 mt-1 block">
                  ₹{totalInvestedCapital.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div className="bg-slate-900/20 border border-slate-900 p-3.5 rounded-2xl group">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  Total Closed Profit
                </span>
                <span className={`text-md font-black mt-1 block ${
                  totalClosedProfit >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}>
                  ₹{totalClosedProfit.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>

            {/* List of Private trades */}
            <div className="border border-slate-900 rounded-2xl overflow-hidden mb-6 bg-slate-900/5 shadow-inner max-h-[220px] overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-900 text-slate-500 text-[9px] uppercase tracking-wider bg-slate-900/25">
                    <th className="py-2.5 px-3 font-bold">Stock</th>
                    <th className="py-2.5 px-3 font-bold text-right">Shares / Buy</th>
                    <th className="py-2.5 px-3 font-bold text-right">Outcomes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40 text-slate-300 text-xs">
                  {trades.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="text-center py-8 text-slate-500 text-[10px]">
                        No admin trades recorded yet.
                      </td>
                    </tr>
                  ) : (
                    trades.map((t) => (
                      <tr key={t.id} className="hover:bg-slate-900/10 transition-colors">
                        <td className="py-2.5 px-3">
                          <span className="font-extrabold text-slate-200 block">{t.display_symbol || t.symbol}</span>
                          <span className="text-[9px] text-slate-500">{t.created_at ? t.created_at.split("T")[0] : ""}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex flex-col items-end">
                            <span className="font-bold text-slate-300">{t.shares_quantity} sh</span>
                            <span className="text-[9px] text-slate-500">₹{t.buy_price}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {t.trade_status === "open" ? (
                            closingTradeId === t.id ? (
                              <form onSubmit={handleCloseTrade} className="flex items-center gap-1.5 justify-end">
                                <input
                                  type="number"
                                  placeholder="Sell"
                                  required
                                  step="any"
                                  onChange={(e) => setSellPriceInput(parseFloat(e.target.value) || 0)}
                                  className="w-14 bg-slate-900 border border-slate-800 rounded px-1.5 py-0.5 text-slate-100 text-[10px]"
                                />
                                <button
                                  type="submit"
                                  className="bg-emerald-600 text-white rounded px-2 py-0.5 text-[9px] font-bold cursor-pointer"
                                >
                                  OK
                                </button>
                              </form>
                            ) : (
                              <button
                                onClick={() => {
                                  setClosingTradeId(t.id!);
                                  setSellPriceInput(0);
                                }}
                                className="text-rose-400 hover:text-rose-300 text-[9px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-rose-500/5 hover:bg-rose-500/15 border border-rose-500/15 transition-all cursor-pointer"
                              >
                                Close Position
                              </button>
                            )
                          ) : (
                            <div className="flex flex-col items-end">
                              <span className={`font-black ${t.profit_loss! >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                {t.profit_loss! >= 0 ? "+" : ""}₹{t.profit_loss}
                              </span>
                              <span className="text-[8px] text-slate-500">Exit: ₹{t.sell_price}</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Record admin trade form */}
          <div className="border-t border-slate-900 pt-5 mt-auto">
            <h4 className="text-[10px] font-black uppercase tracking-wider text-slate-500 mb-3">
              📥 Record Admin Trade Buy
            </h4>
            <form onSubmit={handleBuyTrade} className="grid grid-cols-3 gap-2.5 items-end">
              <div className="space-y-1">
                <label className="text-[9px] font-bold text-slate-500">Symbol</label>
                <input
                  type="text"
                  placeholder="Symbol"
                  required
                  value={tradeSymbol}
                  onChange={(e) => setTradeSymbol(e.target.value)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                />
              </div>
              
              <div className="space-y-1">
                <label className="text-[9px] font-bold text-slate-500">Shares</label>
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  placeholder="Qty"
                  required
                  value={tradeQty || ""}
                  onChange={(e) => setTradeQty(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[9px] font-bold text-slate-500">Buy Price</label>
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  placeholder="Price"
                  required
                  value={tradeBuyPrice || ""}
                  onChange={(e) => setTradeBuyPrice(parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-2.5 py-1.5 text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-purple-500/50"
                />
              </div>

              <button
                type="submit"
                disabled={tradeLoading}
                className="w-full h-8 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white font-extrabold rounded-xl text-[10px] flex items-center justify-center transition-all cursor-pointer border border-purple-500/20 col-span-3 mt-2"
              >
                Record Private Buy
              </button>
            </form>
            {tradeError && (
              <p className="text-[9px] text-rose-400 mt-2 animate-pulse">{tradeError}</p>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}
