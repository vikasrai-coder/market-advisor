"use client";

import React from "react";
import Link from "next/link";
import { Activity, BarChart3, Bot, Check, ShieldCheck, Sparkles, TrendingUp, Zap } from "lucide-react";

export function Landing() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden flex-1 flex items-center py-20 md:py-28 bg-[radial-gradient(ellipse_at_top,rgba(16,185,129,0.08),transparent_50%)]">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10 w-full">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/50 px-4 py-1.5 text-xs font-semibold text-slate-400 backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
              AI-powered signals for the Indian stock market
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl text-white">
              Trade smarter with{" "}
              <span className="bg-gradient-to-r from-emerald-400 via-teal-300 to-emerald-500 bg-clip-text text-transparent">
                algorithmic signals
              </span>
            </h1>
            <p className="mx-auto mt-6 max-w-xl text-base sm:text-lg text-slate-400 leading-relaxed">
              Daily NSE buy/sell ideas, top-10 ranked recommendations and backtested strategies — built by quants, delivered before market open.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/login"
                className="rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 px-6 py-3.5 text-sm font-bold text-white shadow-[0_0_20px_rgba(16,185,129,0.3)] transition hover:opacity-90 active:scale-[0.98]"
              >
                Start free trial
              </Link>
              <Link
                href="/login"
                className="rounded-lg border border-slate-700 bg-slate-900/40 px-6 py-3.5 text-sm font-bold text-slate-300 hover:border-slate-500 hover:text-white transition"
              >
                Sign in
              </Link>
            </div>

            {/* Stat Row */}
            <div className="mx-auto mt-16 grid max-w-2xl grid-cols-3 gap-4 sm:gap-6">
              {[
                { v: "82%", l: "Avg. confidence" },
                { v: "50+", l: "Signals / day" },
                { v: "12k", l: "Active traders" },
              ].map((s) => (
                <div
                  key={s.l}
                  className="rounded-2xl border border-slate-800 bg-slate-900/30 p-4 sm:p-5 backdrop-blur shadow-xl"
                >
                  <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400">{s.v}</div>
                  <div className="mt-1 text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-slate-500">{s.l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="border-t border-slate-900 bg-slate-950 py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
              Everything you need to trade with conviction
            </h2>
            <p className="mt-4 text-slate-400 text-sm sm:text-base">
              From discovery to execution, all in one dashboard.
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[
              { i: TrendingUp, t: "Top 10 Buys", d: "Ranked daily by composite score across trend, technicals and news sentiment." },
              { i: Zap, t: "Buy / Sell Signals", d: "Entry, target and stop-loss for every signal — issued the evening before the trade." },
              { i: BarChart3, t: "Backtested Strategies", d: "Swing, intraday, long-term and penny scans with verified win rates." },
              { i: Bot, t: "AI Advisor", d: "Ask follow-up questions about any stock and get instant, contextual analysis." },
              { i: Activity, t: "Live Portfolio Tracking", d: "See your positions update in real-time against benchmark indices." },
              { i: ShieldCheck, t: "Risk-first Sizing", d: "Position-size suggestions based on your capital and tolerance." },
            ].map((f) => (
              <div
                key={f.t}
                className="group rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900/60 to-slate-950 p-6 shadow-xl transition-all duration-300 hover:border-emerald-500/30 hover:shadow-[0_0_30px_rgba(16,185,129,0.05)] hover:-translate-y-0.5"
              >
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 group-hover:bg-emerald-500/20 group-hover:text-emerald-300 transition-colors">
                  <f.i className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-bold text-white">{f.t}</h3>
                <p className="mt-2 text-sm text-slate-400 leading-relaxed">{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="border-t border-slate-900 bg-slate-950 py-20 md:py-28">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto mb-16 max-w-2xl text-center">
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
              Simple, transparent pricing
            </h2>
            <p className="mt-4 text-slate-400 text-sm sm:text-base">
              Start free. Upgrade when you're ready.
            </p>
          </div>
          <div className="mx-auto grid gap-6 md:grid-cols-2 max-w-4xl">
            {[
              { name: "Starter", price: "Free", features: ["Top 10 Buys (daily)", "5 signals / week", "Email alerts"], cta: "Start free" },
              { name: "Pro", price: "₹1,499", suffix: "/mo", featured: true, features: ["Unlimited signals", "All strategies", "AI Advisor", "Live portfolio tracking", "Priority support"], cta: "Go Pro" },
            ].map((p) => (
              <div
                key={p.name}
                className={`relative rounded-2xl border p-8 backdrop-blur shadow-xl ${
                  p.featured
                    ? "border-emerald-500 bg-gradient-to-br from-slate-900 to-slate-950/80 shadow-[0_0_40px_rgba(16,185,129,0.06)]"
                    : "border-slate-800 bg-slate-900/20"
                }`}
              >
                {p.featured && (
                  <div className="absolute -top-3 right-6 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 px-3 py-1 text-xs font-bold text-white shadow-md">
                    Most popular
                  </div>
                )}
                <h3 className="text-2xl font-bold text-white">{p.name}</h3>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-5xl font-black text-white tracking-tight">{p.price}</span>
                  {"suffix" in p && p.suffix && <span className="text-slate-500 font-semibold">{p.suffix}</span>}
                </div>
                <ul className="mt-6 space-y-3.5">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm font-medium text-slate-300">
                      <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/login"
                  className={`mt-8 block text-center rounded-lg py-3 text-sm font-bold transition duration-200 ${
                    p.featured
                      ? "bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md hover:opacity-90"
                      : "border border-slate-700 bg-slate-900/40 text-slate-300 hover:border-slate-500 hover:text-white"
                  }`}
                >
                  {p.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t border-slate-900 bg-slate-950 py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-12 text-center md:p-20 shadow-2xl">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.06),transparent_60%)]" />
            <div className="relative z-10">
              <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
                Ready to trade with an edge?
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-slate-400 text-sm sm:text-base leading-relaxed">
                Join thousands of NSE traders who get tomorrow's signals tonight.
              </p>
              <Link
                href="/login"
                className="mt-8 inline-block rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 px-8 py-4 text-sm font-bold text-white shadow-[0_0_20px_rgba(16,185,129,0.3)] transition hover:opacity-90 active:scale-[0.98]"
              >
                Create your account
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
