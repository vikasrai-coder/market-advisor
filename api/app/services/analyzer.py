from datetime import date, timedelta
from typing import Any

from app.config import settings
from app.services import hf_ai, market_data, supabase_store, technicals
from app.services.supabase_store import get_client


def run_full_analysis() -> dict[str, Any]:
    client = get_client()
    signal_date = date.today()
    trade_date = signal_date + timedelta(days=1)

    run_id: str | None = None
    if client:
        run_id = supabase_store.start_run(client)
        supabase_store.clear_recommendations_for_date(client, signal_date)
        supabase_store.clear_signals_for_date(client, signal_date)

    scored: list[dict[str, Any]] = []
    sell_candidates: list[dict[str, Any]] = []
    symbols = market_data.get_watchlist()
    errors: list[str] = []

    for symbol in symbols:
        try:
            result = _analyze_symbol(symbol)
            scored.append(result)
            if (result["metrics"].get("trend_score") or 0) < 40 or (
                result["metrics"].get("technical_score") or 0
            ) < 35:
                sell_candidates.append(result)
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    top_buys = scored[:10]

    recommendations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    for rank, item in enumerate(top_buys, start=1):
        insight = hf_ai.generate_recommendation_insight(
            item["symbol"],
            item["profile"],
            item["metrics"],
            item["news_score"],
            item["composite_score"],
        )
        rec = {
            "run_id": run_id,
            "symbol": item["symbol"],
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
        signals.append(
            {
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
        for item in scored:
            supabase_store.upsert_stock(client, item["profile"])
            if item.get("news_rows"):
                supabase_store.insert_news(client, item["news_rows"])
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
        supabase_store.insert_recommendations(client, recommendations)
        supabase_store.insert_signals(client, signals)
        if run_id:
            supabase_store.complete_run(client, run_id, len(scored), len(recommendations))

    return {
        "signal_date": signal_date.isoformat(),
        "trade_date": trade_date.isoformat(),
        "stocks_analyzed": len(scored),
        "top_recommendations": recommendations,
        "signals": signals,
        "errors": errors,
        "supabase_persisted": client is not None,
    }


def _analyze_symbol(symbol: str) -> dict[str, Any]:
    profile = market_data.fetch_stock_profile(symbol)
    history = market_data.fetch_price_history(symbol)
    metrics = technicals.compute_indicators(history)
    articles = market_data.fetch_news(symbol)
    news_score = hf_ai.score_news_batch(articles)

    news_rows = []
    for article in articles:
        label, score = hf_ai.analyze_news_sentiment(
            f"{article.get('title', '')} {article.get('summary', '')}"
        )
        news_rows.append({**article, "sentiment_label": label, "sentiment_score": score})

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
