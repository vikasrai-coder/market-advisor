const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Recommendation = {
  id: string;
  symbol: string;
  rank: number;
  action: string;
  composite_score: number;
  trend_score: number;
  news_score: number;
  technical_score: number;
  ai_confidence: number;
  reasoning: string;
  key_factors: string[];
  signal_date: string;
  trade_date: string;
  stocks?: {
    name: string;
    sector: string;
    pe_ratio: number;
    market_cap: number;
  };
};

export type TradingSignal = {
  id: string;
  symbol: string;
  signal_type: "buy" | "sell" | "hold";
  strength: string;
  price_at_signal: number;
  target_price: number | null;
  stop_loss: number | null;
  rationale: string;
  signal_date: string;
  planned_trade_date: string;
  stocks?: { name: string; sector: string };
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

export async function getRecommendations(tradeDate?: string) {
  const q = tradeDate ? `?trade_date=${tradeDate}` : "";
  return fetchJson<{ recommendations: Recommendation[]; trade_date: string }>(
    `/api/recommendations${q}`
  );
}

export async function getSignals(plannedDate?: string, signalType?: string) {
  const params = new URLSearchParams();
  if (plannedDate) params.set("planned_trade_date", plannedDate);
  if (signalType) params.set("signal_type", signalType);
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

export async function runAnalysis() {
  return fetchJson<Record<string, unknown>>("/api/analysis/run", { method: "POST" });
}

export async function healthCheck() {
  return fetchJson<{ status: string; supabase: boolean; huggingface: boolean }>("/health");
}
