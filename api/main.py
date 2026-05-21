import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.config import settings
from app.services import analyzer
from app.services.supabase_store import get_client

scheduler = BackgroundScheduler()


def _scheduled_analysis() -> None:
    try:
        analyzer.run_full_analysis()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
        scheduler.add_job(_scheduled_analysis, "cron", hour=18, minute=0, id="daily_analysis")
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="Market Advisor API",
    description="AI stock buy recommendations via Hugging Face + Supabase",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "supabase": bool(settings.supabase_url and settings.supabase_service_role_key),
        "huggingface": bool(settings.hf_token),
    }


@app.post("/api/analysis/run")
def run_analysis():
    try:
        return analyzer.run_full_analysis()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/recommendations")
def list_recommendations(trade_date: str | None = None):
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    target_date = trade_date
    if not target_date:
        latest = (
            client.table("recommendations")
            .select("trade_date")
            .order("trade_date", desc=True)
            .limit(1)
            .execute()
        )
        if latest.data:
            target_date = latest.data[0]["trade_date"]
    query = (
        client.table("recommendations")
        .select("*, stocks(name, sector, pe_ratio, market_cap)")
        .order("rank")
    )
    if target_date:
        query = query.eq("trade_date", target_date)
    result = query.execute()
    return {"recommendations": result.data, "trade_date": target_date}


@app.get("/api/signals")
def list_signals(planned_trade_date: str | None = None, signal_type: str | None = None):
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    query = client.table("trading_signals").select("*, stocks(name, sector)").order("created_at", desc=True)
    if planned_trade_date:
        query = query.eq("planned_trade_date", planned_trade_date)
    if signal_type:
        query = query.eq("signal_type", signal_type)
    result = query.limit(50).execute()
    return {"signals": result.data}


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str):
    client = get_client()
    sym = symbol.upper()
    if not client:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    stock = client.table("stocks").select("*").eq("symbol", sym).maybe_single().execute()
    metrics = (
        client.table("stock_metrics")
        .select("*")
        .eq("symbol", sym)
        .order("recorded_at", desc=True)
        .limit(30)
        .execute()
    )
    news = (
        client.table("news_articles")
        .select("*")
        .eq("symbol", sym)
        .order("published_at", desc=True)
        .limit(10)
        .execute()
    )
    rec = (
        client.table("recommendations")
        .select("*")
        .eq("symbol", sym)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return {
        "stock": stock.data,
        "metrics": metrics.data,
        "news": news.data,
        "latest_recommendation": rec.data[0] if rec.data else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
