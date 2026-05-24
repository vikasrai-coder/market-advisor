"use client";

import React, { useEffect, useRef, useState } from "react";

const WIDGET_SCRIPT_SRC = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
const OVERVIEW_SCRIPT_SRC = "https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js";

export function TradingViewChart({ symbol }: { symbol: string }) {
  const advancedRef = useRef<HTMLDivElement>(null);
  const overviewRef = useRef<HTMLDivElement>(null);

  // Normalize symbol: WIPRO.NS -> NSE:WIPRO, WIPRO.BO -> BSE:WIPRO, AAPL -> NASDAQ:AAPL
  const formatSymbol = (sym: string): string => {
    const s = sym.toUpperCase();
    if (s.endsWith(".NS")) return `NSE:${s.replace(".NS", "")}`;
    if (s.endsWith(".BO")) return `BSE:${s.replace(".BO", "")}`;
    // US stock — TradingView auto-resolves most US tickers
    return s;
  };

  const isIndian = symbol.toUpperCase().endsWith(".NS") || symbol.toUpperCase().endsWith(".BO");
  const tvSymbol = formatSymbol(symbol);
  const cleanSymbol = symbol.replace(".NS", "").replace(".BO", "").toUpperCase();

  const [activeTab, setActiveTab] = useState<"advanced" | "overview">(isIndian ? "overview" : "advanced");
  const [loaded, setLoaded] = useState(false);

  // TradingView link
  const tvUrl = isIndian
    ? `https://www.tradingview.com/symbols/${tvSymbol.replace(":", "-")}/`
    : `https://www.tradingview.com/chart/?symbol=${tvSymbol}`;

  // ── Advanced Chart Widget ─────────────────────────────────────────────────
  useEffect(() => {
    if (activeTab !== "advanced" || !advancedRef.current) return;
    const container = advancedRef.current;
    container.innerHTML = "";
    setLoaded(false);

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";
    widgetDiv.style.height = "calc(100% - 32px)";
    widgetDiv.style.width = "100%";

    const config = {
      autosize: true,
      symbol: tvSymbol,
      interval: "D",
      timezone: "Asia/Kolkata",
      theme: "dark",
      style: "1",
      locale: "en",
      backgroundColor: "rgba(9, 11, 23, 1)",
      gridColor: "rgba(30, 41, 59, 0.5)",
      withdateranges: true,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      calendar: false,
      support_host: "https://www.tradingview.com",
      studies: [
        "STD;RSI",
        "STD;MACD",
        "STD;Bollinger_Bands",
        "STD;Volume",
      ],
      show_popup_button: true,
      popup_width: "1000",
      popup_height: "650",
    };

    const script = document.createElement("script");
    script.src = WIDGET_SCRIPT_SRC;
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify(config);
    script.onload = () => setLoaded(true);

    container.appendChild(widgetDiv);
    container.appendChild(script);

    // We do NOT clear container on unmount to prevent s3.tradingview.com querySelector errors.
  }, [tvSymbol, activeTab]);

  // ── Symbol Overview Widget ───────────────────────────────────────────────
  useEffect(() => {
    if (activeTab !== "overview" || !overviewRef.current) return;
    const container = overviewRef.current;
    container.innerHTML = "";
    setLoaded(false);

    // For Indian stocks, TradingView overview widget needs NSE:SYMBOL format
    // For US stocks, just the ticker
    const symbols = isIndian
      ? [[cleanSymbol, tvSymbol]]
      : [[cleanSymbol, tvSymbol]];

    const config = {
      symbols,
      chartOnly: false,
      width: "100%",
      height: "100%",
      locale: "en",
      colorTheme: "dark",
      autosize: true,
      showVolume: false,
      showMA: true,
      hideDateRanges: false,
      hideMarketStatus: false,
      hideSymbolLogo: false,
      scalePosition: "right",
      scaleMode: "Normal",
      fontFamily: "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
      fontSize: "10",
      noTimeScale: false,
      valuesTracking: "1",
      changeMode: "price-and-percent",
      chartType: "area",
      maLineColor: "#2962FF",
      maLineWidth: 1,
      maLength: 9,
      backgroundColor: "rgba(9, 11, 23, 1)",
      lineWidth: 2,
      lineType: 0,
      dateRanges: ["1d|1", "1m|30", "3m|60", "12m|1D", "60m|1W", "all|1M"],
    };

    const widgetDiv = document.createElement("div");
    widgetDiv.className = "tradingview-widget-container__widget";

    const script = document.createElement("script");
    script.src = OVERVIEW_SCRIPT_SRC;
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify(config);
    script.onload = () => setLoaded(true);

    container.appendChild(widgetDiv);
    container.appendChild(script);

    // We do NOT clear container on unmount to prevent s3.tradingview.com querySelector errors.
  }, [tvSymbol, activeTab, isIndian, cleanSymbol]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-[#090b17] shadow-2xl overflow-hidden flex flex-col">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 border-b border-slate-800/80 bg-slate-950/60">
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
          <span className="text-[11px] font-black text-slate-200 uppercase tracking-widest">
            {cleanSymbol}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${
            isIndian
              ? "bg-orange-500/10 text-orange-400 border border-orange-500/20"
              : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
          }`}>
            {isIndian ? "NSE · India" : "NASDAQ · US"}
          </span>
        </div>

        {/* View tabs */}
        <div className="flex items-center gap-1 bg-slate-900/70 rounded-lg p-1 border border-slate-800/60">
          {!isIndian && (
            <button
              onClick={() => setActiveTab("advanced")}
              className={`px-3 py-1 rounded-md text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer ${
                activeTab === "advanced"
                  ? "bg-emerald-600 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              📈 Advanced Chart
            </button>
          )}
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-3 py-1 rounded-md text-[10px] font-black uppercase tracking-wider transition-all cursor-pointer ${
              activeTab === "overview"
                ? "bg-blue-600 text-white shadow-[0_0_10px_rgba(59,130,246,0.3)]"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            🔭 Symbol Overview
          </button>
        </div>

        <a
          href={tvUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-emerald-400 hover:text-emerald-300 text-[10px] font-extrabold uppercase tracking-wider border border-slate-700/60 hover:border-emerald-500/30 transition-all flex items-center gap-1.5 cursor-pointer"
        >
          🚀 Full Screen ↗
        </a>
      </div>

      {/* ── Chart body ─────────────────────────────────────────────── */}
      <div className="relative" style={{ height: 520 }}>
        {/* Loading skeleton */}
        {!loaded && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[#090b17]">
            <div className="w-10 h-10 rounded-full border-2 border-emerald-500/30 border-t-emerald-400 animate-spin" />
            <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">
              Loading TradingView Chart…
            </span>
          </div>
        )}

        {/* Advanced Chart */}
        <div
          ref={advancedRef}
          className="tradingview-widget-container"
          style={{
            height: "100%",
            width: "100%",
            display: activeTab === "advanced" ? "block" : "none",
          }}
        />

        {/* Symbol Overview */}
        <div
          ref={overviewRef}
          className="tradingview-widget-container"
          style={{
            height: "100%",
            width: "100%",
            display: activeTab === "overview" ? "block" : "none",
          }}
        />
      </div>

      {/* ── Footer note ────────────────────────────────────────────── */}
      <div className="px-5 py-3 border-t border-slate-800/60 bg-slate-950/40 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[10px] text-slate-500">
        <div className="flex items-center gap-2">
          <span>📊</span>
          <span>
            Powered by{" "}
            <a
              href="https://www.tradingview.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 font-bold underline underline-offset-2"
            >
              TradingView
            </a>
            {" "}· Indicators: RSI, MACD, Bollinger Bands, Volume ·{" "}
            {isIndian ? "Exchange: NSE India" : "Exchange: US Markets"}
          </span>
        </div>
        {isIndian && (
          <span className="text-emerald-500/90 font-medium">
            💡 For full interactive charting, click <strong>Full Screen ↗</strong>
          </span>
        )}
      </div>
    </div>
  );
}
