import Link from "next/link";
import type { Recommendation } from "@/lib/api";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const stock = rec.stocks;
  const mode = rec.trade_mode || "swing";

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
    <Link
      href={`/stocks/${rec.symbol}`}
      className={`group block rounded-xl border border-slate-700/80 bg-slate-900/60 p-5 transition ${style.borderHover}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${style.badgeBg}`}>
            #{rec.rank} {mode === "intraday" ? "⚡ Intraday" : mode === "longterm" ? "🏦 Long-term" : mode === "future" ? "📅 Future Setup" : "📈 Swing BUY"}
          </span>
          {rec.cap_segment && (
            <span className="ml-1.5 rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400 capitalize">
              {rec.cap_segment}
            </span>
          )}
          <h3 className="mt-2.5 text-xl font-bold text-white">
            {rec.symbol.replace(".NS", "").replace(".BO", "")}
          </h3>
          <p className="text-sm text-slate-400">
            {stock?.name ?? rec.symbol}
            <span className="ml-1 text-slate-600">· NSE</span>
          </p>
        </div>
        <div className="text-right">
          <p className={`text-2xl font-black tracking-tight ${style.text}`}>{rec.composite_score}</p>
          <p className="text-xs text-slate-500 font-medium">composite</p>
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

      <p className="mt-3.5 text-xs text-slate-500 flex items-center justify-between border-t border-slate-800/40 pt-2.5">
        <span>Target: <span className="font-medium text-slate-400">{rec.trade_date}</span></span>
        <span>AI Confidence: <strong className="text-slate-300 font-semibold">{(rec.ai_confidence * 100).toFixed(0)}%</strong></span>
      </p>
    </Link>
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
