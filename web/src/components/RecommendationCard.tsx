import Link from "next/link";
import type { Recommendation } from "@/lib/api";

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const stock = rec.stocks;
  return (
    <Link
      href={`/stocks/${rec.symbol}`}
      className="group block rounded-xl border border-slate-700/80 bg-slate-900/60 p-5 transition hover:border-emerald-500/50 hover:bg-slate-800/80"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-xs font-medium text-emerald-400">#{rec.rank} BUY</span>
          <h3 className="mt-1 text-xl font-bold text-white">{rec.symbol}</h3>
          <p className="text-sm text-slate-400">{stock?.name ?? rec.symbol}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-emerald-400">{rec.composite_score}</p>
          <p className="text-xs text-slate-500">composite</p>
        </div>
      </div>
      <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-slate-300">{rec.reasoning}</p>
      <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <ScorePill label="Trend" value={rec.trend_score} />
        <ScorePill label="Technical" value={rec.technical_score} />
        <ScorePill label="News" value={rec.news_score} />
      </div>
      {rec.key_factors?.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {rec.key_factors.slice(0, 3).map((f) => (
            <li key={f} className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              {f}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-slate-500">
        Plan trade: <span className="text-slate-300">{rec.trade_date}</span> · AI confidence{" "}
        {(rec.ai_confidence * 100).toFixed(0)}%
      </p>
    </Link>
  );
}

function ScorePill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-slate-800/80 py-2">
      <p className="text-slate-500">{label}</p>
      <p className="font-semibold text-white">{value?.toFixed?.(0) ?? value}</p>
    </div>
  );
}
