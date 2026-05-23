import Link from "next/link";
import { getStockDetail } from "@/lib/api";
import { TradingViewChart } from "@/components/TradingViewChart";

export default async function StockPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();

  let data: Awaited<ReturnType<typeof getStockDetail>> | null = null;
  let error: string | null = null;
  try {
    data = await getStockDetail(sym);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load";
  }

  const stock = data?.stock as Record<string, unknown> | null;
  const metrics = (data?.metrics ?? []) as Record<string, unknown>[];
  const news = (data?.news ?? []) as Record<string, unknown>[];
  const latest = data?.latest_recommendation;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <Link href="/" className="text-sm text-emerald-400 hover:underline">
        ← Back to recommendations
      </Link>
      <h1 className="mt-4 text-3xl font-bold text-white">{sym}</h1>
      {error && <p className="mt-2 text-red-400">{error}</p>}
      {stock && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <Info label="Company" value={String(stock.name ?? "—")} />
          <Info label="Sector" value={String(stock.sector ?? "—")} />
          <Info label="P/E" value={stock.pe_ratio != null ? String(stock.pe_ratio) : "—"} />
          <Info label="Beta" value={stock.beta != null ? String(stock.beta) : "—"} />
          <Info label="52W High" value={stock.fifty_two_week_high != null ? `₹${Number(stock.fifty_two_week_high).toLocaleString("en-IN")}` : "—"} />
          <Info label="52W Low" value={stock.fifty_two_week_low != null ? `₹${Number(stock.fifty_two_week_low).toLocaleString("en-IN")}` : "—"} />
        </div>
      )}

      {/* Dynamic TradingView Chart Panel */}
      <section className="mt-8">
        <h2 className="mb-4 text-lg font-semibold text-white">Interactive Chart Study</h2>
        <TradingViewChart symbol={sym} />
      </section>

      {latest && (
        <section className="mt-8 rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-5">
          <h2 className="font-semibold text-emerald-300">Latest AI recommendation</h2>
          <p className="mt-2 text-slate-300">{latest.reasoning}</p>
          <p className="mt-2 text-sm text-slate-500">
            Composite {latest.composite_score} · Trade date {latest.trade_date}
          </p>
        </section>
      )}

      {metrics[0] && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-white">Technical snapshot</h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
            <Metric label="Price" value={`₹${Number(metrics[0].price).toLocaleString("en-IN")}`} />
            <Metric label="Change %" value={`${metrics[0].change_pct}%`} />
            <Metric label="RSI" value={String(metrics[0].rsi ?? "—")} />
            <Metric label="Trend" value={String(metrics[0].trend_score ?? "—")} />
          </div>
        </section>
      )}

      {news.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-white">Recent news</h2>
          <ul className="mt-3 space-y-3">
            {news.map((n) => (
              <li key={String(n.id)} className="rounded-lg border border-slate-800 p-4">
                <p className="font-medium text-slate-200">{String(n.title)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {String(n.sentiment_label)} · {n.source ? String(n.source) : ""}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-900/60 px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-medium text-white">{value}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-800/80 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}
