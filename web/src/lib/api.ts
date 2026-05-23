const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type TradeMode = "intraday" | "swing" | "longterm" | "future";

export type Recommendation = {
  id?: string;
  symbol: string;
  cap_segment?: string;
  rank: number;
  action: string;
  composite_score: number;
  trend_score: number;
  news_score: number;
  technical_score: number;
  fundamental_score?: number;
  ai_confidence: number;
  reasoning: string;
  key_factors: string[];
  signal_date: string;
  trade_date: string;
  trade_mode?: TradeMode;
  // Mode-specific optional indicators
  vwap?: number;
  bullish_crossover?: boolean;
  golden_cross?: boolean;
  range_52w_pct?: number;
  pe_ratio?: number;
  dividend_yield?: number;
  is_undervalued?: boolean;
  stocks?: {
    name: string;
    sector: string;
    pe_ratio: number;
    market_cap: number;
    is_undervalued?: boolean;
  };
};

export type TradingSignal = {
  id?: string;
  symbol: string;
  signal_type: "buy" | "sell" | "hold";
  trade_mode?: TradeMode;
  strength: string;
  price_at_signal: number;
  target_price: number | null;
  stop_loss: number | null;
  rationale: string;
  signal_date: string;
  planned_trade_date: string;
  stocks?: { name: string; sector: string };
};

export type AnalysisJob = {
  job_id: string;
  status: "running" | "completed" | "failed" | "idle";
  progress?: number;
  total?: number;
  done?: number;
  phase?: string;
  message?: string;
  result?: {
    stocks_analyzed: number;
    trade_date: string;
    top_recommendations: Recommendation[];
  };
  error?: string;
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function getRecommendations(tradeDate?: string, mode?: TradeMode) {
  const params = new URLSearchParams();
  if (tradeDate) params.set("trade_date", tradeDate);
  if (mode) params.set("mode", mode);
  const q = params.toString() ? `?${params}` : "";
  return fetchJson<{ recommendations: Recommendation[]; trade_date: string }>(
    `/api/recommendations${q}`
  );
}

export async function getSignals(plannedDate?: string, signalType?: string, mode?: TradeMode) {
  const params = new URLSearchParams();
  if (plannedDate) params.set("planned_trade_date", plannedDate);
  if (signalType) params.set("signal_type", signalType);
  if (mode) params.set("mode", mode);
  const q = params.toString() ? `?${params}` : "";
  return fetchJson<{ signals: TradingSignal[] }>(`/api/signals${q}`);
}

export async function getStockDetail(symbol: string) {
  return fetchJson<{
    stock: Record<string, unknown>;
    metrics: Record<string, unknown>[];
    news: Record<string, unknown>[];
    latest_recommendation: Recommendation | null;
  }>(`/api/stocks/${symbol}`);
}

export type AnalysisStartResponse = {
  job_id: string;
  status: string;
  message: string;
  result?: AnalysisJob["result"] & {
    stocks_analyzed?: number;
    trade_date?: string;
    top_recommendations?: Recommendation[];
  };
};

export async function startAnalysisJob(mode: TradeMode = "swing", targetDate?: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 600000);
  try {
    return await fetchJson<AnalysisStartResponse>("/api/analysis/run", {
      method: "POST",
      body: JSON.stringify({ mode, target_date: targetDate || null }),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}

export async function getAnalysisJob(jobId: string) {
  return fetchJson<AnalysisJob>(`/api/analysis/status/${jobId}`);
}

export async function getActiveAnalysisJob() {
  return fetchJson<AnalysisJob>("/api/analysis/active");
}

export async function healthCheck() {
  return fetchJson<{ status: string; supabase: boolean; huggingface: boolean }>("/health");
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function waitForAnalysisJob(
  jobId: string,
  onProgress?: (job: AnalysisJob) => void,
  pollMs = 1500,
  maxWaitMs = 600000
): Promise<AnalysisJob> {
  const started = Date.now();
  while (Date.now() - started < maxWaitMs) {
    const job = await getAnalysisJob(jobId);
    onProgress?.(job);
    if (job.status === "completed") return job;
    if (job.status === "failed") {
      throw new Error(job.error || "Analysis failed");
    }
    await sleep(pollMs);
  }
  throw new Error("Analysis timed out. Check back in a minute and refresh the page.");
}

export type BacktestResult = {
  rank: number;
  symbol: string;
  display_symbol: string;
  name: string;
  sector: string | null;
  is_undervalued: boolean;
  composite_score: number;
  rsi: number | null;
  macd: number | null;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  outcome: "target_hit" | "stopped_out" | "held" | "insufficient_data";
  exit_price: number;
  exit_date: string | null;
  return_pct: number;
};

export type BacktestResponse = {
  mode: TradeMode;
  start_date: string;
  check_days: number;
  metrics: {
    win_rate: number;
    avg_return: number;
    total_picks: number;
    target_hits: number;
    stop_hits: number;
    held: number;
    index_return: number;
    outperformance: number;
  };
  results: BacktestResult[];
  errors: string[];
};

export async function runBacktest(mode: TradeMode, startDate: string, checkDays = 5) {
  return fetchJson<BacktestResponse>("/api/backtest/simulate", {
    method: "POST",
    body: JSON.stringify({ mode, start_date: startDate, check_days: checkDays }),
  });
}

export type UserWatchlistItem = {
  symbol: string;
  display_symbol: string;
  name: string;
  sector: string;
  price: number;
  change_pct: number;
};

export type UserPortfolioItem = {
  symbol: string;
  display_symbol: string;
  name: string;
  shares_quantity: number;
  buy_price: number;
  current_price: number;
  investment: number;
  current_value: number;
  profit_loss: number;
  profit_loss_pct: number;
};

export type UserPortfolioResponse = {
  summary: {
    total_investment: number;
    total_current_value: number;
    total_profit_loss: number;
    total_profit_loss_pct: number;
  };
  holdings: UserPortfolioItem[];
};

export async function syncWatchlist() {
  return fetchJson<{
    success: boolean;
    large_count: number;
    mid_count: number;
    small_count: number;
    updated_at: string;
  }>("/api/watchlist/sync", { method: "POST" });
}

export async function getUserWatchlist(userId: string) {
  return fetchJson<{ watchlist: UserWatchlistItem[] }>(`/api/user/watchlist?user_id=${userId}`);
}

export async function addToWatchlist(userId: string, symbol: string) {
  return fetchJson<{ success: boolean }>("/api/user/watchlist/add", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, symbol }),
  });
}

export async function removeFromWatchlist(userId: string, symbol: string) {
  return fetchJson<{ success: boolean }>("/api/user/watchlist/remove", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, symbol }),
  });
}

export async function getUserPortfolio(userId: string) {
  return fetchJson<UserPortfolioResponse>(`/api/user/portfolio?user_id=${userId}`);
}

export async function buyHolding(userId: string, symbol: string, quantity: number, buyPrice: number) {
  return fetchJson<{ success: boolean }>("/api/user/portfolio/buy", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, symbol, quantity, buy_price: buyPrice }),
  });
}

export async function sellHolding(userId: string, symbol: string, quantity: number) {
  return fetchJson<{ success: boolean }>("/api/user/portfolio/sell", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, symbol, quantity }),
  });
}

export type UserRoleProfile = {
  id?: string;
  user_id: string;
  email: string;
  role: "admin" | "user";
  permissions: {
    can_view_charts: boolean;
    can_view_recommendations: boolean;
    can_view_heatmap: boolean;
    can_view_signals: boolean;
    can_backtest: boolean;
    can_use_portfolio: boolean;
  };
  offline_password?: string;
  created_at?: string;
};

export type AdminTrade = {
  id?: string;
  symbol: string;
  display_symbol?: string;
  shares_quantity: number;
  buy_price: number;
  sell_price: number | null;
  trade_status: "open" | "closed";
  profit_loss: number | null;
  created_at?: string;
};

export async function getUserProfile(userId: string, email?: string) {
  const q = email ? `&email=${email}` : "";
  return fetchJson<UserRoleProfile>(`/api/user/profile?user_id=${userId}${q}`);
}

export async function adminGetUsers() {
  return fetchJson<{ users: UserRoleProfile[] }>("/api/admin/users");
}

export async function adminCreateUser(email: string, password: string) {
  return fetchJson<{ success: boolean; profile: UserRoleProfile }>("/api/admin/user/create", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function adminSetPermissions(userId: string, permissions: UserRoleProfile["permissions"]) {
  return fetchJson<{ success: boolean }>("/api/admin/user/permissions", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, permissions }),
  });
}

export async function adminGetTrades() {
  return fetchJson<{ trades: AdminTrade[] }>("/api/admin/trades");
}

export async function adminBuyTrade(symbol: string, quantity: number, buyPrice: number) {
  return fetchJson<{ success: boolean }>("/api/admin/trades/buy", {
    method: "POST",
    body: JSON.stringify({ symbol, quantity, buy_price: buyPrice }),
  });
}

export async function adminSellTrade(tradeId: string, sellPrice: number) {
  return fetchJson<{ success: boolean }>("/api/admin/trades/sell", {
    method: "POST",
    body: JSON.stringify({ trade_id: tradeId, sell_price: sellPrice }),
  });
}
export async function sendTelegramTest() {
  return fetchJson<{ success: boolean; message: string }>("/api/telegram/test", {
    method: "POST",
  });
}
