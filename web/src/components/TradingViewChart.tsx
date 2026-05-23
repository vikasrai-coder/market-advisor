"use client";

import React, { useEffect, useRef } from "react";

export function TradingViewChart({ symbol }: { symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalize suffix (e.g. WIPRO.NS -> NSE:WIPRO)
  const formatSymbol = (sym: string) => {
    const s = sym.toUpperCase();
    if (s.endsWith(".NS")) {
      return `NSE:${s.replace(".NS", "")}`;
    }
    if (s.endsWith(".BO")) {
      return `BSE:${s.replace(".BO", "")}`;
    }
    return `NSE:${s}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;

    containerRef.current.innerHTML = "";

    const widgetContainer = document.createElement("div");
    widgetContainer.id = "tradingview_widget";
    widgetContainer.className = "h-[450px] w-full";
    containerRef.current.appendChild(widgetContainer);

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.type = "text/javascript";
    script.async = true;
    script.onload = () => {
      if (typeof window !== "undefined" && (window as any).TradingView) {
        new (window as any).TradingView.widget({
          autosize: true,
          symbol: formatSymbol(symbol),
          interval: "D",
          timezone: "Asia/Kolkata",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#0f172a",
          enable_publishing: false,
          hide_side_toolbar: false,
          allow_symbol_change: true,
          container_id: "tradingview_widget",
          studies: [
            "RSI@tv-basicstudies",
            "MASimple@tv-basicstudies",
            "MACD@tv-basicstudies"
          ],
        });
      }
    };
    document.head.appendChild(script);
  }, [symbol]);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-1.5 shadow-2xl overflow-hidden">
      <div ref={containerRef} className="h-[450px] w-full" />
    </div>
  );
}
