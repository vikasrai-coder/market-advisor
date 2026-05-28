"use client";

import React, { useEffect, useState } from "react";
import { getSignals, type TradingSignal } from "@/lib/api";
import { SignalList } from "./SignalList";
import { BuyStockModal } from "./BuyStockModal";
import { createClient } from "@/lib/supabase/client";

export function SignalsPage() {
  const [buy, setBuy] = useState<TradingSignal[]>([]);
  const [sell, setSell] = useState<TradingSignal[]>([]);
  const [userId, setUserId] = useState<string>("");

  // Modal State
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [defaultPrice, setDefaultPrice] = useState(0);
  const [defaultTarget, setDefaultTarget] = useState<number | null>(null);
  const [defaultStopLoss, setDefaultStopLoss] = useState<number | null>(null);

  useEffect(() => {
    getSignals()
      .then((data) => {
        const all = data.signals ?? [];
        setBuy(all.filter((s) => s.signal_type === "buy"));
        setSell(all.filter((s) => s.signal_type === "sell"));
      })
      .catch(() => {});

    async function loadUser() {
      const offlineId = localStorage.getItem("offline_user_id");
      if (offlineId) {
        setUserId(offlineId);
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
  }, []);

  const handleBuyClick = (symbol: string, price: number, target: number | null, stop: number | null) => {
    setSelectedSymbol(symbol);
    setDefaultPrice(price);
    setDefaultTarget(target);
    setDefaultStopLoss(stop);
    setModalOpen(true);
  };

  return (
    <div className="space-y-10">
      <section>
        <h2 className="mb-3 text-lg font-black text-emerald-400 tracking-wide">Buy signals</h2>
        <SignalList signals={buy} onBuyClick={handleBuyClick} />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-black text-rose-400 tracking-wide">Sell signals</h2>
        <SignalList signals={sell} />
      </section>

      {selectedSymbol && (
        <BuyStockModal
          open={modalOpen}
          onCancel={() => setModalOpen(false)}
          onSuccess={() => setModalOpen(false)}
          symbol={selectedSymbol}
          displaySymbol={selectedSymbol.replace(".NS", "").replace(".BO", "")}
          defaultPrice={defaultPrice}
          defaultTarget={defaultTarget}
          defaultStopLoss={defaultStopLoss}
          userId={userId || "default-trader-admin"}
        />
      )}
    </div>
  );
}
