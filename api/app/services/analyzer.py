import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable
import pandas as pd
import yfinance as yf

from app.config import settings
from app.scan_modes import ScanConfig, get_config
from app.services import hf_ai, market_data, supabase_store, technicals
from app.services.supabase_store import get_client

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
    try:
        from app.services.google_news import fetch_google_news_rss
        macro_articles = fetch_google_news_rss("NIFTY 50", limit=5)
        if macro_articles:
            macro_sentiment_score = hf_ai.score_news_batch(macro_articles)
            macro_headlines = " | ".join(a.get("title", "") for a in macro_articles[:3])
    except Exception as exc:
        print(f"Error fetching macro/NIFTY news: {exc}")

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
                macro_sentiment_score
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
            trend = item["metrics"].get("trend_score") or 50.0
            technical = item["metrics"].get("technical_score") or 50.0
            fundamental = item["metrics"].get("fundamental_score") or 0.0
            news_score = 50.0
            
            composite = round(
                trend * cfg.weight_trend 
                + technical * cfg.weight_technical 
                + news_score * cfg.weight_news
                + fundamental * cfg.weight_fundamental,
                2,
            )
            if macro_sentiment_score < 45:
                macro_modifier = (macro_sentiment_score - 50.0) * 0.4
                composite = round(composite + macro_modifier, 2)
                
            item["news_score"] = 50.0
            item["composite_score"] = composite
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

        # Update candidate stocks with real news scores and recompute final composite
        for item in top_candidates:
            sym = item["symbol"]
            articles = candidate_news.get(sym, [])
            news_score = _compute_news_score(articles)
            
            trend = item["metrics"].get("trend_score") or 50.0
            technical = item["metrics"].get("technical_score") or 50.0
            fundamental = item["metrics"].get("fundamental_score") or 0.0
            
            composite = round(
                trend * cfg.weight_trend 
                + technical * cfg.weight_technical 
                + news_score * cfg.weight_news
                + fundamental * cfg.weight_fundamental,
                2,
            )
            if macro_sentiment_score < 45:
                macro_modifier = (macro_sentiment_score - 50.0) * 0.4
                composite = round(composite + macro_modifier, 2)
            
            item["news_score"] = round(news_score, 2)
            item["composite_score"] = composite
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

    top_buys = _select_diversified_top_buys(scored, count=cfg.top_picks)

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
                reasoning += f" Warning: Bearish NIFTY news sentiment ({macro_sentiment_score:.0f}/100) suggests high risk of gap-down opening."
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
            for rank, item in enumerate(top_buys, start=1)
        ]
        sell_futures = [
            ai_pool.submit(_fetch_sell_rationale, item)
            for item in sell_candidates[:5]
        ]
        
        # Process buy results
        for future in as_completed(buy_futures):
            rank, item, insight = future.result()
            target_price = _target_for_mode(item["metrics"].get("price"), cfg.mode)
            stop_loss = _stop_for_mode(item["metrics"].get("price"), cfg.mode)

            # Quantitative relative valuation scoring vs sector medians
            item_sector = item["profile"].get("sector")
            item_pe = item["profile"].get("pe_ratio")
            is_undervalued = False
            if item_sector and item_pe is not None and item_pe > 0 and item_sector in sector_medians:
                if item_pe < sector_medians[item_sector] * 0.8:
                    is_undervalued = True

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
                "reasoning": insight.get("reasoning", "") if isinstance(insight, dict) else str(insight),
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
                "overnight_gap_down_warning": macro_sentiment_score < 30,
                "stocks": {
                    "name": item["profile"].get("name"),
                    "sector": item["profile"].get("sector"),
                    "pe_ratio": item["profile"].get("pe_ratio"),
                    "market_cap": item["profile"].get("market_cap"),
                    "is_undervalued": is_undervalued,
                },
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
                    "rationale": (insight.get("reasoning", "") if isinstance(insight, dict) else str(insight))[:500],
                    "signal_date": signal_date.isoformat(),
                    "planned_trade_date": trade_date.isoformat(),
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
        for item in scored:
            supabase_store.upsert_stock(client, item["profile"])
            supabase_store.insert_metrics(
                client,
                {
                    "symbol": item["symbol"],
                    **{k: item["metrics"].get(k) for k in (
                        "price", "change_pct", "volume", "rsi", "macd", "macd_signal",
                        "sma_20", "sma_50", "trend_score", "volatility",
                    )},
                },
            )
        for item in top_buys:
            if item.get("news_rows"):
                supabase_store.insert_news(client, item["news_rows"])
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
) -> dict[str, Any]:
    """Route to the mode-appropriate symbol analyzer."""
    if cfg.mode == "intraday":
        return _analyze_symbol_intraday(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score)
    elif cfg.mode == "longterm":
        return _analyze_symbol_longterm(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score)
    else:
        # swing + future use the same analysis
        return _analyze_symbol_swing(symbol, cfg, db_profile, history_df, news_articles, macro_sentiment_score)


def _analyze_symbol_swing(
    symbol: str, 
    cfg: ScanConfig, 
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
) -> dict[str, Any]:
    """Original daily analysis — swing + future modes."""
    profile = db_profile if db_profile is not None else market_data.fetch_stock_profile(symbol)
    history = history_df if history_df is not None and not history_df.empty else market_data.fetch_price_history(symbol, period=cfg.history_period, interval=cfg.history_interval)
    metrics = technicals.compute_indicators(history)
    articles = news_articles if news_articles is not None else []

    news_score = _compute_news_score(articles)

    news_rows = [
        {**article, "sentiment_label": "neutral", "sentiment_score": 0.5}
        for article in articles
    ]

    trend = metrics.get("trend_score") or 50.0
    technical = metrics.get("technical_score") or 50.0
    composite = round(
        trend * cfg.weight_trend + technical * cfg.weight_technical + news_score * cfg.weight_news,
        2,
    )
    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        composite = round(composite + macro_modifier, 2)

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
    }


def _analyze_symbol_intraday(
    symbol: str, 
    cfg: ScanConfig, 
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
) -> dict[str, Any]:
    """60-min candle analysis for intraday trading."""
    profile = db_profile if db_profile is not None else market_data.fetch_stock_profile(symbol)
    history = history_df if history_df is not None and not history_df.empty else market_data.fetch_intraday_history(symbol, period=cfg.history_period, interval=cfg.history_interval)
    metrics = technicals.compute_intraday_indicators(history)
    articles = news_articles if news_articles is not None else []

    news_score = _compute_news_score(articles)

    news_rows = [
        {**article, "sentiment_label": "neutral", "sentiment_score": 0.5}
        for article in articles
    ]

    trend = metrics.get("trend_score") or 50.0
    technical = metrics.get("technical_score") or 50.0
    composite = round(
        trend * cfg.weight_trend + technical * cfg.weight_technical + news_score * cfg.weight_news,
        2,
    )
    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        composite = round(composite + macro_modifier, 2)

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
    }


def _analyze_symbol_longterm(
    symbol: str, 
    cfg: ScanConfig, 
    db_profile: dict[str, Any] | None = None,
    history_df: Any = None,
    news_articles: list[dict[str, Any]] | None = None,
    macro_sentiment_score: float = 50.0,
) -> dict[str, Any]:
    """1-year daily analysis with fundamental scoring for long-term holds."""
    profile = db_profile if db_profile is not None else market_data.fetch_stock_profile(symbol)
    history = history_df if history_df is not None and not history_df.empty else market_data.fetch_longterm_history(symbol, period=cfg.history_period)
    metrics = technicals.compute_longterm_indicators(history, profile=profile)
    articles = news_articles if news_articles is not None else []

    news_score = _compute_news_score(articles)

    news_rows = [
        {**article, "sentiment_label": "neutral", "sentiment_score": 0.5}
        for article in articles
    ]

    trend = metrics.get("trend_score") or 50.0
    technical = metrics.get("technical_score") or 50.0
    fundamental = metrics.get("fundamental_score") or 50.0
    composite = round(
        trend * cfg.weight_trend
        + technical * cfg.weight_technical
        + news_score * cfg.weight_news
        + fundamental * cfg.weight_fundamental,
        2,
    )
    if macro_sentiment_score < 45:
        macro_modifier = (macro_sentiment_score - 50.0) * 0.4
        composite = round(composite + macro_modifier, 2)

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
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


def _target_for_mode(price: float | None, mode: str) -> float | None:
    """Mode-appropriate target price."""
    if price is None:
        return None
    multipliers = {
        "intraday": 1.02,   # 2% target for intraday
        "swing": 1.05,      # 5% target for swing
        "longterm": 1.15,   # 15% target for long-term
        "future": 1.05,     # 5% target for future (swing-like)
    }
    return round(price * multipliers.get(mode, 1.05), 2)


def _stop_for_mode(price: float | None, mode: str) -> float | None:
    """Mode-appropriate stop loss."""
    if price is None:
        return None
    multipliers = {
        "intraday": 0.99,   # 1% stop for intraday
        "swing": 0.95,      # 5% stop for swing
        "longterm": 0.90,   # 10% stop for long-term
        "future": 0.95,     # 5% stop for future
    }
    return round(price * multipliers.get(mode, 0.95), 2)
