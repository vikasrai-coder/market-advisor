import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable
import pandas as pd
import yfinance as yf
import logging
logger = logging.getLogger(__name__)

from app.config import settings
from app.scan_modes import ScanConfig, get_config
from app.services import hf_ai, market_data, supabase_store, technicals
from app.services.supabase_store import get_client
from app.services.sector_rs import (
    get_today_market_context,
    get_sector_relative_strength,
    _normalize_sector,
)

_last_result: dict[str, Any] | None = None
ProgressCallback = Callable[[int, int, str, str], None]


def get_last_result() -> dict[str, Any] | None:
    return _last_result


def run_full_analysis(
    mode: str = "swing",
    target_date: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run analysis in the specified mode.

    Args:
        mode: One of "intraday", "swing", "longterm", "future".
        target_date: ISO date string for "future" mode (e.g. "2025-06-15").
        progress_callback: Optional progress reporter.
    """
    if mode == "future":
        raise NotImplementedError("Future mode not yet implemented")
    global _last_result
    cfg = get_config(mode)

    def report(done: int, total: int, phase: str, message: str) -> None:
        if progress_callback:
            progress_callback(done, total, phase, message)

    # Reconcile past outcomes
    try:
        from app.services.reconciler import reconcile_recommendations
        reconcile_recommendations()
    except Exception:
        pass

    client = get_client()
    signal_date = date.today()

    # Determine trade date based on mode
    if mode == "future" and target_date:
        trade_date = date.fromisoformat(target_date)
    elif mode == "intraday":
        trade_date = signal_date  # same-day trading
    elif mode == "longterm":
        trade_date = signal_date  # entry today
    else:
        trade_date = signal_date + timedelta(days=1)  # swing = next day

    run_id: str | None = None
    if client:
        run_id = supabase_store.start_run(client)
        supabase_store.clear_recommendations_for_date(client, signal_date, trade_mode=mode)
        supabase_store.clear_signals_for_date(client, signal_date, trade_mode=mode)

    # Fetch general market news to assess macro risk / NIFTY conditions
    macro_articles = []
    macro_sentiment_score = 50.0
    macro_headlines = ""
    min_composite_score_override = None
    overnight_gap_down_flag = False
    try:
        from app.services.google_news import fetch_google_news_rss
        macro_articles = fetch_google_news_rss("NIFTY 50", limit=5)
        if macro_articles:
            macro_sentiment_score = hf_ai.score_news_batch(macro_articles)
            macro_headlines = " | ".join(a.get("title", "") for a in macro_articles[:3])
    except Exception as exc:
        print(f"Error fetching macro/NIFTY news: {exc}")

    if macro_sentiment_score < 25:
        min_composite_score_override = 80.0  # raise bar only on extreme panic
        overnight_gap_down_flag = True

    _macro_veto = False
    if macro_sentiment_score < 25:
        _macro_veto = True

    # ENHANCEMENT #4 — Market Breadth Gate (runs ONCE, before any stock is evaluated)
    try:
        market_ctx = get_today_market_context()
        market_env = market_ctx["breadth"]
        sector_cache = market_ctx["sectors"]  # {sector_name: rs_dict}
    except Exception:
        market_env = {"environment": "caution", "reasons": []}
        sector_cache = {}

    # Graduated breadth threshold: caution = mild raise, risk_off = significant raise
    if market_env.get("environment") == "risk_off":
        _breadth_threshold_override = 75.0
    elif market_env.get("environment") == "caution":
        _breadth_threshold_override = 68.0  # mild raise — caution != panic
    else:
        _breadth_threshold_override = None  # use reconciler adaptive threshold

    symbols = market_data.get_watchlist()
    total_symbols = len(symbols)
    
    if macro_articles:
        report(0, total_symbols, "scanning", f"[{cfg.label}] Macro sentiment scored {macro_sentiment_score:.0f}/100. Scanning {total_symbols} NSE stocks…")
    else:
        report(0, total_symbols, "scanning", f"[{cfg.label}] Scanning {total_symbols} NSE stocks…")

    # 1. Fetch DB cached stock profiles in one query to avoid slow sequential ticker.info calls
    db_profiles = {}
    if client:
        try:
            res = client.table("stocks").select("*").execute()
            for row in res.data:
                db_profiles[row["symbol"]] = row
        except Exception as exc:
            print(f"Error caching DB stock profiles: {exc}")

    # 2. Bulk download stock histories in a single query (1-2 seconds) instead of 90 sequential queries
    bulk_history = {}
    bulk_daily_history = {}
    try:
        tickers_str = " ".join(symbols)
        df = yf.download(tickers_str, period=cfg.history_period, interval=cfg.history_interval, group_by="ticker", progress=False, threads=True)
        for sym in symbols:
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if sym in df.columns.get_level_values(0):
                        sym_df = df[sym].copy()
                        sym_df = sym_df.dropna(how="all")
                        if not sym_df.empty:
                            bulk_history[sym] = sym_df
                else:
                    sym_df = df.copy()
                    sym_df = sym_df.dropna(how="all")
                    if not sym_df.empty:
                        bulk_history[sym] = sym_df
            except Exception:
                pass
    except Exception as exc:
        print(f"Error bulk downloading history: {exc}")

    # For intraday mode: bulk download 3-month daily history for HTF daily regime checks
    if mode == "intraday":
        try:
            tickers_str = " ".join(symbols)
            df_daily = yf.download(tickers_str, period="3mo", interval="1d", group_by="ticker", progress=False, threads=True)
            for sym in symbols:
                try:
                    if isinstance(df_daily.columns, pd.MultiIndex):
                        if sym in df_daily.columns.get_level_values(0):
                            sym_df = df_daily[sym].copy()
                            sym_df = sym_df.dropna(how="all")
                            if not sym_df.empty:
                                bulk_daily_history[sym] = sym_df
                    else:
                        sym_df = df_daily.copy()
                        sym_df = sym_df.dropna(how="all")
                        if not sym_df.empty:
                            bulk_daily_history[sym] = sym_df
                except Exception:
                    pass
        except Exception as exc:
            print(f"Error bulk downloading daily history for intraday HTF checks: {exc}")

    # At scan start — load learned config
    try:
        from app.services.loss_analyzer import load_learned_adjustments
        learned = load_learned_adjustments()
    except Exception:
        learned = {}

    scored: list[dict[str, Any]] = []
    sell_candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    completed = 0

    # 3. Analyze technical indicator configurations in parallel using the pre-fetched datasets
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(
                _analyze_symbol_dispatch, 
                symbol, 
                cfg, 
                db_profiles.get(symbol), 
                bulk_history.get(symbol),
                [], # Start with empty news to save 90 HTTP news calls
                macro_sentiment_score,
                sector_cache,
                learned,
                bulk_daily_history.get(symbol),
            ): symbol
            for symbol in symbols
            if bulk_history.get(symbol) is not None  # skip delisted/missing symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            completed += 1
            try:
                result = future.result(timeout=30)  # 30s per symbol max
                if result is None:
                    errors.append(f"{symbol}: analysis returned None")
                else:
                    scored.append(result)
                    trend = result["metrics"].get("trend_score") or 0
                    tech = result["metrics"].get("technical_score") or 0
                    if trend < 40 or tech < 35:
                        sell_candidates.append(result)
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
            report(
                completed,
                total_symbols,
                "scanning",
                f"[{cfg.label}] Scored {completed}/{total_symbols} stocks…",
            )

    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # 4. Fetch news only for top 15 candidate stocks in parallel to speed up news checks
    top_candidates = scored[:15]
    
    # 4.1. Fetch event risks in parallel for top 15 candidates to prevent Vercel serverless timeouts (saves 150+ yfinance HTTP calls!)
    from app.services.event_risk import get_event_risk
    event_risks = {}
    with ThreadPoolExecutor(max_workers=5) as event_pool:
        event_futures = {
            event_pool.submit(get_event_risk, item["symbol"]): item["symbol"]
            for item in top_candidates
        }
        for future in as_completed(event_futures):
            sym = event_futures[future]
            try:
                event_risks[sym] = future.result()
            except Exception:
                event_risks[sym] = {"risk_level": "clear", "events": [], "safe_to_trade": True}

    # Apply event risks and penalties/blocks to the top candidates
    for item in top_candidates:
        sym = item["symbol"]
        evt_risk = event_risks.get(sym, {"risk_level": "clear"})
        
        event_risk_penalty = 0
        event_risk_warning = ""
        
        if evt_risk["risk_level"] == "high_risk":
            item["composite_score"] = 0.0
            item["event_blocked"] = True
            item["reasoning"] = "Avoid: high upcoming event risk"
        elif evt_risk["risk_level"] == "earnings_near":
            if cfg.mode in ("swing", "longterm"):
                item["composite_score"] = 0.0
                item["event_blocked"] = True
                item["reasoning"] = "Avoid: earnings approaching in next 7 days"
            else:
                event_risk_penalty = 20
                event_risk_warning = " ⚠️ EARNINGS APPROACHING — intraday only, no overnight holding."
        elif evt_risk["risk_level"] == "exdiv_near":
            event_risk_penalty = 15
            event_risk_warning = " ⚠️ Ex-dividend date approaching — price may drop."
            
        if event_risk_penalty > 0:
            item["composite_score"] = max(0.0, item["composite_score"] - event_risk_penalty)
        if event_risk_warning:
            item["entry_note"] = (item.get("entry_note") or "") + event_risk_warning

    from app.services.system_settings import get_settings
    settings_data = get_settings()
    usage_mode = settings_data.get("usage_mode", "low")

    # Run lightweight (skipping heavy AI calls) if mode is intraday OR usage_mode is set to "low".
    # This keeps Vercel Fluid CPU usage low by default while letting the admin toggle "high" usage at any time.
    run_lightweight = (cfg.mode == "intraday" or usage_mode == "low")

    if run_lightweight:
        # Skip heavy news fetching & classification in intraday or Vercel serverless functions
        # to save Vercel Fluid Active CPU time and ensure quick execution.
        for item in top_candidates:
            item["news_score"] = 50.0
            item["news_rows"] = []
    else:
        candidate_news = {}
        with ThreadPoolExecutor(max_workers=5) as news_pool:
            news_futures = {
                news_pool.submit(market_data.fetch_news, item["symbol"], limit=3): item["symbol"]
                for item in top_candidates
            }
            for future in as_completed(news_futures):
                sym = news_futures[future]
                try:
                    candidate_news[sym] = future.result()
                except Exception:
                    candidate_news[sym] = []

        # Update candidate stocks with real news scores and adjust the composite score by the delta
        for item in top_candidates:
            sym = item["symbol"]
            articles = candidate_news.get(sym, [])
            real_news_score = _compute_news_score(articles)
            
            # Since first pass used news_score=50.0, adjust by the weighted difference
            news_delta = (real_news_score - 50.0) * cfg.weight_news
            
            item["news_score"] = round(real_news_score, 2)
            item["composite_score"] = round(max(0.0, min(100.0, item["composite_score"] + news_delta)), 2)
            item["news_rows"] = [
                {**article, "sentiment_label": "neutral", "sentiment_score": 0.5}
                for article in articles
            ]

    # Re-sort scored list and select top buys
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Compute sector median valuation levels (Relative Valuation Index)
    import statistics
    sector_pes = {}
    for item in scored:
        sec_name = item["profile"].get("sector")
        pe_val = item["profile"].get("pe_ratio")
        if sec_name and pe_val is not None and pe_val > 0:
            if sec_name not in sector_pes:
                sector_pes[sec_name] = []
            sector_pes[sec_name].append(pe_val)
    sector_medians = {}
    for sec_name, pes_list in sector_pes.items():
        if len(pes_list) >= 2:
            sector_medians[sec_name] = statistics.median(pes_list)

    # FIX #7 — Adaptive threshold from reconciler performance stats
    min_composite_score = 65.0  # default minimum
    try:
        from app.services.reconciler import get_performance_stats
        perf = get_performance_stats(client, cfg.mode) if client else {}
        min_composite_score = float(perf.get("adjusted_threshold", 65))
    except Exception:
        pass

    # Self-learning minimum score override
    min_score_override = learned.get("min_composite_score_override") if 'learned' in locals() else None
    if min_score_override is not None:
        min_composite_score = max(min_composite_score, float(min_score_override))

    # Macro sentiment minimum score override
    if min_composite_score_override is not None:
        min_composite_score = max(min_composite_score, min_composite_score_override)

    # ENHANCEMENT #4 — breadth caution override (75 on uncertain days)
    if _breadth_threshold_override is not None:
        min_composite_score = max(min_composite_score, _breadth_threshold_override)

    # Determine risk environment — graduated, not binary
    is_macro_risk_off = (macro_sentiment_score < 25)  # only extreme panic (<25), not mild negative news
    is_breadth_risk_off = (market_env.get("environment") == "risk_off")
    is_macro_cautious = (macro_sentiment_score < 40)  # mild caution flag for warnings
    reasons_list = []
    if is_macro_risk_off:
        reasons_list.append(f"Extreme bearish macro sentiment ({macro_sentiment_score:.0f}/100)")
    elif is_macro_cautious:
        reasons_list.append(f"Cautious macro sentiment ({macro_sentiment_score:.0f}/100)")
    if is_breadth_risk_off:
        breadth_reasons = ", ".join(market_env.get("reasons", ["unknown"]))
        reasons_list.append(f"Market breadth risk-off ({breadth_reasons})")

    # Group into priority tiers — only dump ALL to fallback when BOTH gates fire simultaneously
    if is_macro_risk_off and is_breadth_risk_off:
        # TRUE panic: both extreme macro AND breadth risk-off → suppress everything
        priority_1 = []
        priority_2 = []
        priority_3 = list(scored)
    else:
        # Normal or mildly cautious market — let stocks qualify on their own merit
        priority_1 = [s for s in scored if not s.get("is_blocked", False) and s.get("composite_score", 0) >= min_composite_score]
        priority_2 = [s for s in scored if not s.get("is_blocked", False) and s.get("composite_score", 0) < min_composite_score]
        priority_3 = [s for s in scored if s.get("is_blocked", False)]

    # Sort each priority tier
    priority_1.sort(key=lambda x: x["composite_score"], reverse=True)
    priority_2.sort(key=lambda x: x["composite_score"], reverse=True)
    priority_3.sort(key=lambda x: x.get("relaxed_composite_score", 0), reverse=True)

    # Try strict first
    strict_qualifying = list(priority_1)
    target_count = max(10, cfg.top_picks)
    normal_top_buys = _select_diversified_top_buys(strict_qualifying, count=target_count)

    fallback_active = False
    if len(normal_top_buys) < target_count:
        fallback_active = True
        candidate_pool = priority_1 + priority_2 + priority_3
        
        def pool_sorting_key(x):
            if not x.get("is_blocked", False) and x.get("composite_score", 0) >= min_composite_score and not (is_macro_risk_off or is_breadth_risk_off):
                return (0, -x.get("composite_score", 0))
            elif not x.get("is_blocked", False) and not (is_macro_risk_off or is_breadth_risk_off):
                return (1, -x.get("composite_score", 0))
            else:
                return (2, -x.get("relaxed_composite_score", 0))
        
        candidate_pool.sort(key=pool_sorting_key)
        
        strict_symbols = {s["symbol"] for s in strict_qualifying}
        for item in candidate_pool:
            if item["symbol"] not in strict_symbols:
                item["is_fallback"] = True
            else:
                item["is_fallback"] = False
                
        normal_top_buys = _select_diversified_top_buys(candidate_pool, count=target_count)

    # Sort the final list to preserve priority and score order
    def final_sorting_key(x):
        if not x.get("is_blocked", False) and x.get("composite_score", 0) >= min_composite_score and not (is_macro_risk_off or is_breadth_risk_off):
            return (0, -x.get("composite_score", 0))
        elif not x.get("is_blocked", False) and not (is_macro_risk_off or is_breadth_risk_off):
            return (1, -x.get("composite_score", 0))
        else:
            return (2, -x.get("relaxed_composite_score", 0))
            
    normal_top_buys.sort(key=final_sorting_key)
    
    # Adjust score of fallback/blocked items before submitting to parallel threads
    for item in normal_top_buys:
        if item.get("is_fallback", False) and item.get("is_blocked", False):
            item["composite_score"] = item.get("relaxed_composite_score", 0.0)
            
    top_buys = normal_top_buys

    recommendations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    report(total_symbols, total_symbols, "ai", f"[{cfg.label}] Generating AI insights…")

    # 5. Parallel generation of AI insights for top buys
    def _fetch_buy_insight(rank, item):
        if run_lightweight:
            # Quick local rule-based generation to save API roundtrip & CPU billing on Vercel
            display = item["profile"].get("display_symbol") or item["symbol"].replace(".NS", "")
            reasoning = f"{display} ({item['profile'].get('sector') or 'NSE'}) scores {item['composite_score']:.0f}/100. RSI is at {item['metrics'].get('rsi', 50):.1f} with active technical momentum."
            key_factors = [
                "Technical crossovers and volume momentum",
                f"Sector: {item['profile'].get('sector') or 'N/A'}",
                "Rule-based quant filter passed",
            ]
            if macro_sentiment_score < 45:
                reasoning += f" Warning: Bearish NIFTY news sentiment ({macro_sentiment_score:.0f}/100) suggests risk of gap-down opening."
                key_factors.append("Bearish macro environment warning")
                
            insight = {
                "reasoning": reasoning,
                "confidence": min(0.95, item["composite_score"] / 100),
                "key_factors": key_factors
            }
            return rank, item, insight

        try:
            insight = hf_ai.generate_recommendation_insight(
                item["symbol"],
                item["profile"],
                item["metrics"],
                item["news_score"],
                item["composite_score"],
                macro_sentiment=macro_sentiment_score,
                macro_headlines=macro_headlines,
                market_context=item.get("market_context"),
            )
        except Exception:
            display = item["profile"].get("display_symbol") or item["symbol"].replace(".NS", "")
            reasoning = f"{display} (NSE) scores {item['composite_score']:.0f}/100 with bullish technical crossovers."
            key_factors = ["Technical momentum"]
            if macro_sentiment_score < 45:
                reasoning += " Warning: Bearish global macro sentiment, expect overnight gap-down volatility."
                key_factors.append("Geopolitical and global market volatility warning")
                
            insight = {
                "reasoning": reasoning,
                "confidence": min(0.95, item["composite_score"] / 100),
                "key_factors": key_factors
            }
        return rank, item, insight

    # Parallel generation of sell rationales
    def _fetch_sell_rationale(item):
        if run_lightweight:
            display = item["symbol"].replace(".NS", "").replace(".BO", "")
            return item, f"Reduce position in {display} due to technical indicators dropping below signal thresholds."

        try:
            rationale = hf_ai.generate_sell_rationale(item["symbol"], item["metrics"])
        except Exception:
            display = item["symbol"].replace(".NS", "").replace(".BO", "")
            rationale = f"Reduce {display} due to weakening trend indicators."
        return item, rationale

    with ThreadPoolExecutor(max_workers=10) as ai_pool:
        buy_futures = [
            ai_pool.submit(_fetch_buy_insight, rank, item)
            for rank, item in enumerate(normal_top_buys, start=1)
        ]
        sell_futures = [
            ai_pool.submit(_fetch_sell_rationale, item)
            for item in sell_candidates[:5]
        ]
        
        # Process buy results
        for future in as_completed(buy_futures):
            rank, item, insight = future.result()
            target_price = _target_for_mode(item["metrics"].get("price"), cfg.mode, item.get("atr_levels"))
            stop_loss = _stop_for_mode(item["metrics"].get("price"), cfg.mode, item.get("atr_levels"))

            # BUG-05: Minimum R:R check as a final gate (skip only if not a fallback recommendation)
            entry_price = item.get("ideal_entry_price") or item["metrics"].get("price")
            is_fallback = item.get("is_fallback", False)
            if entry_price and stop_loss and target_price and stop_loss < entry_price:
                rr = (target_price - entry_price) / (entry_price - stop_loss)
                if rr < 2.0 and not is_fallback:
                    continue  # skip this recommendation if strict and poor R:R

            # Quantitative relative valuation scoring vs sector medians
            item_sector = item["profile"].get("sector")
            item_pe = item["profile"].get("pe_ratio")
            is_undervalued = False
            if item_sector and item_pe is not None and item_pe > 0 and item_sector in sector_medians:
                if item_pe < sector_medians[item_sector] * 0.8:
                    is_undervalued = True

            # Calculate visual trade tier and size
            confirming_signals = item.get("confirming_signals_list", [])
            tier_info = classify_trade_tier(item["composite_score"], confirming_signals)

            reasoning = insight.get("reasoning", "") if isinstance(insight, dict) else str(insight)
            if is_fallback:
                reasons_warnings = []
                if is_macro_risk_off or is_breadth_risk_off:
                    reasons_warnings.append("MARKET RISK-OFF")
                elif is_macro_cautious:
                    reasons_warnings.append("MARKET CAUTIOUS")
                if item.get("is_blocked", False):
                    reasons_warnings.append(f"Blocked: {', '.join(item.get('block_reasons', []))}")
                elif item.get("composite_score", 0.0) < min_composite_score:
                    reasons_warnings.append(f"Score {item.get('composite_score', 0.0):.1f} below threshold {min_composite_score:.1f}")
                
                warning_prefix = f"⚠️ [FALLBACK MODE: {', '.join(reasons_warnings)}] "
                reasoning = warning_prefix + reasoning

            if item.get("overbought_warning"):
                if "Overbought — reduced confidence" not in reasoning:
                    reasoning = reasoning.rstrip(".") + ". Overbought — reduced confidence."

            sentiment_gate_status = "passed" if macro_sentiment_score >= 40 else "overridden"

            rec = {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "symbol": item["symbol"],
                "cap_segment": item["profile"].get("cap_segment"),
                "rank": rank,
                "action": "buy",
                "trade_mode": cfg.mode,
                "composite_score": item["composite_score"],
                "trend_score": item["metrics"].get("trend_score"),
                "news_score": item["news_score"],
                "technical_score": item["metrics"].get("technical_score"),
                "fundamental_score": item["metrics"].get("fundamental_score"),
                "ai_confidence": insight.get("confidence", 0.7) if isinstance(insight, dict) else 0.7,
                "reasoning": reasoning,
                "key_factors": insight.get("key_factors", []) if isinstance(insight, dict) else [],
                "signal_date": signal_date.isoformat(),
                "trade_date": trade_date.isoformat(),
                "target_price": target_price,
                "stop_loss": stop_loss,
                "performance_status": "pending",
                "vwap": item["metrics"].get("vwap"),
                "bullish_crossover": item["metrics"].get("bullish_crossover"),
                "golden_cross": item["metrics"].get("golden_cross"),
                "range_52w_pct": item["metrics"].get("range_52w_pct"),
                "pe_ratio": item["metrics"].get("pe_ratio"),
                "dividend_yield": item["metrics"].get("dividend_yield"),
                "is_undervalued": is_undervalued,
                "overnight_gap_down_warning": macro_sentiment_score < 30 or overnight_gap_down_flag,
                # Prompt 3 entries
                "entry_type": item.get("entry_type", "immediate"),
                "ideal_entry_price": item.get("ideal_entry_price"),
                "entry_note": item.get("entry_note"),
                "trade_tier": tier_info["tier"],
                "position_size_pct": tier_info["position_size_pct"],
                "confirming_signals": tier_info["confirming_signals"],
                "stocks": {
                    "name": item["profile"].get("name"),
                    "sector": item["profile"].get("sector"),
                    "pe_ratio": item["profile"].get("pe_ratio"),
                    "market_cap": item["profile"].get("market_cap"),
                    "is_undervalued": is_undervalued,
                },
                "sentiment_gate": sentiment_gate_status,
            }
            recommendations.append(rec)
            signals.append(
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "symbol": item["symbol"],
                    "signal_type": "buy",
                    "trade_mode": cfg.mode,
                    "strength": _strength(item["composite_score"]),
                    "price_at_signal": item["metrics"].get("price"),
                    "target_price": target_price,
                    "stop_loss": stop_loss,
                    "rationale": reasoning[:500],
                    "signal_date": signal_date.isoformat(),
                    "planned_trade_date": trade_date.isoformat(),
                    "sentiment_gate": sentiment_gate_status,
                }
            )
            
        # Process sell results
        for future in as_completed(sell_futures):
            item, rationale = future.result()
            signals.append(
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "symbol": item["symbol"],
                    "signal_type": "sell",
                    "trade_mode": cfg.mode,
                    "strength": "moderate",
                    "price_at_signal": item["metrics"].get("price"),
                    "target_price": None,
                    "stop_loss": None,
                    "rationale": rationale,
                    "signal_date": signal_date.isoformat(),
                    "planned_trade_date": trade_date.isoformat(),
                }
            )

    # Sort recommendations by rank to preserve deterministic order
    recommendations.sort(key=lambda x: x["rank"])

    if client:
        report(total_symbols, total_symbols, "saving", "Saving to Supabase…")
        
        # Bulk upsert stocks
        profiles = [item["profile"] for item in scored]
        try:
            supabase_store.upsert_stocks(client, profiles)
        except Exception as e:
            print(f"Failed to bulk upsert stocks: {e}. Falling back to sequential.")
            for profile in profiles:
                try:
                    supabase_store.upsert_stock(client, profile)
                except Exception:
                    pass

        # Bulk insert metrics
        metrics_rows = [
            {
                "symbol": item["symbol"],
                **{k: item["metrics"].get(k) for k in (
                    "price", "change_pct", "volume", "rsi", "macd", "macd_signal",
                    "sma_20", "sma_50", "trend_score", "volatility",
                )},
            }
            for item in scored
        ]
        try:
            supabase_store.insert_metrics_batch(client, metrics_rows)
        except Exception as e:
            print(f"Failed to bulk insert metrics: {e}. Falling back to sequential.")
            for row in metrics_rows:
                try:
                    supabase_store.insert_metrics(client, row)
                except Exception:
                    pass

        # Bulk insert news
        all_news_rows = []
        for item in top_buys:
            if item.get("news_rows"):
                all_news_rows.extend(item["news_rows"])
        if all_news_rows:
            try:
                supabase_store.insert_news(client, all_news_rows)
            except Exception as e:
                print(f"Failed to bulk insert news: {e}. Falling back to sequential.")
                for item in top_buys:
                    if item.get("news_rows"):
                        try:
                            supabase_store.insert_news(client, item["news_rows"])
                        except Exception:
                            pass

        # Deduplicate signals by (symbol, signal_date, signal_type)
        seen_signals = set()
        deduped_signals = []
        for sig in signals:
            key = (sig.get("symbol"), sig.get("signal_date"), sig.get("signal_type"))
            if key not in seen_signals:
                seen_signals.add(key)
                deduped_signals.append(sig)
        signals = deduped_signals

        supabase_store.insert_recommendations(client, recommendations)
        supabase_store.insert_signals(client, signals)
        if run_id:
            supabase_store.complete_run(client, run_id, len(scored), len(recommendations))

    result = {
        "trade_mode": cfg.mode,
        "signal_date": signal_date.isoformat(),
        "trade_date": trade_date.isoformat(),
        "stocks_analyzed": len(scored),
        "top_recommendations": recommendations,
        "signals": signals,
        "errors": errors,
        "supabase_persisted": client is not None,
    }
    _last_result = result

    # Broadcast to Telegram if configured
    try:
        from app.services.notifier import send_telegram_recommendations, send_telegram_entry_alert
        send_telegram_recommendations(recommendations, cfg.label)
        
        # Dispatch specific high-probability buy entry alerts
        for rec in recommendations:
            score = rec.get("composite_score", 0)
            is_undervalued = rec.get("is_undervalued", False)
            confidence = rec.get("ai_confidence", 0.5)
            
            match = next((item for item in scored if item["symbol"] == rec["symbol"]), None)
            price = match["metrics"].get("price") if match else (rec.get("target_price", 100) / 1.05)
            
            if score >= 70 or is_undervalued or confidence >= 0.75:
                send_telegram_entry_alert(rec, price)
    except Exception:
        pass

    report(total_symbols, total_symbols, "done", "Complete")
    return result


# ---------------------------------------------------------------------------
# Dispatch — route to the right analyzer per mode
# ---------------------------------------------------------------------------


def _analyze_symbol_dispatch(
    symbol: str,
    cfg: ScanConfig,
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
    sector_cache: dict[str, Any] | None = None,
    learned: dict[str, Any] | None = None,
    daily_history_df: Any = None,
) -> dict[str, Any]:
    """Route to the mode-appropriate symbol analyzer."""
    if cfg.mode == "future":
        raise NotImplementedError("Future mode not yet implemented")
    elif cfg.mode == "intraday":
        return _analyze_symbol_intraday(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score, sector_cache, learned, daily_history_df)
    elif cfg.mode == "longterm":
        return _analyze_symbol_longterm(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score, sector_cache, learned)
    else:
        # swing use the same analysis
        return _analyze_symbol_swing(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score, sector_cache, learned)


def _analyze_symbol_swing(
    symbol: str,
    cfg: ScanConfig,
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
    sector_cache: dict[str, Any] | None = None,
    learned: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Daily analysis — swing + future modes with regime gate, ATR SL/TP, and intelligence layer."""
    profile = db_profile if db_profile is not None else {
        "symbol": symbol,
        "name": symbol.replace(".NS", ""),
        "sector": "Unclassified",
        "market_cap": 0.0,
        "pe_ratio": 0.0,
        "dividend_yield": 0.0,
    }
    history = history_df
    if history is None or history.empty:
        return {
            "symbol": symbol, "profile": profile, "metrics": {},
            "news_score": 50.0, "composite_score": 0.0, "news_rows": [],
            "relaxed_composite_score": 0.0, "is_blocked": True, "block_reasons": ["No historical data"]
        }
    metrics = technicals.compute_indicators(history)
    articles = news_articles if news_articles is not None else []
    news_score = _compute_news_score(articles)

    # 1. Market regime
    regime = technicals.get_market_regime(history)
    regime_blocked = not regime["tradeable"]

    # 2. Smart money
    smart_money = technicals.get_smart_money_signals(history)
    distribution_blocked = (smart_money["signal"] == "distribution" and smart_money["bearish_divergence"])

    # 3. Candlestick patterns
    candle_signals = technicals.get_candlestick_patterns(history)
    bearish_candles = [p for p in candle_signals["patterns"] if "bearish" in p["type"]]
    bearish_candle_blocked = any(p["strength"] == "high" for p in bearish_candles)

    # 4. Volume confirmation
    vol_conf = technicals.get_volume_confirmation(history)

    # 5. Stock Personality
    personality = technicals.get_stock_personality(profile, history)
    personality_blocked = (personality["personality"] == "avoid_today")
    rules = personality["rules"]
    atr_sl_multiplier = rules.get("atr_sl_multiplier", 2.0)
    min_volume_ratio = rules.get("min_volume_ratio", 1.5)

    # 6. Self-Learning
    raw_sector = profile.get("sector")
    from app.services.sector_rs import _normalize_sector
    normalized_sector = _normalize_sector(raw_sector)
    sector_learning_penalty = 0
    mode_suppressed = False
    if learned:
        suppressed_sectors = learned.get("suppressed_sectors", [])
        suppressed_modes = learned.get("suppressed_trade_modes", [])
        if cfg.mode in suppressed_modes:
            mode_suppressed = True
        if raw_sector in suppressed_sectors or normalized_sector in suppressed_sectors:
            sector_learning_penalty = 25

    # 7. ATR SL/TP
    price = metrics.get("price")
    atr_levels = technicals.get_atr_levels(history, price, sl_multiplier=atr_sl_multiplier) if price else None

    # 8. Entry Precision
    entry_zone = technicals.get_optimal_entry_zone(history, regime, atr_levels["atr"] if atr_levels else 0.0)
    entry_blocked = (entry_zone["entry_type"] == "avoid")
    entry_timing_penalty = 0
    if entry_zone["entry_type"] == "wait_dip":
        entry_timing_penalty = 10
        if atr_levels:
            atr_levels = technicals.get_atr_levels(
                history,
                entry_zone["ideal_entry"],
                sl_multiplier=atr_sl_multiplier
            )

    # 9. Support/Resistance
    key_levels = technicals.get_key_levels(history)

    # 10. RSI & Overbought
    rsi = metrics.get("rsi")
    rsi_val = rsi or 50.0
    rsi_overbought_blocked = (rsi is not None and rsi > 75)
    overbought_warning = (70 <= rsi_val <= 75)

    # 11. News Sentiment
    sentiment_dict: dict[str, Any] = {"label": "neutral", "score": 0.0}
    if settings.hf_token and articles:
        try:
            headlines = " ".join(
                f"{a.get('title', '')} {a.get('summary', '')[:200]}" for a in articles[:3]
            ).strip()
            if headlines:
                label, score = hf_ai.analyze_news_sentiment(headlines)
                sentiment_dict = {"label": label, "score": score}
        except Exception:
            pass
    sentiment_blocked = (sentiment_dict["label"] == "negative" and sentiment_dict["score"] > 0.75)

    # Compute base composite score
    base_composite = _compute_composite_score(
        regime=regime,
        rsi=rsi_val,
        macd_cross=bool(metrics.get("macd") is not None and metrics.get("macd_signal") is not None and metrics.get("macd") > metrics.get("macd_signal")),
        volume_conf=vol_conf,
        sentiment=sentiment_dict,
        price_vs_sma={
            "above_sma20": bool(price and metrics.get("sma_20") and price > metrics.get("sma_20")),
            "above_sma50": bool(price and metrics.get("sma_50") and price > metrics.get("sma_50")),
            "above_sma200": bool(price and metrics.get("sma_200") and price > metrics.get("sma_200")),
        },
        atr_levels=atr_levels,
    )

    if overbought_warning:
        base_composite = max(0.0, base_composite - 20)
    if vol_conf.get("volume_ratio", 1.0) < min_volume_ratio:
        base_composite = max(0.0, base_composite - 15)
    if smart_money["signal"] == "distribution":
        base_composite = max(0.0, base_composite - 25)
    elif smart_money["signal"] == "accumulation":
        base_composite = min(100.0, base_composite + 15)
    base_composite = round(min(100.0, max(0.0, base_composite + candle_signals["score_delta"])), 2)

    # Sector RS
    sector_rs: dict[str, Any] = {"status": "neutral", "rs_score": 1.0}
    if normalized_sector:
        if sector_cache and normalized_sector in sector_cache:
            sector_rs = sector_cache[normalized_sector]
        else:
            try:
                sector_rs = get_sector_relative_strength(normalized_sector)
            except Exception:
                pass
    if sector_rs["status"] == "lagging":
        base_composite = max(0.0, base_composite - 20)
    elif sector_rs["status"] == "leading":
        base_composite = min(100.0, base_composite + 10)

    # Lagging sector block
    lagging_sector_blocked = (sector_rs["status"] == "lagging" and base_composite < 80)

    if key_levels["target_blocked"]:
        base_composite = max(0.0, base_composite - 15)
    if atr_levels and key_levels["nearest_support"]:
        if atr_levels["stop_loss"] > key_levels["nearest_support"]:
            atr_levels = {**atr_levels,
                          "stop_loss": round(key_levels["nearest_support"] * 0.995, 2)}

    if sentiment_dict["label"] == "negative" and sentiment_dict["score"] > 0.55:
        base_composite = max(0.0, base_composite - 25)

    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        base_composite = round(max(0.0, base_composite + macro_modifier), 2)

    base_composite = max(0.0, base_composite - sector_learning_penalty - entry_timing_penalty)
    base_composite = round(base_composite, 2)

    # R:R block check
    rr = atr_levels["risk_reward"] if atr_levels else 0.0
    rr_blocked = (rr < 1.5)  # lowered from 2.0 — was too aggressive

    # Compile blocks
    warnings = []
    relaxed_penalties = 0.0

    if regime_blocked:
        relaxed_penalties += 25
        warnings.append("Downtrend regime")
    if distribution_blocked:
        relaxed_penalties += 20
        warnings.append("Institutional distribution")
    if bearish_candle_blocked:
        relaxed_penalties += 15
        warnings.append("Bearish candlestick pattern")
    if personality_blocked:
        relaxed_penalties += 15
        warnings.append("Avoid personality rule")
    if entry_blocked:
        relaxed_penalties += 15
        warnings.append("Unfavorable entry zone")
    if rsi_overbought_blocked:
        relaxed_penalties += 20
        warnings.append("RSI overbought (>75)")
    if sentiment_blocked:
        relaxed_penalties += 20
        warnings.append("Negative news sentiment")
    if lagging_sector_blocked:
        relaxed_penalties += 20
        warnings.append("Lagging sector")
    if rr_blocked:
        relaxed_penalties += 15
        warnings.append("Low R:R ratio (<2.0)")
    if mode_suppressed:
        relaxed_penalties += 30
        warnings.append("Trade mode suppressed")

    is_blocked = (
        regime_blocked or 
        distribution_blocked or 
        bearish_candle_blocked or 
        personality_blocked or 
        entry_blocked or 
        rsi_overbought_blocked or 
        sentiment_blocked or 
        lagging_sector_blocked or 
        rr_blocked or
        mode_suppressed
    )

    strict_composite = 0.0 if is_blocked else base_composite
    relaxed_composite = round(max(0.0, base_composite - relaxed_penalties), 2)

    news_rows = [
        {**article, "sentiment_label": sentiment_dict["label"], "sentiment_score": sentiment_dict["score"]}
        for article in articles
    ]

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": {
            **metrics,
            "regime": regime["regime"],
            "adx": regime["adx"],
            "volume_ratio": vol_conf["volume_ratio"],
            "atr": atr_levels["atr"] if atr_levels else None,
            "risk_reward": atr_levels["risk_reward"] if atr_levels else None,
            "atr_stop_loss": atr_levels["stop_loss"] if atr_levels else None,
            "atr_target_price": atr_levels["target_price"] if atr_levels else None,
            "smart_money_signal": smart_money["signal"],
            "smart_money_cmf": smart_money["cmf"],
            "primary_candle_pattern": candle_signals["primary_pattern"],
            "sector_rs_status": sector_rs["status"],
            "sector_rs_score": sector_rs["rs_score"],
            "nearest_support": key_levels["nearest_support"],
            "nearest_resistance": key_levels["nearest_resistance"],
            "target_blocked": key_levels["target_blocked"],
        },
        "news_score": round(news_score, 2),
        "composite_score": strict_composite,
        "relaxed_composite_score": relaxed_composite,
        "is_blocked": is_blocked,
        "block_reasons": warnings,
        "news_rows": news_rows,
        "atr_levels": atr_levels,
        "overbought_warning": overbought_warning,
        "market_context": {
            "sector_rs_status": sector_rs["status"],
            "market_environment": "caution" if macro_sentiment_score < 45 else "risk_on",
            "nifty_vs_sma20": None,
            "smart_money": smart_money["reason"],
            "primary_candle": candle_signals["primary_pattern"],
        },
        "entry_type": entry_zone["entry_type"],
        "ideal_entry_price": entry_zone["ideal_entry"],
        "entry_note": entry_zone["entry_note"],
        "personality": personality["personality"],
        "confirming_signals_list": [
            sig for sig, cond in [
                ("regime_uptrend", regime["regime"] == "uptrend"),
                ("volume_confirmed", vol_conf.get("confirmed", False) or vol_conf.get("strong", False)),
                ("smart_money_accumulation", smart_money["signal"] == "accumulation"),
                ("sector_leading", sector_rs["status"] == "leading"),
                ("bullish_candlestick", candle_signals["score_delta"] > 0),
                ("above_vwap", metrics.get("vwap") is not None and price is not None and price > metrics.get("vwap")),
            ] if cond
        ]
    }


def _analyze_symbol_intraday(
    symbol: str,
    cfg: ScanConfig,
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
    sector_cache: dict[str, Any] | None = None,
    learned: dict[str, Any] | None = None,
    daily_history_df: Any = None,
) -> dict[str, Any]:
    """60-min candle analysis for intraday with daily HTF regime gate and ATR SL/TP."""
    profile = db_profile if db_profile is not None else {
        "symbol": symbol,
        "name": symbol.replace(".NS", ""),
        "sector": "Unclassified",
        "market_cap": 0.0,
        "pe_ratio": 0.0,
        "dividend_yield": 0.0,
    }
    history = history_df
    if history is None or history.empty:
        return {
            "symbol": symbol, "profile": profile, "metrics": {},
            "news_score": 50.0, "composite_score": 0.0, "news_rows": [],
            "relaxed_composite_score": 0.0, "is_blocked": True, "block_reasons": ["No historical data"]
        }

    metrics = technicals.compute_intraday_indicators(history)
    articles = news_articles if news_articles is not None else []
    news_score = _compute_news_score(articles)

    # 1. Higher timeframe (daily) regime check
    try:
        if daily_history_df is not None and not daily_history_df.empty:
            daily_regime = technicals.get_market_regime(daily_history_df)
        else:
            daily_regime = {"regime": "sideways", "adx": 0.0, "tradeable": True}
        daily_regime_blocked = (daily_regime["regime"] == "downtrend")
    except Exception:
        daily_regime = {"regime": "sideways", "adx": 0.0, "tradeable": True}
        daily_regime_blocked = False

    # 2. Intraday regime
    intraday_regime = technicals.get_market_regime(history)
    regime_blocked = not intraday_regime["tradeable"]

    # 3. Smart money
    smart_money = technicals.get_smart_money_signals(history)
    distribution_blocked = (smart_money["signal"] == "distribution" and smart_money["bearish_divergence"])

    # 4. Candlestick patterns
    candle_signals = technicals.get_candlestick_patterns(history)
    bearish_candles = [p for p in candle_signals["patterns"] if "bearish" in p["type"]]
    bearish_candle_blocked = any(p["strength"] == "high" for p in bearish_candles)

    # 5. VWAP
    price = metrics.get("price")
    vwap = metrics.get("vwap")
    vwap_blocked = bool(price and vwap and price < vwap)

    # 6. RSI
    rsi = metrics.get("rsi") or 0.0
    rsi_blocked = (rsi < 45)
    rsi_overbought_blocked = (rsi > 78)
    overbought_warning = (70 <= rsi <= 75)

    # 7. Volume confirmation
    vol_conf = technicals.get_volume_confirmation(history)

    # 8. Stock Personality
    personality = technicals.get_stock_personality(profile, history)
    personality_blocked = (personality["personality"] == "avoid_today")
    rules = personality["rules"]
    min_volume_ratio = rules.get("min_volume_ratio", 1.5)

    # 9. Self-Learning
    raw_sector = profile.get("sector")
    from app.services.sector_rs import _normalize_sector
    normalized_sector = _normalize_sector(raw_sector)
    sector_learning_penalty = 0
    mode_suppressed = False
    if learned:
        suppressed_sectors = learned.get("suppressed_sectors", [])
        suppressed_modes = learned.get("suppressed_trade_modes", [])
        if cfg.mode in suppressed_modes:
            mode_suppressed = True
        if raw_sector in suppressed_sectors or normalized_sector in suppressed_sectors:
            sector_learning_penalty = 25

    # 10. ATR SL/TP
    atr_levels = technicals.get_atr_levels(history, price, sl_multiplier=1.5, rr_ratio=2.0) if price else None

    # 11. Entry Precision
    entry_zone = technicals.get_optimal_entry_zone(history, intraday_regime, atr_levels["atr"] if atr_levels else 0.0)
    entry_blocked = (entry_zone["entry_type"] == "avoid")
    entry_timing_penalty = 0
    if entry_zone["entry_type"] == "wait_dip":
        entry_timing_penalty = 10
        if atr_levels:
            atr_levels = technicals.get_atr_levels(
                history,
                entry_zone["ideal_entry"],
                sl_multiplier=1.5,
                rr_ratio=2.0
            )

    # 12. Support/Resistance
    key_levels = technicals.get_key_levels(history)

    # Compute base composite score
    base_composite = _compute_composite_score(
        regime=intraday_regime,
        rsi=rsi,
        macd_cross=bool(metrics.get("macd") is not None and metrics.get("macd_signal") is not None and metrics.get("macd") > metrics.get("macd_signal")),
        volume_conf=vol_conf,
        sentiment={"label": "neutral", "score": 0.0},
        price_vs_sma={
            "above_sma20": bool(price and metrics.get("sma_9") and price > metrics.get("sma_9")),
            "above_sma50": bool(price and metrics.get("sma_21") and price > metrics.get("sma_21")),
            "above_sma200": False,
        },
        atr_levels=atr_levels,
    )

    if overbought_warning:
        base_composite = max(0.0, base_composite - 20)
    if vol_conf.get("volume_ratio", 1.0) < min_volume_ratio:
        base_composite = max(0.0, base_composite - 15)
    if smart_money["signal"] == "distribution":
        base_composite = max(0.0, base_composite - 25)
    elif smart_money["signal"] == "accumulation":
        base_composite = min(100.0, base_composite + 15)
    base_composite = round(min(100.0, max(0.0, base_composite + candle_signals["score_delta"])), 2)

    # Sector RS
    sector_rs: dict[str, Any] = {"status": "neutral", "rs_score": 1.0}
    if normalized_sector:
        if sector_cache and normalized_sector in sector_cache:
            sector_rs = sector_cache[normalized_sector]
        else:
            try:
                sector_rs = get_sector_relative_strength(normalized_sector)
            except Exception:
                pass
    if sector_rs["status"] == "lagging":
        base_composite = max(0.0, base_composite - 20)
    elif sector_rs["status"] == "leading":
        base_composite = min(100.0, base_composite + 10)

    # Lagging sector block
    lagging_sector_blocked = (sector_rs["status"] == "lagging" and base_composite < 80)

    if key_levels["target_blocked"]:
        base_composite = max(0.0, base_composite - 15)
    if atr_levels and key_levels["nearest_support"]:
        if atr_levels["stop_loss"] > key_levels["nearest_support"]:
            atr_levels = {**atr_levels,
                          "stop_loss": round(key_levels["nearest_support"] * 0.995, 2)}

    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        base_composite = round(max(0.0, base_composite + macro_modifier), 2)

    base_composite = max(0.0, base_composite - sector_learning_penalty - entry_timing_penalty)
    base_composite = round(base_composite, 2)

    # R:R block check
    rr = atr_levels["risk_reward"] if atr_levels else 0.0
    rr_blocked = (rr < 1.5)  # lowered from 2.0 — was too aggressive

    # Compile blocks
    warnings = []
    relaxed_penalties = 0.0

    if daily_regime_blocked:
        relaxed_penalties += 25
        warnings.append("Daily timeframe downtrend")
    if regime_blocked:
        relaxed_penalties += 25
        warnings.append("Intraday downtrend")
    if distribution_blocked:
        relaxed_penalties += 20
        warnings.append("Institutional distribution")
    if bearish_candle_blocked:
        relaxed_penalties += 15
        warnings.append("Bearish candlestick pattern")
    if vwap_blocked:
        relaxed_penalties += 15
        warnings.append("Price below VWAP")
    if rsi_blocked:
        relaxed_penalties += 15
        warnings.append("RSI weak (<45)")
    if rsi_overbought_blocked:
        relaxed_penalties += 20
        warnings.append("RSI overbought (>78)")
    if personality_blocked:
        relaxed_penalties += 15
        warnings.append("Avoid personality rule")
    if entry_blocked:
        relaxed_penalties += 15
        warnings.append("Unfavorable entry zone")
    if lagging_sector_blocked:
        relaxed_penalties += 20
        warnings.append("Lagging sector")
    if rr_blocked:
        relaxed_penalties += 15
        warnings.append("Low R:R ratio (<2.0)")
    if mode_suppressed:
        relaxed_penalties += 30
        warnings.append("Trade mode suppressed")

    is_blocked = (
        daily_regime_blocked or 
        regime_blocked or 
        distribution_blocked or 
        bearish_candle_blocked or 
        vwap_blocked or 
        rsi_blocked or 
        rsi_overbought_blocked or 
        personality_blocked or 
        entry_blocked or 
        lagging_sector_blocked or 
        rr_blocked or
        mode_suppressed
    )

    strict_composite = 0.0 if is_blocked else base_composite
    relaxed_composite = round(max(0.0, base_composite - relaxed_penalties), 2)

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": {
            **metrics,
            "regime": intraday_regime["regime"],
            "daily_regime": daily_regime["regime"],
            "volume_ratio": vol_conf["volume_ratio"],
            "atr": atr_levels["atr"] if atr_levels else None,
            "risk_reward": atr_levels["risk_reward"] if atr_levels else None,
            "atr_stop_loss": atr_levels["stop_loss"] if atr_levels else None,
            "atr_target_price": atr_levels["target_price"] if atr_levels else None,
            "smart_money_signal": smart_money["signal"],
            "smart_money_cmf": smart_money["cmf"],
            "primary_candle_pattern": candle_signals["primary_pattern"],
            "sector_rs_status": sector_rs["status"],
            "sector_rs_score": sector_rs["rs_score"],
            "nearest_support": key_levels["nearest_support"],
            "nearest_resistance": key_levels["nearest_resistance"],
            "target_blocked": key_levels["target_blocked"],
        },
        "news_score": round(news_score, 2),
        "composite_score": strict_composite,
        "relaxed_composite_score": relaxed_composite,
        "is_blocked": is_blocked,
        "block_reasons": warnings,
        "news_rows": [],
        "atr_levels": atr_levels,
        "overbought_warning": overbought_warning,
        "market_context": {
            "sector_rs_status": sector_rs["status"],
            "market_environment": "caution" if macro_sentiment_score < 45 else "risk_on",
            "nifty_vs_sma20": None,
            "smart_money": smart_money["reason"],
            "primary_candle": candle_signals["primary_pattern"],
        },
        "entry_type": entry_zone["entry_type"],
        "ideal_entry_price": entry_zone["ideal_entry"],
        "entry_note": entry_zone["entry_note"],
        "personality": personality["personality"],
        "confirming_signals_list": [
            sig for sig, cond in [
                ("regime_uptrend", intraday_regime["regime"] == "uptrend"),
                ("volume_confirmed", vol_conf.get("confirmed", False) or vol_conf.get("strong", False)),
                ("smart_money_accumulation", smart_money["signal"] == "accumulation"),
                ("sector_leading", sector_rs["status"] == "leading"),
                ("bullish_candlestick", candle_signals["score_delta"] > 0),
                ("above_vwap", price is not None and vwap is not None and price > vwap),
            ] if cond
        ]
    }


def _analyze_symbol_longterm(
    symbol: str,
    cfg: ScanConfig,
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
    sector_cache: dict[str, Any] | None = None,
    learned: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """1-year daily analysis with fundamental scoring for long-term holds."""
    profile = db_profile if db_profile is not None else market_data.fetch_stock_profile(symbol)
    history = (
        history_df
        if history_df is not None and not history_df.empty
        else market_data.fetch_longterm_history(symbol, period=cfg.history_period)
    )
    metrics = technicals.compute_longterm_indicators(history, profile=profile)
    articles = news_articles if news_articles is not None else []
    news_score = _compute_news_score(articles)

    # 1. Market regime
    regime = technicals.get_market_regime(history)
    regime_blocked = not regime["tradeable"]

    # 2. Smart money
    smart_money = technicals.get_smart_money_signals(history)
    distribution_blocked = (smart_money["signal"] == "distribution" and smart_money["bearish_divergence"])

    # 3. Candlestick patterns
    candle_signals = technicals.get_candlestick_patterns(history)
    bearish_candles = [p for p in candle_signals["patterns"] if "bearish" in p["type"]]
    bearish_candle_blocked = any(p["strength"] == "high" for p in bearish_candles)

    # 4. Volume confirmation
    vol_conf = technicals.get_volume_confirmation(history)

    # 5. Stock Personality
    personality = technicals.get_stock_personality(profile, history)
    personality_blocked = (personality["personality"] == "avoid_today")
    rules = personality["rules"]
    atr_sl_multiplier = rules.get("atr_sl_multiplier", 2.0)
    min_volume_ratio = rules.get("min_volume_ratio", 1.5)

    # 6. Self-Learning
    raw_sector = profile.get("sector")
    from app.services.sector_rs import _normalize_sector
    normalized_sector = _normalize_sector(raw_sector)
    sector_learning_penalty = 0
    mode_suppressed = False
    if learned:
        suppressed_sectors = learned.get("suppressed_sectors", [])
        suppressed_modes = learned.get("suppressed_trade_modes", [])
        if cfg.mode in suppressed_modes:
            mode_suppressed = True
        if raw_sector in suppressed_sectors or normalized_sector in suppressed_sectors:
            sector_learning_penalty = 25

    # 7. ATR SL/TP
    price = metrics.get("price")
    atr_levels = technicals.get_atr_levels(history, price, sl_multiplier=atr_sl_multiplier) if price else None

    # 8. Entry Precision
    entry_zone = technicals.get_optimal_entry_zone(history, regime, atr_levels["atr"] if atr_levels else 0.0)
    entry_blocked = (entry_zone["entry_type"] == "avoid")
    entry_timing_penalty = 0
    if entry_zone["entry_type"] == "wait_dip":
        entry_timing_penalty = 10
        if atr_levels:
            atr_levels = technicals.get_atr_levels(
                history,
                entry_zone["ideal_entry"],
                sl_multiplier=atr_sl_multiplier
            )

    # 9. Support/Resistance
    key_levels = technicals.get_key_levels(history)

    # 10. RSI & Overbought
    rsi = metrics.get("rsi")
    rsi_val = rsi or 50.0
    rsi_overbought_blocked = (rsi is not None and rsi > 75)
    overbought_warning = (70 <= rsi_val <= 75)

    # 11. News Sentiment
    sentiment_dict: dict[str, Any] = {"label": "neutral", "score": 0.0}
    if settings.hf_token and articles:
        try:
            headlines = " ".join(
                f"{a.get('title', '')} {a.get('summary', '')[:200]}" for a in articles[:3]
            ).strip()
            if headlines:
                label, score = hf_ai.analyze_news_sentiment(headlines)
                sentiment_dict = {"label": label, "score": score}
        except Exception:
            pass
    sentiment_blocked = (sentiment_dict["label"] == "negative" and sentiment_dict["score"] > 0.75)

    # Compute base composite score
    base_composite = _compute_composite_score(
        regime=regime,
        rsi=rsi_val,
        macd_cross=bool(metrics.get("macd") is not None and metrics.get("macd_signal") is not None and metrics.get("macd") > metrics.get("macd_signal")),
        volume_conf=vol_conf,
        sentiment=sentiment_dict,
        price_vs_sma={
            "above_sma20": bool(price and metrics.get("sma_20") and price > metrics.get("sma_20")),
            "above_sma50": bool(price and metrics.get("sma_50") and price > metrics.get("sma_50")),
            "above_sma200": bool(price and metrics.get("sma_200") and price > metrics.get("sma_200")),
        },
        atr_levels=atr_levels,
    )

    if overbought_warning:
        base_composite = max(0.0, base_composite - 20)
    if vol_conf.get("volume_ratio", 1.0) < min_volume_ratio:
        base_composite = max(0.0, base_composite - 15)
    if smart_money["signal"] == "distribution":
        base_composite = max(0.0, base_composite - 25)
    elif smart_money["signal"] == "accumulation":
        base_composite = min(100.0, base_composite + 15)
    base_composite = round(min(100.0, max(0.0, base_composite + candle_signals["score_delta"])), 2)

    # Sector RS
    sector_rs: dict[str, Any] = {"status": "neutral", "rs_score": 1.0}
    if normalized_sector:
        if sector_cache and normalized_sector in sector_cache:
            sector_rs = sector_cache[normalized_sector]
        else:
            try:
                sector_rs = get_sector_relative_strength(normalized_sector)
            except Exception:
                pass
    if sector_rs["status"] == "lagging":
        base_composite = max(0.0, base_composite - 20)
    elif sector_rs["status"] == "leading":
        base_composite = min(100.0, base_composite + 10)

    # Lagging sector block
    lagging_sector_blocked = (sector_rs["status"] == "lagging" and base_composite < 80)

    if key_levels["target_blocked"]:
        base_composite = max(0.0, base_composite - 15)
    if atr_levels and key_levels["nearest_support"]:
        if atr_levels["stop_loss"] > key_levels["nearest_support"]:
            atr_levels = {**atr_levels,
                          "stop_loss": round(key_levels["nearest_support"] * 0.995, 2)}

    if sentiment_dict["label"] == "negative" and sentiment_dict["score"] > 0.55:
        base_composite = max(0.0, base_composite - 25)

    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        base_composite = round(max(0.0, base_composite + macro_modifier), 2)

    base_composite = max(0.0, base_composite - sector_learning_penalty - entry_timing_penalty)

    # Longterm fundamental blend
    fundamental_score = metrics.get("fundamental_score") or 50.0
    if fundamental_score >= 70:
        base_composite = min(100.0, base_composite + 15)
    elif fundamental_score >= 55:
        base_composite = min(100.0, base_composite + 5)
    elif fundamental_score < 40:
        base_composite = max(0.0, base_composite - 15)

    base_composite = round(base_composite, 2)

    # R:R block check
    rr = atr_levels["risk_reward"] if atr_levels else 0.0
    rr_blocked = (rr < 1.5)  # lowered from 2.0 — was too aggressive

    # Compile blocks
    warnings = []
    relaxed_penalties = 0.0

    if regime_blocked:
        relaxed_penalties += 25
        warnings.append("Downtrend regime")
    if distribution_blocked:
        relaxed_penalties += 20
        warnings.append("Institutional distribution")
    if bearish_candle_blocked:
        relaxed_penalties += 15
        warnings.append("Bearish candlestick pattern")
    if personality_blocked:
        relaxed_penalties += 15
        warnings.append("Avoid personality rule")
    if entry_blocked:
        relaxed_penalties += 15
        warnings.append("Unfavorable entry zone")
    if rsi_overbought_blocked:
        relaxed_penalties += 20
        warnings.append("RSI overbought (>75)")
    if sentiment_blocked:
        relaxed_penalties += 20
        warnings.append("Negative news sentiment")
    if lagging_sector_blocked:
        relaxed_penalties += 20
        warnings.append("Lagging sector")
    if rr_blocked:
        relaxed_penalties += 15
        warnings.append("Low R:R ratio (<2.0)")
    if mode_suppressed:
        relaxed_penalties += 30
        warnings.append("Trade mode suppressed")

    is_blocked = (
        regime_blocked or 
        distribution_blocked or 
        bearish_candle_blocked or 
        personality_blocked or 
        entry_blocked or 
        rsi_overbought_blocked or 
        sentiment_blocked or 
        lagging_sector_blocked or 
        rr_blocked or
        mode_suppressed
    )

    strict_composite = 0.0 if is_blocked else base_composite
    relaxed_composite = round(max(0.0, base_composite - relaxed_penalties), 2)

    news_rows = [
        {**article, "sentiment_label": sentiment_dict["label"], "sentiment_score": sentiment_dict["score"]}
        for article in articles
    ]

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": {
            **metrics,
            "regime": regime["regime"],
            "adx": regime["adx"],
            "volume_ratio": vol_conf["volume_ratio"],
            "atr": atr_levels["atr"] if atr_levels else None,
            "risk_reward": atr_levels["risk_reward"] if atr_levels else None,
            "atr_stop_loss": atr_levels["stop_loss"] if atr_levels else None,
            "atr_target_price": atr_levels["target_price"] if atr_levels else None,
            "smart_money_signal": smart_money["signal"],
            "smart_money_cmf": smart_money["cmf"],
            "primary_candle_pattern": candle_signals["primary_pattern"],
            "sector_rs_status": sector_rs["status"],
            "sector_rs_score": sector_rs["rs_score"],
            "nearest_support": key_levels["nearest_support"],
            "nearest_resistance": key_levels["nearest_resistance"],
            "target_blocked": key_levels["target_blocked"],
        },
        "news_score": round(news_score, 2),
        "composite_score": strict_composite,
        "relaxed_composite_score": relaxed_composite,
        "is_blocked": is_blocked,
        "block_reasons": warnings,
        "news_rows": news_rows,
        "atr_levels": atr_levels,
        "overbought_warning": overbought_warning,
        "market_context": {
            "sector_rs_status": sector_rs["status"],
            "market_environment": "caution" if macro_sentiment_score < 45 else "risk_on",
            "nifty_vs_sma20": None,
            "smart_money": smart_money["reason"],
            "primary_candle": candle_signals["primary_pattern"],
        },
        "entry_type": entry_zone["entry_type"],
        "ideal_entry_price": entry_zone["ideal_entry"],
        "entry_note": entry_zone["entry_note"],
        "personality": personality["personality"],
        "confirming_signals_list": [
            sig for sig, cond in [
                ("regime_uptrend", regime["regime"] == "uptrend"),
                ("volume_confirmed", vol_conf.get("confirmed", False) or vol_conf.get("strong", False)),
                ("smart_money_accumulation", smart_money["signal"] == "accumulation"),
                ("sector_leading", sector_rs["status"] == "leading"),
                ("bullish_candlestick", candle_signals["score_delta"] > 0),
                ("fundamental_strong", fundamental_score >= 70),
            ] if cond
        ]
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _compute_news_score(articles: list[dict[str, Any]]) -> float:
    """Compute news sentiment score from articles."""
    headlines = " ".join(
        f"{a.get('title', '')} {a.get('summary', '')[:200]}"
        for a in articles[:3]
    ).strip()

    if headlines and settings.hf_token:
        label, score = hf_ai.analyze_news_sentiment(headlines)
        if label == "positive":
            return 50 + score * 50
        elif label == "negative":
            return 50 - score * 50
        else:
            return 50.0
    elif headlines:
        return hf_ai.score_news_batch(articles)
    return 50.0


def _select_diversified_top_buys(scored: list[dict[str, Any]], count: int = 10) -> list[dict[str, Any]]:
    by_segment: dict[str, list[dict[str, Any]]] = {"large": [], "mid": [], "small": []}
    for item in scored:
        seg = item["profile"].get("cap_segment") or "large"
        if seg in by_segment:
            by_segment[seg].append(item)

    quotas = [("large", 4), ("mid", 3), ("small", 3)]
    picks: list[dict[str, Any]] = []
    used: set[str] = set()

    for segment, quota in quotas:
        for item in by_segment.get(segment, [])[:quota]:
            sym = item["symbol"]
            if sym not in used:
                picks.append(item)
                used.add(sym)

    if len(picks) < count:
        for item in scored:
            if item["symbol"] not in used:
                picks.append(item)
                used.add(item["symbol"])
            if len(picks) >= count:
                break

    picks.sort(key=lambda x: x["composite_score"], reverse=True)
    return picks[:count]


def _strength(score: float) -> str:
    if score >= 75:
        return "strong"
    if score >= 60:
        return "moderate"
    return "weak"


def _target_for_mode(price: float | None, mode: str, atr_levels: dict | None = None) -> float | None:
    """ATR-aware target price. Uses ATR levels if available, else falls back to fixed %."""
    if price is None:
        return None
    # Prefer ATR-based target — enforces 2.5:1 R:R minimum
    if atr_levels and atr_levels.get("target_price"):
        return atr_levels["target_price"]
    multipliers = {
        "intraday": 1.02,
        "swing": 1.10,
        "longterm": 1.20,
        "future": 1.10,
    }
    return round(price * multipliers.get(mode, 1.10), 2)


def _stop_for_mode(price: float | None, mode: str, atr_levels: dict | None = None) -> float | None:
    """ATR-aware stop loss. Uses ATR levels if available, else falls back to fixed %."""
    if price is None:
        return None
    # Prefer ATR-based SL — respects actual volatility
    if atr_levels and atr_levels.get("stop_loss"):
        return atr_levels["stop_loss"]
    multipliers = {
        "intraday": 0.99,
        "swing": 0.95,
        "longterm": 0.90,
        "future": 0.95,
    }
    return round(price * multipliers.get(mode, 0.95), 2)


def _compute_composite_score(
    regime: dict,
    rsi: float,
    macd_cross: bool,
    volume_conf: dict,
    sentiment: dict,
    price_vs_sma: dict,
    atr_levels: dict | None,
) -> float:
    """FIX #6 — New rebalanced composite score formula.

    Weights:
      Regime       30 pts  (most important — don't fight the trend)
      Trend struct 20 pts  (SMA alignment)
      Volume       20 pts  (institutional confirmation)
      RSI          15 pts  (momentum sweet spot 50-65, NOT oversold)
      MACD cross   10 pts
      Sentiment     5 pts
      R:R bonus     5 pts
    """
    score = 0.0

    # Regime (30 pts)
    if regime["regime"] == "uptrend":
        score += 30
    elif regime["regime"] == "sideways":
        score += 15
    # downtrend = 0 (should be gated before reaching here)

    # Trend structure (20 pts)
    if price_vs_sma.get("above_sma200"):
        score += 8
    if price_vs_sma.get("above_sma50"):
        score += 7
    if price_vs_sma.get("above_sma20"):
        score += 5

    # Volume (20 pts)
    if volume_conf.get("strong"):
        score += 20
    elif volume_conf.get("confirmed"):
        score += 13
    else:
        score += 3  # Low volume — low conviction

    # RSI momentum sweet spot (15 pts) — buy strength not weakness
    if 50 <= rsi <= 65:
        score += 15
    elif 45 <= rsi < 50:
        score += 10
    elif 65 < rsi <= 72:
        score += 7   # Getting overbought
    elif 30 <= rsi < 45:
        score += 3   # Weak momentum
    else:
        score += 0   # Overbought >72 or extreme oversold <30 — avoid

    # MACD cross (10 pts)
    if macd_cross:
        score += 10

    # Sentiment (5 pts max, -10 penalty)
    if sentiment:
        if sentiment.get("label") == "positive" and sentiment.get("score", 0) > 0.6:
            score += 5
        elif sentiment.get("label") == "negative":
            score -= 10

    # R:R quality bonus (5 pts)
    if atr_levels:
        rr = atr_levels.get("risk_reward", 0)
        if rr >= 3.0:
            score += 5
        elif rr >= 2.5:
            score += 3

    return round(min(max(score, 0.0), 100.0), 2)


def classify_trade_tier(composite_score: float, confirming_signals: list) -> dict:
    """
    Assigns a visual tier to each recommendation.
    
    S-Tier: The rare setup where everything aligns perfectly.
            Enter with full allocated capital.
    A-Tier: High-quality setup. Standard position size.
    B-Tier: Valid but not exceptional. Half position size.
    C-Tier: Marginal. Paper trade or very small size.
    
    confirming_signals: list of strings — each signal that confirmed
    e.g. ["regime_uptrend", "volume_confirmed", "smart_money_accumulation", 
           "sector_leading", "bullish_engulfing", "above_vwap"]
    """
    num_confirmations = len(confirming_signals)
    
    if composite_score >= 88 and num_confirmations >= 6:
        tier = "S"
        color = "#FFD700"   # Gold
        position_size_pct = 100  # Full allocated capital for this trade
        label = "PRIME SETUP"
        description = "Maximum confluence. All systems aligned."
        
    elif composite_score >= 78 and num_confirmations >= 4:
        tier = "A"
        color = "#00C851"   # Green
        position_size_pct = 75
        label = "HIGH CONFIDENCE"
        description = "Strong setup with multiple confirmations."
        
    elif composite_score >= 68 and num_confirmations >= 3:
        tier = "B"
        color = "#ffbb33"   # Amber
        position_size_pct = 50
        label = "STANDARD SETUP"
        description = "Valid setup. Moderate position size recommended."
        
    else:
        tier = "C"
        color = "#ff4444"   # Red-orange
        position_size_pct = 25
        label = "MARGINAL"
        description = "Technically valid but limited confluence. Small size only."
    
    return {
        "tier": tier,
        "color": color,
        "position_size_pct": position_size_pct,
        "label": label,
        "description": description,
        "confirming_signals": confirming_signals,
        "num_confirmations": num_confirmations
    }
