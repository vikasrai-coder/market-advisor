from datetime import date, datetime
from typing import Any

from supabase import Client, create_client

from app.config import settings

STOCK_COLUMNS = {
    "symbol", "name", "sector", "industry", "market_cap", "pe_ratio",
    "dividend_yield", "beta", "fifty_two_week_high", "fifty_two_week_low",
    "cap_segment", "exchange", "currency",
}
RECOMMENDATION_COLUMNS = {
    "id", "run_id", "symbol", "rank", "action", "composite_score", "trend_score",
    "news_score", "technical_score", "ai_confidence", "reasoning", "key_factors",
    "signal_date", "trade_date", "cap_segment", "trade_mode",
    "target_price", "stop_loss", "performance_status", "exit_price",
}
SIGNAL_COLUMNS = {
    "id", "run_id", "symbol", "signal_type", "strength", "price_at_signal",
    "target_price", "stop_loss", "rationale", "signal_date", "planned_trade_date",
    "trade_mode",
}
NEWS_COLUMNS = {
    "symbol", "title", "summary", "url", "source", "sentiment_label",
    "sentiment_score", "published_at",
}
METRIC_COLUMNS = {
    "symbol", "price", "change_pct", "volume", "rsi", "macd", "macd_signal",
    "sma_20", "sma_50", "trend_score", "volatility",
}


def _pick(data: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in allowed and v is not None}


def get_client() -> Client | None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def start_run(client: Client) -> str:
    row = client.table("analysis_runs").insert({"status": "running"}).execute()
    return row.data[0]["id"]


def complete_run(client: Client, run_id: str, stocks: int, recs: int, error: str | None = None) -> None:
    payload: dict[str, Any] = {
        "status": "failed" if error else "completed",
        "stocks_analyzed": stocks,
        "recommendations_count": recs,
        "completed_at": datetime.utcnow().isoformat(),
    }
    if error:
        payload["error_message"] = error
    client.table("analysis_runs").update(payload).eq("id", run_id).execute()


def upsert_stock(client: Client, data: dict[str, Any]) -> None:
    client.table("stocks").upsert(_pick(data, STOCK_COLUMNS)).execute()


def upsert_stocks(client: Client, data_list: list[dict[str, Any]]) -> None:
    if data_list:
        cleaned = [_pick(d, STOCK_COLUMNS) for d in data_list]
        client.table("stocks").upsert(cleaned).execute()


def insert_news(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        cleaned = [_pick(r, NEWS_COLUMNS) for r in rows]
        client.table("news_articles").insert(cleaned).execute()


def insert_metrics(client: Client, row: dict[str, Any]) -> None:
    client.table("stock_metrics").insert(_pick(row, METRIC_COLUMNS)).execute()


def insert_metrics_batch(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        cleaned = [_pick(r, METRIC_COLUMNS) for r in rows]
        client.table("stock_metrics").insert(cleaned).execute()


def clear_recommendations_for_date(client: Client, signal_date: date, trade_mode: str | None = None) -> None:
    query = client.table("recommendations").delete().eq("signal_date", signal_date.isoformat())
    if trade_mode:
        query = query.eq("trade_mode", trade_mode)
    query.execute()


def insert_recommendations(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        cleaned = [_pick(r, RECOMMENDATION_COLUMNS) for r in rows]
        try:
            client.table("recommendations").insert(cleaned).execute()
        except Exception as exc:
            # Fallback: if table doesn't have trade_mode yet, strip it and insert
            if "trade_mode" in str(exc).lower() or "column" in str(exc).lower():
                cols_without_mode = RECOMMENDATION_COLUMNS - {"trade_mode"}
                cleaned_fallback = [_pick(r, cols_without_mode) for r in rows]
                client.table("recommendations").insert(cleaned_fallback).execute()
            else:
                raise exc


def clear_signals_for_date(client: Client, signal_date: date, trade_mode: str | None = None) -> None:
    query = client.table("trading_signals").delete().eq("signal_date", signal_date.isoformat())
    if trade_mode:
        query = query.eq("trade_mode", trade_mode)
    query.execute()


def insert_signals(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        cleaned = [_pick(r, SIGNAL_COLUMNS) for r in rows]
        try:
            client.table("trading_signals").insert(cleaned).execute()
        except Exception as exc:
            # Fallback: if table doesn't have trade_mode yet, strip it and insert
            if "trade_mode" in str(exc).lower() or "column" in str(exc).lower():
                cols_without_mode = SIGNAL_COLUMNS - {"trade_mode"}
                cleaned_fallback = [_pick(r, cols_without_mode) for r in rows]
                client.table("trading_signals").insert(cleaned_fallback).execute()
            else:
                raise exc
