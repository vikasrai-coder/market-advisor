"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { type Recommendation, getStockDetail } from "@/lib/api";
import { BuyStockModal } from "./BuyStockModal";
import { createClient } from "@/lib/supabase/client";

interface RecommendationCardProps {
  rec: Recommendation;
  userId?: string;
}

// ── Confidence Tier Logic ────────────────────────────────────────────────

type ConfidenceTier = "S" | "A" | "B" | "C";

function getConfidenceTier(score: number): ConfidenceTier {
  if (score >= 90) return "S";
  if (score >= 80) return "A";
  if (score >= 70) return "B";
  return "C";
}

const TIER_CONFIG: Record<
  ConfidenceTier,
  {
    label: string;
    icon: string;
    bgClass: string;
    textClass: string;
    borderClass: string;
    glowClass: string;
  }
> = {
  S: {
    label: "S-TIER",
    icon: "⚡",
    bgClass: "bg-gradient-to-r from-amber-500/20 to-yellow-500/20",
    textClass: "text-amber-300",
    borderClass: "border-amber-400/40",
    glowClass: "shadow-[0_0_12px_rgba(245,158,11,0.25)] animate-pulse",
  },
  A: {
    label: "A-TIER",
    icon: "✓",
    bgClass: "bg-emerald-500/15",
    textClass: "text-emerald-300",
    borderClass: "border-emerald-500/30",
    glowClass: "",
  },
  B: {
    label: "B-TIER",
    icon: "⚠",
    bgClass: "bg-amber-500/10",
    textClass: "text-amber-400",
    borderClass: "border-amber-500/25",
    glowClass: "",
  },
  C: {
    label: "C-TIER",
    icon: "✕",
    bgClass: "bg-red-500/10",
    textClass: "text-red-400",
    borderClass: "border-red-500/25",
    glowClass: "",
  },
};

// Self-learning brain default threshold (updated by API if available)
const BRAIN_THRESHOLD = 85;

// ── Component ────────────────────────────────────────────────────────────

export function RecommendationCard({ rec, userId: propUserId }: RecommendationCardProps) {
  const stock = rec.stocks;
  const mode = rec.trade_mode || "swing";

  const [modalOpen, setModalOpen] = useState(false);
  const [livePrice, setLivePrice] = useState<number>(0);
  const [userId, setUserId] = useState<string>("test-trader-1");
  const [showBreakdown, setShowBreakdown] = useState(false);

  useEffect(() => {
    if (propUserId) {
      setUserId(propUserId);
      return;
    }
    async function loadUser() {
      const storedId = localStorage.getItem("offline_user_id") || sessionStorage.getItem("impersonated_id");
      if (storedId) {
        setUserId(storedId);
        return;
      }
      try {
        const supabase = createClient();
        const { data } = await supabase.auth.getUser();
        if (data?.user?.id) {
          setUserId(data.user.id);
        }
      } catch {}
    }
    loadUser();
  }, [propUserId]);

  const handleOpenBuy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setModalOpen(true);
    try {
      const detail = await getStockDetail(rec.symbol);
      const price = (detail.metrics?.[0]?.price as number) || (detail.stock?.fiftyTwoWeekLow as number) || 100.0;
      setLivePrice(price);
    } catch (err) {
      setLivePrice(100.0);
    }
  };

  // Confidence tier
  const tier = getConfidenceTier(rec.composite_score);
  const tierCfg = TIER_CONFIG[tier];
  const isBrainApproved = rec.composite_score >= BRAIN_THRESHOLD;

  // Accent styles per mode
  const getAccentStyles = () => {
    switch (mode) {
      case "intraday":
        return {
          text: "text-sky-400",
          borderHover: "hover:border-sky-500/50 hover:bg-slate-800/80",
          badgeBg: "bg-sky-950/40 text-sky-300 border border-sky-500/20",
        };
      case "longterm":
        return {
          text: "text-purple-400",
          borderHover: "hover:border-purple-500/50 hover:bg-slate-800/80",
          badgeBg: "bg-purple-950/40 text-purple-300 border border-purple-500/20",
        };
      case "future":
        return {
          text: "text-amber-400",
          borderHover: "hover:border-amber-500/50 hover:bg-slate-800/80",
          badgeBg: "bg-amber-950/40 text-amber-300 border border-amber-500/20",
        };
      case "swing":
      default:
        return {
          text: "text-emerald-400",
          borderHover: "hover:border-emerald-500/50 hover:bg-slate-800/80",
          badgeBg: "bg-emerald-950/40 text-emerald-300 border border-emerald-500/20",
        };
    }
  };

  const style = getAccentStyles();

  return (
    <>
      <Link
        href={`/stocks/${rec.symbol}`}
        className={`group block rounded-xl border border-slate-700/80 bg-slate-900/60 p-5 transition ${style.borderHover} ${tier === "C" ? "opacity-60" : ""}`}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            {/* Mode badge + cap segment */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${style.badgeBg}`}>
                #{rec.rank} {mode === "intraday" ? "⚡ Intraday" : mode === "longterm" ? "🏦 Long-term" : mode === "future" ? "📅 Future Setup" : "📈 Swing BUY"}
              </span>
              {rec.cap_segment && (
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400 capitalize">
                  {rec.cap_segment}
                </span>
              )}
              {rec.stocks?.is_undervalued && (
                <span className="rounded bg-amber-950/80 text-amber-300 border border-amber-500/25 px-1.5 py-0.5 text-[10px] font-extrabold tracking-wide uppercase shadow-[0_0_8px_rgba(245,158,11,0.15)]">
                  🔥 Under Valued
                </span>
              )}
            </div>

            <h3 className={`mt-2.5 text-xl font-bold text-white ${tier === "C" ? "line-through decoration-red-500/40" : ""}`}>
              {rec.symbol.replace(".NS", "").replace(".BO", "")}
            </h3>
            <p className="text-sm text-slate-400">
              {stock?.name ?? rec.symbol}
              <span className="ml-1 text-slate-600">· NSE</span>
            </p>
          </div>

          {/* Score + Tier Badge */}
          <div className="text-right flex flex-col items-end gap-1.5">
            <p className={`text-2xl font-black tracking-tight ${style.text}`}>{rec.composite_score}</p>
            <p className="text-xs text-slate-500 font-medium">composite</p>

            {/* Confidence Tier Badge */}
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold tracking-wider uppercase border ${tierCfg.bgClass} ${tierCfg.textClass} ${tierCfg.borderClass} ${tierCfg.glowClass}`}
              title={`Confidence Tier: ${tierCfg.label} (score ${rec.composite_score})`}
            >
              <span>{tierCfg.icon}</span>
              {tierCfg.label}
            </span>

            {/* Brain Approved Badge */}
            {isBrainApproved && (
              <span
                className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/25"
                title={`Self-learning system requires minimum score of ${BRAIN_THRESHOLD} based on rolling win rate`}
              >
                🧠 BRAIN OK
              </span>
            )}
            {!isBrainApproved && (
              <span
                className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wider uppercase bg-red-500/10 text-red-400 border border-red-500/20"
                title={`Below self-learning threshold of ${BRAIN_THRESHOLD} — system would filter this signal`}
              >
                ⛔ BELOW BAR
              </span>
            )}
          </div>
        </div>

        <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-slate-300">{rec.reasoning}</p>

        {/* Mode-specific metrics */}
        {mode === "intraday" && rec.vwap && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs border-t border-slate-800/55 pt-3">
            <span className="rounded bg-sky-950/20 px-2 py-1 text-sky-300">
              VWAP: <strong className="text-white">₹{rec.vwap.toFixed(2)}</strong>
            </span>
            {rec.bullish_crossover && (
              <span className="rounded bg-emerald-950/30 px-2 py-1 text-emerald-300 font-medium border border-emerald-500/10">
                MACD Crossover
              </span>
            )}
          </div>
        )}

        {mode === "longterm" && (
          <div className="mt-3 space-y-2.5 border-t border-slate-800/55 pt-3">
            <div className="flex flex-wrap gap-2 text-xs">
              {rec.pe_ratio && (
                <span className="rounded bg-purple-950/25 px-2 py-1 text-purple-300">
                  P/E: <strong className="text-white">{rec.pe_ratio.toFixed(1)}</strong>
                </span>
              )}
              {rec.dividend_yield !== undefined && (
                <span className="rounded bg-purple-950/25 px-2 py-1 text-purple-300">
                  Yield: <strong className="text-white">{(rec.dividend_yield * 100).toFixed(2)}%</strong>
                </span>
              )}
              {rec.golden_cross && (
                <span className="rounded bg-amber-950/30 px-2 py-1 text-amber-300 font-bold border border-amber-500/10">
                  ✨ Golden Cross
                </span>
              )}
            </div>
            
            {rec.range_52w_pct !== undefined && (
              <div className="space-y-1">
                <div className="flex justify-between text-xxs text-slate-500">
                  <span>52W Low</span>
                  <span className="font-semibold text-slate-400">Position: {rec.range_52w_pct.toFixed(0)}%</span>
                  <span>52W High</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-purple-500 to-indigo-500"
                    style={{ width: `${rec.range_52w_pct}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
          <ScorePill label="Trend" value={rec.trend_score} />
          <ScorePill label="Technical" value={rec.technical_score} />
          {mode === "longterm" && rec.fundamental_score ? (
            <ScorePill label="Fundamental" value={rec.fundamental_score} />
          ) : (
            <ScorePill label="News" value={rec.news_score} />
          )}
        </div>

        {rec.key_factors?.length > 0 && (
          <ul className="mt-3.5 flex flex-wrap gap-1.5">
            {rec.key_factors.slice(0, 3).map((f, i) => (
              <li key={`${rec.symbol}-factor-${i}`} className="rounded-full bg-slate-800/70 px-2 py-0.5 text-xxs text-slate-400">
                {f}
              </li>
            ))}
          </ul>
        )}

        {/* Footer actions */}
        <div className="mt-3.5 flex items-center justify-between border-t border-slate-800/40 pt-2.5">
          <div className="flex items-center gap-2">
            <button
              onClick={handleOpenBuy}
              className="px-3.5 py-1.5 bg-emerald-500/10 text-emerald-400 rounded-md border border-emerald-500/25 hover:bg-emerald-500 hover:text-black font-extrabold text-[10px] uppercase transition-all duration-300 flex items-center gap-1 cursor-pointer"
            >
              🛒 Buy Stock
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setShowBreakdown((prev) => !prev);
              }}
              className="px-2.5 py-1.5 bg-slate-800 text-slate-400 hover:text-slate-200 rounded-md border border-slate-700/60 text-[10px] font-bold transition cursor-pointer"
            >
              {showBreakdown ? "Hide Breakdown ▲" : "Why this score? ▼"}
            </button>
          </div>
          <span className="text-xxs text-slate-500 flex items-center gap-1.5">
            <span>Target: <span className="font-medium text-slate-400">{rec.trade_date}</span></span>
            <span>·</span>
            <span>AI Conf: <strong className="text-slate-300 font-semibold">{(rec.ai_confidence * 100).toFixed(0)}%</strong></span>
          </span>
        </div>

        {/* Expandable Confidence Breakdown Panel */}
        {showBreakdown && (
          <div
            className="mt-3 rounded-lg bg-slate-950/80 p-3.5 border border-slate-800 text-xs space-y-2.5"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-bold text-slate-300 text-[11px] uppercase tracking-wider mb-1">🔍 Score Explanation Engine</p>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Trend Alignment</span>
                <span className="font-bold text-slate-200">{(rec.trend_score ?? 50).toFixed(0)} / 100</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full"
                  style={{ width: `${Math.min(100, rec.trend_score ?? 50)}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Technical Conviction</span>
                <span className="font-bold text-slate-200">{(rec.technical_score ?? 50).toFixed(0)} / 100</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-sky-500 rounded-full"
                  style={{ width: `${Math.min(100, rec.technical_score ?? 50)}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">News & Macro Sentiment</span>
                <span className="font-bold text-slate-200">{(rec.news_score ?? 50).toFixed(0)} / 100</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full"
                  style={{ width: `${Math.min(100, rec.news_score ?? 50)}%` }}
                />
              </div>
            </div>

            <div className="space-y-1.5 pt-1 border-t border-slate-800/80">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 font-medium">Self-Learning Threshold Check</span>
                <span className={`font-bold ${isBrainApproved ? "text-cyan-400" : "text-red-400"}`}>
                  {isBrainApproved ? "PASS (≥85)" : "BELOW BAR (<85)"}
                </span>
              </div>
            </div>
          </div>
        )}
      </Link>

      <BuyStockModal
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onSuccess={() => setModalOpen(false)}
        symbol={rec.symbol}
        displaySymbol={rec.symbol.replace(".NS", "").replace(".BO", "")}
        defaultPrice={livePrice || 100.0}
        defaultTarget={livePrice ? Math.round(livePrice * 1.10 * 100) / 100 : null}
        defaultStopLoss={livePrice ? Math.round(livePrice * 0.97 * 100) / 100 : null}
        userId={userId}
      />
    </>
  );
}

function ScorePill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-800/50 py-2 border border-slate-800">
      <p className="text-xxs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="font-bold text-slate-200 mt-0.5">{value?.toFixed?.(0) ?? value}</p>
    </div>
  );
}
