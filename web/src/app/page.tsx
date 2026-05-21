import { Dashboard } from "@/components/Dashboard";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <section className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Today&apos;s top 10 stocks to buy
        </h1>
        <p className="mt-2 max-w-2xl text-slate-400">
          AI-powered picks from trend analysis, technical indicators (RSI, MACD, moving averages),
          FinBERT news sentiment, and Hugging Face reasoning — signals generated today for
          tomorrow&apos;s trading plan.
        </p>
      </section>
      <Dashboard />
    </div>
  );
}
