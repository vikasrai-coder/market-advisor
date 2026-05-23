import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.config import settings
from app.watchlists import watchlist_summary
from app import analysis_jobs
from app.services import analyzer, market_data
from app.services.supabase_store import get_client
from app.symbols import normalize_symbol

IS_VERCEL = bool(os.getenv("VERCEL"))
scheduler = BackgroundScheduler()


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _scheduled_analysis() -> None:
    try:
        analyzer.run_full_analysis()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Seed administrative credentials in Supabase Auth on backend startup
    try:
        from app.services.user_roles import seed_admin_user
        seed_admin_user()
    except Exception as exc:
        print(f"Failed to seed admin user on startup: {exc}")

    if not IS_VERCEL and os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
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
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "market": settings.market,
        "exchange": "NSE (Yahoo Finance .NS symbols)",
        "data_provider": "yfinance",
        "watchlist_size": len(settings.watchlist),
        "watchlist_segments": watchlist_summary(),
        "supabase": bool(settings.supabase_url and settings.supabase_service_role_key),
        "huggingface": bool(settings.hf_token),
    }


from pydantic import BaseModel

class AnalysisRequest(BaseModel):
    mode: str = "swing"
    target_date: str | None = None


class BacktestRequest(BaseModel):
    mode: str = "swing"
    start_date: str
    check_days: int = 5


class WatchlistActionRequest(BaseModel):
    user_id: str
    symbol: str


class PortfolioBuyRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: float
    buy_price: float


class PortfolioSellRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: float


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreateRequest(BaseModel):
    email: str
    password: str


class UserPermissionsRequest(BaseModel):
    user_id: str
    permissions: dict


class AdminTradeRequest(BaseModel):
    symbol: str
    quantity: float
    buy_price: float


class AdminTradeCloseRequest(BaseModel):
    trade_id: str
    sell_price: float


@app.post("/api/backtest/simulate")
def simulate_backtest(req: BacktestRequest):
    try:
        from app.services.backtester import run_backtest_simulation
        res = run_backtest_simulation(
            mode=req.mode,
            start_date_str=req.start_date,
            check_days=req.check_days,
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login_endpoint(req: LoginRequest):
    email = req.email.strip()
    password = req.password
    
    # 1. Check master designated admin credentials
    from app.services.user_roles import ADMIN_EMAIL, get_user_role_profile, get_all_roles_profiles
    if email.lower() == ADMIN_EMAIL.lower() and password == "DellCompaq@123":
        # Ensure role profile is seeded
        profile = get_user_role_profile("admin-vikas-id", ADMIN_EMAIL)
        return {
            "user_id": "admin-vikas-id",
            "email": ADMIN_EMAIL,
            "role": "admin",
            "permissions": profile["permissions"],
        }
        
    # 2. Check offline users registry
    profiles = get_all_roles_profiles()
    for p in profiles:
        if p["email"].lower() == email.lower() and p.get("offline_password") == password:
            return {
                "user_id": p["user_id"],
                "email": p["email"],
                "role": p["role"],
                "permissions": p["permissions"],
            }
            
    # Check if there is an auth user inside Supabase (if Supabase is active)
    # Since Supabase handles client logins directly, this endpoint acts as a complete fallback
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/user/profile")
def get_user_profile_endpoint(user_id: str, email: str | None = None):
    try:
        from app.services.user_roles import get_user_role_profile
        profile = get_user_role_profile(user_id, email)
        return profile
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/users")
def get_admin_users():
    try:
        from app.services.user_roles import get_all_roles_profiles
        return {"users": get_all_roles_profiles()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/user/create")
def admin_create_user(req: UserCreateRequest):
    try:
        from app.services.user_roles import create_user_admin
        profile = create_user_admin(req.email, req.password)
        return {"success": True, "profile": profile}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/user/permissions")
def admin_set_user_permissions(req: UserPermissionsRequest):
    try:
        from app.services.user_roles import set_user_permissions
        success = set_user_permissions(req.user_id, req.permissions)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/trades")
def admin_get_trades_endpoint():
    try:
        from app.services.user_roles import get_admin_trades
        return {"trades": get_admin_trades()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/trades/buy")
def admin_buy_trade_endpoint(req: AdminTradeRequest):
    try:
        from app.services.user_roles import record_admin_trade
        success = record_admin_trade(req.symbol, req.quantity, req.buy_price)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/trades/sell")
def admin_sell_trade_endpoint(req: AdminTradeCloseRequest):
    try:
        from app.services.user_roles import close_admin_trade
        success = close_admin_trade(req.trade_id, req.sell_price)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.post("/api/watchlist/sync")
def sync_watchlist():
    try:
        from app.services.watchlist_sync import sync_nse_watchlists
        summary = sync_nse_watchlists()
        return summary
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/user/watchlist")
def get_watchlist_endpoint(user_id: str):
    try:
        from app.services.user_workspace import get_user_watchlist
        return {"watchlist": get_user_watchlist(user_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/watchlist/add")
def add_to_watchlist_endpoint(req: WatchlistActionRequest):
    try:
        from app.services.user_workspace import add_to_watchlist
        success = add_to_watchlist(req.user_id, req.symbol)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/watchlist/remove")
def remove_from_watchlist_endpoint(req: WatchlistActionRequest):
    try:
        from app.services.user_workspace import remove_from_watchlist
        success = remove_from_watchlist(req.user_id, req.symbol)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/user/portfolio")
def get_portfolio_endpoint(user_id: str):
    try:
        from app.services.user_workspace import get_user_portfolio
        return get_user_portfolio(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/portfolio/buy")
def buy_holding_endpoint(req: PortfolioBuyRequest):
    try:
        from app.services.user_workspace import add_to_portfolio
        success = add_to_portfolio(req.user_id, req.symbol, req.quantity, req.buy_price)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/portfolio/sell")
def sell_holding_endpoint(req: PortfolioSellRequest):
    try:
        from app.services.user_workspace import sell_from_portfolio
        success = sell_from_portfolio(req.user_id, req.symbol, req.quantity)
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.post("/api/analysis/run")
def run_analysis(req: AnalysisRequest = None):
    # Support both json body or default
    mode = "swing"
    target_date = None
    if req:
        mode = req.mode
        target_date = req.target_date

    if IS_VERCEL:
        try:
            result = analyzer.run_full_analysis(mode=mode, target_date=target_date)
            return {
                "job_id": "vercel-sync",
                "status": "completed",
                "message": "Analysis complete",
                "result": result,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    running = analysis_jobs.get_running_job()
    if running:
        return {
            "job_id": running["job_id"],
            "status": "running",
            "message": "Analysis already in progress",
        }
    job_id = analysis_jobs.start_job(mode=mode, target_date=target_date)
    return {
        "job_id": job_id,
        "status": "running",
        "message": f"Analysis started for {mode}. Poll /api/analysis/status/{{job_id}} for progress.",
    }


@app.get("/api/analysis/status/{job_id}")
def analysis_status(job_id: str):
    job = analysis_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/analysis/active")
def analysis_active():
    job = analysis_jobs.get_running_job()
    return job or {"status": "idle"}


@app.post("/api/analysis/reconcile")
def run_reconcile():
    try:
        from app.services.reconciler import reconcile_recommendations
        summary = reconcile_recommendations()
        return {
            "status": "success",
            "message": "Reconciliation completed",
            "summary": summary,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/recommendations")
def list_recommendations(trade_date: str | None = None, mode: str | None = None):
    client = get_client()
    if not client:
        cached = analyzer.get_last_result()
        if not cached:
            return {"recommendations": [], "trade_date": None, "source": "memory"}
        recs = cached.get("top_recommendations") or []
        if mode:
            recs = [r for r in recs if r.get("trade_mode") == mode]
        if trade_date:
            recs = [r for r in recs if r.get("trade_date") == trade_date]
        return {
            "recommendations": recs,
            "trade_date": cached.get("trade_date"),
            "source": "memory",
        }
    target_date = trade_date
    if not target_date:
        latest_query = (
            client.table("recommendations")
            .select("trade_date")
        )
        if mode:
            latest_query = latest_query.eq("trade_mode", mode)
        try:
            latest = latest_query.order("trade_date", desc=True).limit(1).execute()
        except Exception as exc:
            if "trade_mode" in str(exc).lower() or "column" in str(exc).lower():
                latest = client.table("recommendations").select("trade_date").order("trade_date", desc=True).limit(1).execute()
            else:
                raise exc
        if latest.data:
            target_date = latest.data[0]["trade_date"]
    query = (
        client.table("recommendations")
        .select("*, stocks(name, sector, pe_ratio, market_cap)")
        .order("rank")
    )
    if target_date:
        query = query.eq("trade_date", target_date)
    
    try:
        if mode:
            query_with_mode = query.eq("trade_mode", mode)
            result = query_with_mode.execute()
        else:
            result = query.execute()
    except Exception as exc:
        if "trade_mode" in str(exc).lower() or "column" in str(exc).lower() or getattr(exc, "code", None) == "42703":
            # Reconstruct completely fresh to avoid mutation issues
            fallback_query = (
                client.table("recommendations")
                .select("*, stocks(name, sector, pe_ratio, market_cap)")
                .order("rank")
            )
            if target_date:
                fallback_query = fallback_query.eq("trade_date", target_date)
            result = fallback_query.execute()
            if mode:
                filtered_data = []
                for row in result.data:
                    row_mode = row.get("trade_mode", "swing")
                    if row_mode == mode:
                        filtered_data.append(row)
                return {"recommendations": filtered_data, "trade_date": target_date, "trade_mode": mode}
        else:
            raise exc
    return {"recommendations": result.data, "trade_date": target_date, "trade_mode": mode}


@app.get("/api/signals")
def list_signals(planned_trade_date: str | None = None, signal_type: str | None = None, mode: str | None = None):
    client = get_client()
    if not client:
        cached = analyzer.get_last_result()
        signals = (cached or {}).get("signals") or []
        if mode:
            signals = [s for s in signals if s.get("trade_mode") == mode]
        if planned_trade_date:
            signals = [s for s in signals if s.get("planned_trade_date") == planned_trade_date]
        if signal_type:
            signals = [s for s in signals if s.get("signal_type") == signal_type]
        return {"signals": signals, "source": "memory"}
    query = client.table("trading_signals").select("*, stocks(name, sector)").order("created_at", desc=True)
    if planned_trade_date:
        query = query.eq("planned_trade_date", planned_trade_date)
    if signal_type:
        query = query.eq("signal_type", signal_type)
    
    try:
        if mode:
            query_with_mode = query.eq("trade_mode", mode)
            result = query_with_mode.limit(50).execute()
        else:
            result = query.limit(50).execute()
    except Exception as exc:
        if "trade_mode" in str(exc).lower() or "column" in str(exc).lower() or getattr(exc, "code", None) == "42703":
            # Reconstruct completely fresh to avoid mutation issues
            fallback_query = client.table("trading_signals").select("*, stocks(name, sector)").order("created_at", desc=True)
            if planned_trade_date:
                fallback_query = fallback_query.eq("planned_trade_date", planned_trade_date)
            if signal_type:
                fallback_query = fallback_query.eq("signal_type", signal_type)
            result = fallback_query.limit(50).execute()
            if mode:
                filtered_data = []
                for row in result.data:
                    row_mode = row.get("trade_mode", "swing")
                    if row_mode == mode:
                        filtered_data.append(row)
                return {"signals": filtered_data}
        else:
            raise exc
    return {"signals": result.data}


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str):
    sym = normalize_symbol(symbol)
    client = get_client()
    if not client:
        profile = market_data.fetch_stock_profile(sym)
        history = market_data.fetch_price_history(sym, "3mo")
        from app.services.technicals import compute_indicators

        metrics_row = compute_indicators(history)
        news = market_data.fetch_news(sym, 10)
        cached = analyzer.get_last_result() or {}
        latest = next(
            (r for r in cached.get("top_recommendations") or [] if r.get("symbol") == sym),
            None,
        )
        return {
            "stock": profile,
            "metrics": [metrics_row] if metrics_row.get("price") else [],
            "news": news,
            "latest_recommendation": latest,
            "source": "yfinance",
        }
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
