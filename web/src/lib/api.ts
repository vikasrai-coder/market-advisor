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
  stocks?: {
    name: string;
    sector: string;
    pe_ratio: number;
    market_cap: number;
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
