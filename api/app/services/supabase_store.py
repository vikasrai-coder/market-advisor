from datetime import date, datetime
from typing import Any

from supabase import Client, create_client

from app.config import settings


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
    client.table("stocks").upsert(data).execute()


def insert_news(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        client.table("news_articles").insert(rows).execute()


def insert_metrics(client: Client, row: dict[str, Any]) -> None:
    client.table("stock_metrics").insert(row).execute()


def clear_recommendations_for_date(client: Client, signal_date: date) -> None:
    client.table("recommendations").delete().eq("signal_date", signal_date.isoformat()).execute()


def insert_recommendations(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        client.table("recommendations").insert(rows).execute()


def clear_signals_for_date(client: Client, signal_date: date) -> None:
    client.table("trading_signals").delete().eq("signal_date", signal_date.isoformat()).execute()


def insert_signals(client: Client, rows: list[dict[str, Any]]) -> None:
    if rows:
        client.table("trading_signals").insert(rows).execute()
