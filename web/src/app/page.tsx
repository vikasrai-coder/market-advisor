import { Dashboard } from "@/components/Dashboard";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <section className="mb-10">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Top 10 NSE stocks to buy today
        </h1>
        <p className="mt-2 max-w-2xl text-slate-400">
          Scans NSE large, mid, and small cap stocks via Yahoo Finance — trend, RSI/MACD/SMA,
          news sentiment via Hugging Face, and AI reasoning. Signals are for the next trading session
          (NSE/BSE).
        </p>
      </section>
      <Dashboard />
    </div>
  );
}
