import type { TradingSignal } from "@/lib/api";

export function SignalList({ signals }: { signals: TradingSignal[] }) {
  if (!signals.length) {
    return <p className="text-sm text-slate-500">No signals yet. Run analysis to generate buy/sell signals.</p>;
  }

  return (
    <ul className="space-y-3">
      {signals.map((s) => (
        <li
          key={s.id}
          className="flex flex-col gap-2 rounded-lg border border-slate-700/60 bg-slate-900/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <span
              className={`inline-block rounded px-2 py-0.5 text-xs font-bold uppercase ${
                s.signal_type === "buy"
                  ? "bg-emerald-900/60 text-emerald-300"
                  : s.signal_type === "sell"
                    ? "bg-red-900/60 text-red-300"
                    : "bg-slate-700 text-slate-300"
              }`}
            >
              {s.signal_type}
            </span>
            <span className="ml-2 font-semibold text-white">{s.symbol}</span>
            <span className="ml-2 text-xs text-slate-500">{s.stocks?.name}</span>
            <p className="mt-1 text-sm text-slate-400 line-clamp-2">{s.rationale}</p>
          </div>
          <div className="text-right text-xs text-slate-500 shrink-0">
            <p>Trade date: {s.planned_trade_date}</p>
            {s.price_at_signal != null && <p>@${Number(s.price_at_signal).toFixed(2)}</p>}
            {s.target_price != null && (
              <p className="text-emerald-500">Target ${Number(s.target_price).toFixed(2)}</p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
