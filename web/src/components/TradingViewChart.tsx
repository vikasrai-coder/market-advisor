"use client";

import React, { useEffect, useRef, useState } from "react";

interface TradingViewChartProps {
  symbol: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function TradingViewChart({ symbol }: { symbol: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanSymbol = symbol.replace(".NS", "").replace(".BO", "").toUpperCase();
  const tvUrl = `https://www.tradingview.com/symbols/NSE-${cleanSymbol}/`;

  // Custom Chart State
  const [metrics, setMetrics] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [hoveredPoint, setHoveredPoint] = useState<any | null>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const isIndianStock = symbol.toUpperCase().endsWith(".NS") || symbol.toUpperCase().endsWith(".BO");

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

  // Fetch metrics history for local interactive chart if it's an Indian stock
  useEffect(() => {
    if (!isIndianStock) {
      setLoading(false);
      return;
    }

    async function fetchHistory() {
      try {
        setLoading(true);
        const res = await fetch(`${API_URL}/api/stocks/${symbol}`);
        if (res.ok) {
          const data = await res.json();
          // Sort chronologically (oldest to newest)
          const sorted = (data.metrics ?? []).reverse();
          setMetrics(sorted);
        }
      } catch (err) {
        console.error("Failed to load local stock metrics:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchHistory();
  }, [symbol, isIndianStock]);

  // Load TradingView Advanced Widget for US Stocks (e.g. AAPL)
  useEffect(() => {
    if (isIndianStock || !containerRef.current) return;

    containerRef.current.innerHTML = "";

    const widgetContainer = document.createElement("div");
    widgetContainer.id = "tradingview_widget";
    widgetContainer.className = "h-[400px] w-full";
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
          allow_symbol_change: false,
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
  }, [symbol, isIndianStock]);

  // Render Custom Chart Math
  const renderCustomChart = () => {
    if (metrics.length === 0) {
      return (
        <div className="h-[400px] w-full flex items-center justify-center border border-slate-900 bg-slate-950/40 rounded-xl">
          <p className="text-xs text-slate-500 font-bold">No historical price metrics loaded for {cleanSymbol}</p>
        </div>
      );
    }

    const width = 720;
    const height = 320;
    const paddingLeft = 50;
    const paddingRight = 20;
    const paddingTop = 25;
    const paddingBottom = 40;

    const prices = metrics.map((m) => Number(m.price || 0));
    const maxPrice = Math.max(...prices);
    const minPrice = Math.min(...prices);
    const priceRange = maxPrice - minPrice || 1;

    // Coordinate mapping
    const points = metrics.map((m, idx) => {
      const x = paddingLeft + (idx / (metrics.length - 1)) * (width - paddingLeft - paddingRight);
      const y = height - paddingBottom - ((Number(m.price || 0) - minPrice) / priceRange) * (height - paddingTop - paddingBottom);
      return { x, y, metric: m };
    });

    const linePath = points.map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z`;

    const handleMouseMove = (e: React.MouseEvent<SVGSVGElement, MouseEvent>) => {
      const svg = e.currentTarget;
      const rect = svg.getBoundingClientRect();
      const clientX = e.clientX - rect.left;
      
      // Map back to coordinates scale
      const scaleX = (clientX / rect.width) * width;
      
      // Find closest X point
      let closestIdx = 0;
      let minDiff = Infinity;
      points.forEach((p, idx) => {
        const diff = Math.abs(p.x - scaleX);
        if (diff < minDiff) {
          minDiff = diff;
          closestIdx = idx;
        }
      });

      setHoverIdx(closestIdx);
      setHoveredPoint(points[closestIdx]);
    };

    const handleMouseLeave = () => {
      setHoverIdx(null);
      setHoveredPoint(null);
    };

    return (
      <div className="relative w-full group">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto bg-slate-950/40 rounded-xl overflow-visible border border-slate-900/60"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Definitions */}
          <defs>
            <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={paddingLeft} y1={paddingTop} x2={width - paddingRight} y2={paddingTop} stroke="#1e293b" strokeDasharray="3" />
          <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} stroke="#1e293b" strokeDasharray="3" />
          <line
            x1={paddingLeft}
            y1={paddingTop + (height - paddingTop - paddingBottom) / 2}
            x2={width - paddingRight}
            y2={paddingTop + (height - paddingTop - paddingBottom) / 2}
            stroke="#1e293b"
            strokeDasharray="3"
          />

          {/* Y Axis Labels */}
          <text x={paddingLeft - 8} y={paddingTop + 4} textAnchor="end" className="fill-slate-500 font-black text-[9px]">
            ₹{maxPrice.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </text>
          <text x={paddingLeft - 8} y={paddingTop + (height - paddingTop - paddingBottom) / 2 + 3} textAnchor="end" className="fill-slate-500 font-black text-[9px]">
            ₹{((maxPrice + minPrice) / 2).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </text>
          <text x={paddingLeft - 8} y={height - paddingBottom + 3} textAnchor="end" className="fill-slate-500 font-black text-[9px]">
            ₹{minPrice.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
          </text>

          {/* Area Fill */}
          <path d={areaPath} fill="url(#chartGradient)" />

          {/* Price Line */}
          <path d={linePath} fill="none" stroke="#10b981" strokeWidth={2.5} strokeLinecap="round" />

          {/* X Axis Date labels (Min and Max dates) */}
          <text x={paddingLeft} y={height - 15} textAnchor="start" className="fill-slate-500 font-bold text-[9px]">
            {metrics[0]?.recorded_at ? new Date(metrics[0].recorded_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) : "Start"}
          </text>
          <text x={width - paddingRight} y={height - 15} textAnchor="end" className="fill-slate-500 font-bold text-[9px]">
            {metrics[metrics.length - 1]?.recorded_at ? new Date(metrics[metrics.length - 1].recorded_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) : "End"}
          </text>

          {/* Hover highlight line */}
          {hoveredPoint && (
            <>
              <line
                x1={hoveredPoint.x}
                y1={paddingTop}
                x2={hoveredPoint.x}
                y2={height - paddingBottom}
                stroke="#334155"
                strokeWidth={1}
                strokeDasharray="2"
              />
              <circle cx={hoveredPoint.x} cy={hoveredPoint.y} r={5} fill="#10b981" className="shadow-lg" />
              <circle cx={hoveredPoint.x} cy={hoveredPoint.y} r={8} fill="none" stroke="#10b981" strokeWidth={1.5} className="animate-ping opacity-60" />
            </>
          )}
        </svg>

        {/* Hover Floating Glassmorphic Tooltip */}
        {hoveredPoint && (
          <div className="absolute top-4 left-[60px] bg-slate-950/90 border border-slate-800 rounded-2xl p-4.5 shadow-2xl backdrop-blur-md text-slate-300 text-xs min-w-[200px] flex flex-col gap-1.5 animate-fadeIn z-15 pointer-events-none">
            <div className="flex justify-between items-center border-b border-slate-900 pb-1.5 mb-1">
              <span className="font-extrabold text-slate-200">
                {new Date(hoveredPoint.metric.recorded_at).toLocaleDateString("en-IN", {
                  day: "2-digit",
                  month: "long",
                  year: "numeric",
                })}
              </span>
              <span className="px-1.5 py-0.5 rounded text-[8px] font-black tracking-wider uppercase bg-emerald-500/10 text-emerald-400">
                Session Log
              </span>
            </div>
            
            <div className="flex justify-between">
              <span className="text-slate-500 font-bold">Closing Price:</span>
              <span className="font-black text-slate-200">₹{Number(hoveredPoint.metric.price).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
            </div>

            <div className="flex justify-between">
              <span className="text-slate-500 font-bold">Daily Change:</span>
              <span className={`font-black ${Number(hoveredPoint.metric.change_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {Number(hoveredPoint.metric.change_pct || 0) >= 0 ? "+" : ""}{hoveredPoint.metric.change_pct}%
              </span>
            </div>

            {hoveredPoint.metric.rsi && (
              <div className="flex justify-between">
                <span className="text-slate-500 font-bold">RSI (14):</span>
                <span className={`font-black ${hoveredPoint.metric.rsi > 70 ? "text-amber-400" : hoveredPoint.metric.rsi < 30 ? "text-cyan-400" : "text-slate-200"}`}>
                  {Number(hoveredPoint.metric.rsi).toFixed(2)}
                </span>
              </div>
            )}

            {hoveredPoint.metric.volume && (
              <div className="flex justify-between">
                <span className="text-slate-500 font-bold">Volume:</span>
                <span className="font-black text-slate-200">{Number(hoveredPoint.metric.volume).toLocaleString("en-IN")}</span>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 shadow-2xl overflow-hidden flex flex-col gap-6">
      {/* Header bar with direct link */}
      <div className="flex flex-wrap justify-between items-center gap-3 border-b border-slate-900 pb-4">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest flex items-center gap-1.5">
            {isIndianStock ? "✨ Interactive Local Area Study" : `TradingView Chart: ${formatSymbol(symbol)}`}
          </span>
        </div>
        
        <a
          href={tvUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3.5 py-1.5 rounded-lg bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 hover:text-emerald-300 text-[10px] font-extrabold uppercase tracking-wider border border-emerald-500/20 hover:border-emerald-500/40 transition-all flex items-center gap-1.5 cursor-pointer shadow-[0_0_12px_rgba(16,185,129,0.05)] hover:shadow-[0_0_15px_rgba(16,185,129,0.15)]"
        >
          🚀 Open Full Chart on TradingView ↗
        </a>
      </div>

      {/* Embedded Chart */}
      {loading ? (
        <div className="h-[320px] w-full flex flex-col items-center justify-center gap-3 border border-slate-900 bg-slate-950/40 rounded-xl animate-pulse">
          <svg className="animate-spin h-6 w-6 text-emerald-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Loading local indicators study...</span>
        </div>
      ) : isIndianStock ? (
        renderCustomChart()
      ) : (
        <div ref={containerRef} className="h-[400px] w-full rounded-xl overflow-hidden border border-slate-900 bg-slate-950 shadow-inner" />
      )}
      
      {/* Premium Alert Notice */}
      <div className="text-[10px] text-slate-400 leading-relaxed bg-slate-900/10 border border-slate-900 px-4.5 py-3 rounded-2xl">
        💡 **Interactive Indicators Guide**: 
        {isIndianStock 
          ? " Move your mouse over the green chart area above to inspect historical price logs, daily percentage changes, RSI ratings, and session volumes dynamically."
          : " TradingView restricts embeds of Indian NSE stock data on personal domains. US Stocks (like AAPL) load cleanly, but for NSE stocks, use our local interactive chart study!"
        }
        {" "}You can always click the **🚀 Open Full Chart** button above to load their official advanced charts in a new tab without restrictions.
      </div>
    </div>
  );
}
