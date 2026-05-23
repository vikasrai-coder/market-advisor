import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable

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
        supabase_store.clear_recommendations_for_date(client, signal_date)
        supabase_store.clear_signals_for_date(client, signal_date)

    symbols = market_data.get_watchlist()
    total_symbols = len(symbols)
    report(0, total_symbols, "scanning", f"[{cfg.label}] Scanning {total_symbols} NSE stocks…")

    scored: list[dict[str, Any]] = []
    sell_candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    completed = 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {
            pool.submit(_analyze_symbol_dispatch, symbol, cfg): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            completed += 1
            try:
                result = future.result()
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
    top_buys = _select_diversified_top_buys(scored, count=cfg.top_picks)

    recommendations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    ai_total = len(top_buys) + min(5, len(sell_candidates))
    ai_done = 0
    report(total_symbols, total_symbols, "ai", f"[{cfg.label}] Generating AI insights…")

    for rank, item in enumerate(top_buys, start=1):
        insight = hf_ai.generate_recommendation_insight(
            item["symbol"],
            item["profile"],
            item["metrics"],
            item["news_score"],
            item["composite_score"],
        )
        ai_done += 1
        report(
            total_symbols,
            total_symbols,
            "ai",
            f"AI insights {ai_done}/{ai_total}…",
        )

        # Mode-specific target/stop calculations
        target_price = _target_for_mode(item["metrics"].get("price"), cfg.mode)
        stop_loss = _stop_for_mode(item["metrics"].get("price"), cfg.mode)

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
            "ai_confidence": insight.get("confidence", 0.7),
            "reasoning": insight.get("reasoning", ""),
            "key_factors": insight.get("key_factors", []),
            "signal_date": signal_date.isoformat(),
            "trade_date": trade_date.isoformat(),
            # Mode-specific extra fields
            "vwap": item["metrics"].get("vwap"),
            "bullish_crossover": item["metrics"].get("bullish_crossover"),
            "golden_cross": item["metrics"].get("golden_cross"),
            "range_52w_pct": item["metrics"].get("range_52w_pct"),
            "pe_ratio": item["metrics"].get("pe_ratio"),
            "dividend_yield": item["metrics"].get("dividend_yield"),
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
                "rationale": insight.get("reasoning", "")[:500],
                "signal_date": signal_date.isoformat(),
                "planned_trade_date": trade_date.isoformat(),
            }
        )

    for item in sell_candidates[:5]:
        rationale = hf_ai.generate_sell_rationale(item["symbol"], item["metrics"])
        ai_done += 1
        report(
            total_symbols,
            total_symbols,
            "ai",
            f"AI insights {ai_done}/{ai_total}…",
        )
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
    report(total_symbols, total_symbols, "done", "Complete")
    return result


# ---------------------------------------------------------------------------
# Dispatch — route to the right analyzer per mode
# ---------------------------------------------------------------------------


def _analyze_symbol_dispatch(symbol: str, cfg: ScanConfig) -> dict[str, Any]:
    """Route to the mode-appropriate symbol analyzer."""
    if cfg.mode == "intraday":
        return _analyze_symbol_intraday(symbol, cfg)
    elif cfg.mode == "longterm":
        return _analyze_symbol_longterm(symbol, cfg)
    else:
        # swing + future use the same analysis
        return _analyze_symbol_swing(symbol, cfg)


def _analyze_symbol_swing(symbol: str, cfg: ScanConfig) -> dict[str, Any]:
    """Original daily analysis — swing + future modes."""
    profile = market_data.fetch_stock_profile(symbol)
    history = market_data.fetch_price_history(symbol, period=cfg.history_period, interval=cfg.history_interval)
    metrics = technicals.compute_indicators(history)
    articles = market_data.fetch_news(symbol, limit=3)

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

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
    }


def _analyze_symbol_intraday(symbol: str, cfg: ScanConfig) -> dict[str, Any]:
    """60-min candle analysis for intraday trading."""
    profile = market_data.fetch_stock_profile(symbol)
    history = market_data.fetch_intraday_history(symbol, period=cfg.history_period, interval=cfg.history_interval)
    metrics = technicals.compute_intraday_indicators(history)
    articles = market_data.fetch_news(symbol, limit=2)

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

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
    }


def _analyze_symbol_longterm(symbol: str, cfg: ScanConfig) -> dict[str, Any]:
    """1-year daily analysis with fundamental scoring for long-term holds."""
    profile = market_data.fetch_stock_profile(symbol)
    history = market_data.fetch_longterm_history(symbol, period=cfg.history_period)
    metrics = technicals.compute_longterm_indicators(history, profile=profile)
    articles = market_data.fetch_news(symbol, limit=3)

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
