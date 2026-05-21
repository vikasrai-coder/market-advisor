"use client";

import { useEffect, useState } from "react";
import { getSignals, type TradingSignal } from "@/lib/api";
import { SignalList } from "./SignalList";

export function SignalsPage() {
  const [buy, setBuy] = useState<TradingSignal[]>([]);
  const [sell, setSell] = useState<TradingSignal[]>([]);

  useEffect(() => {
    getSignals()
      .then((data) => {
        const all = data.signals ?? [];
        setBuy(all.filter((s) => s.signal_type === "buy"));
        setSell(all.filter((s) => s.signal_type === "sell"));
      })
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-10">
      <section>
        <h2 className="mb-3 text-lg font-semibold text-emerald-400">Buy signals</h2>
        <SignalList signals={buy} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold text-red-400">Sell signals</h2>
        <SignalList signals={sell} />
      </section>
    </div>
  );
}
