import React from "react";
import type { TradingSignal } from "@/lib/api";

export function SignalList({
  signals,
  onBuyClick,
}: {
  signals: TradingSignal[];
  onBuyClick?: (symbol: string, price: number, target: number | null, stopLoss: number | null) => void;
}) {
  if (!signals.length) {
    return <p className="text-sm text-slate-500">No signals yet. Run analysis to generate buy/sell signals.</p>;
  }

  return (
    <ul className="space-y-3">
      {signals.map((s, index) => (
        <li
          key={s.id ?? `${s.symbol}-${s.signal_type}-${s.planned_trade_date}-${index}`}
          className="flex flex-col gap-3 rounded-xl border border-slate-800/80 bg-slate-900/35 px-5 py-4 sm:flex-row sm:items-center sm:justify-between hover:border-slate-700/60 transition-all duration-200"
        >
          <div className="flex-1">
            <div className="flex items-center flex-wrap gap-2">
              <span
                className={`inline-block rounded px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                  s.signal_type === "buy"
                    ? "bg-emerald-900/60 text-emerald-300 border border-emerald-500/20"
                    : s.signal_type === "sell"
                      ? "bg-rose-900/60 text-rose-300 border border-rose-500/20"
                      : "bg-slate-800 text-slate-300 border border-slate-700/20"
                }`}
              >
                {s.signal_type}
              </span>
              <span className="font-extrabold text-white text-base">
                {s.symbol.replace(".NS", "").replace(".BO", "")}
              </span>
              <span className="text-xs text-slate-500 font-semibold">{s.stocks?.name}</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-400 line-clamp-2">{s.rationale}</p>
          </div>
          <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-3 shrink-0">
            <div className="text-right text-xs text-slate-500 leading-normal font-medium">
              <p>Trade date: <strong className="text-slate-400">{s.planned_trade_date}</strong></p>
              {s.price_at_signal != null && (
                <p>Price: <strong className="text-slate-300">₹{Number(s.price_at_signal).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong></p>
              )}
              {s.target_price != null && (
                <p className="text-emerald-400 font-semibold">
                  Target: ₹{Number(s.target_price).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
              )}
              {s.stop_loss != null && (
                <p className="text-rose-400 font-semibold">
                  SL: ₹{Number(s.stop_loss).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </p>
              )}
            </div>
            {s.signal_type === "buy" && onBuyClick && (
              <button
                onClick={() => onBuyClick(s.symbol, s.price_at_signal || 0.0, s.target_price, s.stop_loss)}
                className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-slate-100 text-xs font-black rounded-lg uppercase tracking-wider shadow-md hover:shadow-emerald-500/25 transition-all duration-200 cursor-pointer flex items-center gap-1.5 shrink-0 border border-emerald-500/20"
              >
                <span>🛒 BUY STOCK</span>
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
