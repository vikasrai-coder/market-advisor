import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Callable

from app.config import settings
from app.services import hf_ai, market_data, supabase_store, technicals
from app.services.supabase_store import get_client

_last_result: dict[str, Any] | None = None
ProgressCallback = Callable[[int, int, str, str], None]


def get_last_result() -> dict[str, Any] | None:
    return _last_result


def run_full_analysis(progress_callback: ProgressCallback | None = None) -> dict[str, Any]:
    global _last_result

    def report(done: int, total: int, phase: str, message: str) -> None:
        if progress_callback:
            progress_callback(done, total, phase, message)

    client = get_client()
    signal_date = date.today()
    trade_date = signal_date + timedelta(days=1)

    run_id: str | None = None
    if client:
        run_id = supabase_store.start_run(client)
        supabase_store.clear_recommendations_for_date(client, signal_date)
        supabase_store.clear_signals_for_date(client, signal_date)

    symbols = market_data.get_watchlist()
    total_symbols = len(symbols)
    report(0, total_symbols, "scanning", f"Scanning {total_symbols} NSE stocks…")

    scored: list[dict[str, Any]] = []
    sell_candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    completed = 0

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_analyze_symbol, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            completed += 1
            try:
                result = future.result()
                scored.append(result)
                if (result["metrics"].get("trend_score") or 0) < 40 or (
                    result["metrics"].get("technical_score") or 0
                ) < 35:
                    sell_candidates.append(result)
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
            report(
                completed,
                total_symbols,
                "scanning",
                f"Scored {completed}/{total_symbols} stocks…",
            )

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    top_buys = _select_diversified_top_buys(scored, count=10)

    recommendations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    ai_total = len(top_buys) + min(5, len(sell_candidates))
    ai_done = 0
    report(total_symbols, total_symbols, "ai", "Generating AI buy/sell insights…")

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
        rec = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "symbol": item["symbol"],
            "cap_segment": item["profile"].get("cap_segment"),
            "rank": rank,
            "action": "buy",
            "composite_score": item["composite_score"],
            "trend_score": item["metrics"].get("trend_score"),
            "news_score": item["news_score"],
            "technical_score": item["metrics"].get("technical_score"),
            "ai_confidence": insight.get("confidence", 0.7),
            "reasoning": insight.get("reasoning", ""),
            "key_factors": insight.get("key_factors", []),
            "signal_date": signal_date.isoformat(),
            "trade_date": trade_date.isoformat(),
        }
        recommendations.append(rec)
        signals.append(
            {
                "id": str(uuid.uuid4()),
                "run_id": run_id,
                "symbol": item["symbol"],
                "signal_type": "buy",
                "strength": _strength(item["composite_score"]),
                "price_at_signal": item["metrics"].get("price"),
                "target_price": _target(item["metrics"].get("price")),
                "stop_loss": _stop(item["metrics"].get("price")),
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


def _analyze_symbol(symbol: str) -> dict[str, Any]:
    profile = market_data.fetch_stock_profile(symbol)
    history = market_data.fetch_price_history(symbol)
    metrics = technicals.compute_indicators(history)
    articles = market_data.fetch_news(symbol, limit=3)

    headlines = " ".join(
        f"{a.get('title', '')} {a.get('summary', '')[:200]}"
        for a in articles[:3]
    ).strip()
    label, score = "neutral", 0.5
    if headlines and settings.hf_token:
        label, score = hf_ai.analyze_news_sentiment(headlines)
        if label == "positive":
            news_score = 50 + score * 50
        elif label == "negative":
            news_score = 50 - score * 50
        else:
            news_score = 50.0
    elif headlines:
        news_score = hf_ai.score_news_batch(articles)
    else:
        news_score = 50.0

    news_rows = [
        {**article, "sentiment_label": label, "sentiment_score": score}
        for article in articles
    ]

    trend = metrics.get("trend_score") or 50.0
    technical = metrics.get("technical_score") or 50.0
    composite = round(trend * 0.4 + technical * 0.35 + news_score * 0.25, 2)

    return {
        "symbol": symbol,
        "profile": profile,
        "metrics": metrics,
        "news_score": round(news_score, 2),
        "composite_score": composite,
        "news_rows": news_rows,
    }


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


def _target(price: float | None) -> float | None:
    if price is None:
        return None
    return round(price * 1.05, 2)


def _stop(price: float | None) -> float | None:
    if price is None:
        return None
    return round(price * 0.95, 2)
