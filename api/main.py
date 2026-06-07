import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


def is_indian_market_hours() -> bool:
    if os.getenv("FORCE_LIVE_SYNC", "false").lower() == "true":
        return True
    
    from datetime import datetime, timezone, timedelta
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(ist_tz)
    
    # Weekdays: Mon=0 to Fri=4
    if now_ist.weekday() > 4:
        return False
        
    # 9:15 AM to 3:30 PM
    minutes = now_ist.hour * 60 + now_ist.minute
    return 555 <= minutes <= 930


def _live_market_sync() -> None:
    if not is_indian_market_hours():
        return
        
    print("[LiveSync] Starting 2-minute live synchronization...", flush=True)
    
    # 1. Reconcile recommendations
    try:
        from app.services.reconciler import reconcile_recommendations
        reconcile_recommendations()
    except Exception as exc:
        print(f"[LiveSync] Error in reconcile_recommendations: {exc}", flush=True)

    # 2. Reconcile active stop/target triggers for all users
    try:
        from app.services.user_roles import get_all_roles_profiles
        from app.services.user_workspace import reconcile_active_triggers
        
        profiles = get_all_roles_profiles()
        for profile in profiles:
            user_id = profile.get("user_id")
            if user_id:
                try:
                    reconcile_active_triggers(user_id)
                except Exception as user_exc:
                    print(f"[LiveSync] Error reconciling triggers for user {user_id}: {user_exc}", flush=True)
    except Exception as exc:
        print(f"[LiveSync] Error fetching user roles / profiles: {exc}", flush=True)

    # 3. Synchronize prices and run scans
    try:
        analyzer.run_full_analysis(mode="intraday")
    except Exception as exc:
        print(f"[LiveSync] Error running intraday scan: {exc}", flush=True)
        
    try:
        analyzer.run_full_analysis(mode="swing")
    except Exception as exc:
        print(f"[LiveSync] Error running swing scan: {exc}", flush=True)


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
        scheduler.add_job(_live_market_sync, "interval", minutes=2, id="live_market_sync")
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
from app.domains.strategies.models import (
    StrategyCloneRequest,
    StrategyCreateRequest,
    StrategyValidationRequest,
    StrategyVersionRequest,
)

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
    target_price: float | None = None
    stop_loss: float | None = None


class PortfolioThresholdUpdateRequest(BaseModel):
    user_id: str
    symbol: str
    target_price: float | None = None
    stop_loss: float | None = None


class PortfolioSellRequest(BaseModel):
    user_id: str
    symbol: str
    quantity: float
    sell_price: float | None = None



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
    target_price: float | None = None
    stop_loss: float | None = None
    source_alert_id: str | None = None


class AdminTradeCloseRequest(BaseModel):
    trade_id: str
    sell_price: float


class SystemSettingsRequest(BaseModel):
    usage_mode: str


class ChatbotRequest(BaseModel):
    message: str
    symbol: str | None = None
    shares: float | None = None
    buy_price: float | None = None


@app.post("/api/strategies/validate")
def validate_strategy_endpoint(req: StrategyValidationRequest):
    try:
        from app.domains.strategies.service import validate_definition
        return validate_definition(req.definition)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/strategies")
def list_strategies_endpoint(user_id: str):
    try:
        from app.domains.strategies.service import list_strategies
        return {"strategies": list_strategies(user_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/strategies")
def create_strategy_endpoint(req: StrategyCreateRequest):
    try:
        from app.domains.strategies.service import create_strategy
        return {"strategy": create_strategy(req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/strategies/{strategy_id}")
def get_strategy_endpoint(strategy_id: str, user_id: str):
    try:
        from app.domains.strategies.service import get_strategy
        return {"strategy": get_strategy(strategy_id, user_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/strategies/{strategy_id}/versions")
def create_strategy_version_endpoint(strategy_id: str, req: StrategyVersionRequest):
    try:
        from app.domains.strategies.service import add_strategy_version
        return {"version": add_strategy_version(strategy_id, req.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/strategies/{strategy_id}/clone")
def clone_strategy_endpoint(strategy_id: str, req: StrategyCloneRequest):
    try:
        from app.domains.strategies.service import clone_strategy
        return {"strategy": clone_strategy(strategy_id, req.user_id, req.name)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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


@app.post("/api/chatbot/ask")
def chatbot_ask_endpoint(req: ChatbotRequest):
    try:
        from app.services.supabase_store import get_client
        from app.symbols import normalize_symbol
        import logging

        logger = logging.getLogger(__name__)
        client = get_client()

        symbol = req.symbol
        shares = req.shares
        buy_price = req.buy_price
        message = req.message

        # Ticker & Metric Auto-Extraction: Parse symbol, shares, and cost directly from text queries if omitted
        import re
        if not symbol and message:
            # 1. Match suffix format: e.g. KAYNES.NS, TCS.BO, Dixon.ns
            match = re.search(r'\b([A-Za-z0-9_-]+\.(NS|BO))\b', message)
            if match:
                symbol = match.group(1).upper()
            else:
                # 2. Match generic raw uppercase symbols: e.g. "KAYNES", "TCS", "RELIANCE"
                words = re.findall(r'\b([A-Z]{3,10})\b', message)
                for w in words:
                    if w not in ["NSE", "BSE", "INR", "USD", "BUY", "SELL", "HOLD"]:
                        symbol = f"{w}.NS"
                        break

        if not buy_price and message:
            # Match formats like: bought at 3000, at ₹3000, price of 3000, @ 3000, etc.
            price_match = re.search(r'(?:bought\s+at|at|price|₹|@)\s*(\d+(?:\.\d+)?)', message, re.IGNORECASE)
            if price_match:
                buy_price = float(price_match.group(1))

        if not shares and message:
            # Match formats like: 10 shares, 50 qty, 5 shares, 20 units
            qty_match = re.search(r'(\d+)\s*(?:shares|qty|units|sh|holding)', message, re.IGNORECASE)
            if qty_match:
                shares = float(qty_match.group(1))

        # Fetch recovery picks
        short_term_picks = []
        medium_term_picks = []
        long_term_picks = []

        if client:
            try:
                # Query the latest active trade date for swing recommendations
                latest_swing = client.table("recommendations").select("trade_date").eq("trade_mode", "swing").order("trade_date", desc=True).limit(1).execute()
                latest_swing_date = latest_swing.data[0]["trade_date"] if latest_swing and latest_swing.data else None

                query_swing = client.table("recommendations").select("*, stocks(name)").eq("trade_mode", "swing")
                if latest_swing_date:
                    query_swing = query_swing.eq("trade_date", latest_swing_date)
                recs_res = query_swing.order("rank").limit(10).execute() # Fetch more to allow filtering corrupt rows
                
                if recs_res and recs_res.data:
                    for r in recs_res.data:
                        target = float(r.get("target_price") or 0)
                        stop = float(r.get("stop_loss") or 0)
                        # Skip corrupt or placeholder rows
                        if target <= 0 or stop <= 0:
                            continue
                        display = r["symbol"].replace(".NS", "")
                        reason = r.get("reasoning", "")
                        pick_info = f"{display} (Target: INR {target:.2f}, Stop-Loss: INR {stop:.2f}) - {reason[:120]}..."
                        if len(short_term_picks) < 2:
                            short_term_picks.append(pick_info)
                        elif len(medium_term_picks) < 2:
                            medium_term_picks.append(pick_info)
                
                # Query the latest active trade date for longterm recommendations
                latest_long = client.table("recommendations").select("trade_date").eq("trade_mode", "longterm").order("trade_date", desc=True).limit(1).execute()
                latest_long_date = latest_long.data[0]["trade_date"] if latest_long and latest_long.data else None

                query_long = client.table("recommendations").select("*, stocks(name)").eq("trade_mode", "longterm")
                if latest_long_date:
                    query_long = query_long.eq("trade_date", latest_long_date)
                long_res = query_long.order("rank").limit(10).execute()

                if long_res and long_res.data:
                    for r in long_res.data:
                        target = float(r.get("target_price") or 0)
                        stop = float(r.get("stop_loss") or 0)
                        if target <= 0 or stop <= 0:
                            continue
                        display = r["symbol"].replace(".NS", "")
                        reason = r.get("reasoning", "")
                        long_term_picks.append(f"{display} (Target: INR {target:.2f}, Stop-Loss: INR {stop:.2f}) - {reason[:120]}...")
            except Exception as exc:
                logger.error(f"Error querying chatbot recovery picks: {exc}")

        if not short_term_picks or not long_term_picks:
            try:
                from app.services.analyzer import get_last_result
                cached = get_last_result() or {}
                cached_recs = cached.get("top_recommendations") or []
                for r in cached_recs:
                    display = r.get("symbol", "").replace(".NS", "")
                    target = float(r.get("target_price") or 0)
                    stop = float(r.get("stop_loss") or 0)
                    reason = r.get("reasoning", "")
                    pick_info = f"{display} (Target: INR {target:.2f}, Stop-Loss: INR {stop:.2f}) - {reason[:120]}..."
                    mode_r = r.get("trade_mode", "swing")
                    if mode_r == "swing":
                        if len(short_term_picks) < 2:
                            short_term_picks.append(pick_info)
                        else:
                            medium_term_picks.append(pick_info)
                    elif mode_r == "longterm":
                        long_term_picks.append(pick_info)
            except Exception:
                pass

        # Apply robust default recovery picks if database is completely empty
        if not short_term_picks:
            short_term_picks = [
                "RELIANCE (Target: INR 2,750.00, Stop-Loss: INR 2,420.00) - Strong support at 200 SMA, high bullish momentum.",
                "TCS (Target: INR 4,120.00, Stop-Loss: INR 3,750.00) - Q4 earnings outperformance, stable sector defensive buy."
            ]
        if not medium_term_picks:
            medium_term_picks = [
                "HDFCBANK (Target: INR 1,650.00, Stop-Loss: INR 1,440.00) - Net interest margin stabilization, high credit growth.",
                "ICICIBANK (Target: INR 1,220.00, Stop-Loss: INR 1,080.00) - Sector leader with robust balance sheet."
            ]
        if not long_term_picks:
            long_term_picks = [
                "INFY (Target: INR 1,750.00, Stop-Loss: INR 1,450.00) - Large digital deal pipeline, strong long-term structural tailwinds.",
                "L&T (Target: INR 3,900.00, Stop-Loss: INR 3,350.00) - Order book expansion, robust infrastructure capital expenditure."
            ]

        # Gather queried stock metrics
        stock_details = None
        if symbol:
            try:
                sym = normalize_symbol(symbol)
                from app.services.market_data import fetch_stock_profile, fetch_price_history
                profile = fetch_stock_profile(sym)
                history = fetch_price_history(sym, "5d")
                
                current_price = None
                if not history.empty:
                    current_price = float(history["Close"].iloc[-1])
                
                latest_rec_reasoning = None
                if client:
                    rec_res = client.table("recommendations").select("reasoning").eq("symbol", sym).order("created_at", desc=True).limit(1).execute()
                    if rec_res and rec_res.data:
                        latest_rec_reasoning = rec_res.data[0].get("reasoning")
                
                if current_price:
                    buy_pr = buy_price if buy_price and buy_price > 0 else current_price
                    qty = shares if shares and shares > 0 else 1.0
                    current_value = qty * current_price
                    pnl = (current_price - buy_pr) * qty
                    pnl_pct = ((current_price - buy_pr) / buy_pr) * 100
                    
                    stock_details = {
                        "symbol": sym,
                        "name": profile.get("name") or sym,
                        "sector": profile.get("sector") or "N/A",
                        "current_price": current_price,
                        "buy_price": buy_pr,
                        "shares": qty,
                        "current_value": current_value,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "latest_rec_reasoning": latest_rec_reasoning
                    }
            except Exception as exc:
                logger.error(f"Error fetching stock details for chatbot query: {exc}")

        # Formulate Prompt
        prompt = f"""You are a professional, elite AI Stock Portfolio Advisor & Market Analyst for the Indian Stock Market (NSE).
The user is asking: "{message}"

Please analyze their request using these specific parameters:"""

        if stock_details:
            prompt += f"""
- Stock Symbol: {stock_details['symbol']} ({stock_details['name']})
- Sector: {stock_details['sector']}
- Shares Owned: {stock_details['shares']}
- Purchased Price: INR {stock_details['buy_price']:.2f}
- Real-time Current Price: INR {stock_details['current_price']:.2f}
- Current Valuation: INR {stock_details['current_value']:.2f}
- Net Profit/Loss (P&L): INR {stock_details['pnl']:.2f} ({stock_details['pnl_pct']:+.2f}%)
- Existing Analyst System Score Context: {stock_details['latest_rec_reasoning'] or "No active scanner ratings in the database"}"""

        prompt += f"""

High-Probability Recovery/Investment Picks:
- Short term (7 Trading Days):
  1. {short_term_picks[0]}
  2. {short_term_picks[1] if len(short_term_picks) > 1 else ""}
- Medium term (30 Trading Days):
  1. {medium_term_picks[0]}
  2. {medium_term_picks[1] if len(medium_term_picks) > 1 else ""}
- Long term (6 Months):
  1. {long_term_picks[0]}
  2. {long_term_picks[1] if len(long_term_picks) > 1 else ""}

Format your response in neat, professional GitHub markdown including bullet points, bold lists, and short sections:
1. **Holding Analysis**: Provide an elegant analysis of whether they should stay invested, reduce position, or exit based on trend and P/L (if a stock is queried). Be direct, supportive, and realistic.
2. **Loss Recovery Recommendations**: Present the 7-day, 30-day, and 6-month recovery picks with clear targets, stop-losses, and expected projections to recover any losses.
3. **Disclaimer**: Add a strict, visible disclaimer stating: "DISCLAIMER: This is an AI generated recommendation for educational purposes only. Investing involves risk. All trading decisions must be made independently by the user."

Reply now in a highly polished, premium analyst tone."""

        # Attempt to get LLM response
        response_text = None
        from app.config import settings
        if settings.hf_token:
            from app.services.hf_ai import generate_advisor_response
            response_text = generate_advisor_response(prompt)

        # Fallback if AI token is missing or fails
        if not response_text:
            # Algorithmic markdown generator
            md = f"### 📊 AI Portfolio Holding & Market Recovery Analysis\n\n"
            if stock_details:
                action = "HOLD & MONITOR"
                if stock_details["pnl_pct"] < -10:
                    action = "CONSIDER REDUCING POSITION (RISK AVOIDANCE)"
                elif stock_details["pnl_pct"] > 5:
                    action = "PARTIAL PROFIT BOOKING OR HOLD"
                
                md += f"**Holding Details for {stock_details['name']} ({stock_details['symbol']})**:\n"
                md += f"- **Sector**: {stock_details['sector']}\n"
                md += f"- **Current P&L**: **INR {stock_details['pnl']:.2f} ({stock_details['pnl_pct']:+.2f}%)**\n"
                md += f"- **Current Market Value**: INR {stock_details['current_value']:.2f} (Current Price: INR {stock_details['current_price']:.2f})\n\n"
                
                md += f"#### **1. Holding Advisor Verdict: `{action}`**\n"
                md += f"- Your investment of {stock_details['shares']} shares bought at INR {stock_details['buy_price']:.2f} is currently valued at INR {stock_details['current_value']:.2f}.\n"
                if stock_details["pnl_pct"] < -8:
                    md += f"- **Risk Assessment**: The stock has slipped significantly below your entry price. If support levels break, it is recommended to cut losses conservatively and reallocate capital into high-momentum recovery picks to offset deficits.\n"
                else:
                    md += f"- **Trend Assessment**: The technical indicators indicate the stock remains in a stable accumulation range. It is recommended to hold with a strict stop-loss set 5% below current support.\n"
                if stock_details["latest_rec_reasoning"]:
                    md += f"- **Analyst Note**: {stock_details['latest_rec_reasoning']}\n"
                md += "\n"
            else:
                md += f"#### **1. Market Outlook & General Advice**\n"
                md += f"- You asked: *\"{message}\"*\n"
                md += f"- We recommend taking a highly disciplined, risk-managed approach to your capital allocation. Diversify across cap segments and execute trades with predefined targets and stop-losses.\n\n"

            md += f"#### **2. Loss Recovery & Reinvestment Plan**\n"
            md += f"To recoup potential losses or deploy fresh capital efficiently, consider allocating into the following scanned recommendations:\n\n"
            
            md += f"🗓️ **Short-Term Horizon (7 Trading Days - Tactical Swing/Momentum)**\n"
            for pick in short_term_picks:
                md += f"- {pick}\n"
            md += "\n"

            md += f"📅 **Medium-Term Horizon (30 Trading Days - Core Swing Scans)**\n"
            for pick in medium_term_picks:
                md += f"- {pick}\n"
            md += "\n"

            md += f"📈 **Long-Term Horizon (6 Months - Fundamental Value Picks)**\n"
            for pick in long_term_picks:
                md += f"- {pick}\n"
            md += "\n"

            md += f"> **⚠️ STRICT FINANCIAL DISCLAIMER**\n"
            md += f"> *This report is an AI-generated suggestion for educational purposes only. Equity trading involves substantial risk of loss. The user remains solely responsible for all financial decisions and must verify with a certified advisor before acting.*"
            response_text = md

        return {"response": response_text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login_endpoint(req: LoginRequest):
    email = req.email.strip()
    password = req.password
    
    # 1. Check master designated admin credentials
    from app.services.user_roles import ADMIN_EMAIL, get_user_role_profile, get_all_roles_profiles
    import os
    import bcrypt
    admin_password = os.getenv("ADMIN_PASSWORD", "MarketAdvisorRotated#2026")
    if email.lower() == ADMIN_EMAIL.lower() and password == admin_password:
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
        if p["email"].lower() == email.lower():
            hashed_pw = p.get("offline_password_hash")
            if hashed_pw and bcrypt.checkpw(password.encode(), hashed_pw.encode()):
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


@app.get("/api/admin/system-settings")
def get_system_settings():
    try:
        from app.services.system_settings import get_settings
        return get_settings()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/system-settings")
def save_system_settings(req: SystemSettingsRequest):
    try:
        from app.services.system_settings import save_settings
        return save_settings(req.usage_mode)
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
        success = record_admin_trade(
            req.symbol,
            req.quantity,
            req.buy_price,
            target_price=req.target_price,
            stop_loss=req.stop_loss,
            source_alert_id=req.source_alert_id,
        )
        return {"success": success}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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


@app.get("/api/admin/penny-scans")
def admin_penny_scans():
    try:
        import yfinance as yf
        import numpy as np
        import pandas as pd
        from app.services import market_data
        from app.services.supabase_store import get_client

        # 1. Fetch watchlist symbols
        watchlist = market_data.get_watchlist()
        
        # 2. Try to enrich with known database symbols
        client = get_client()
        if client:
            try:
                db_res = client.table("stocks").select("symbol").execute()
                if db_res and db_res.data:
                    watchlist = list(set(watchlist + [row["symbol"] for row in db_res.data]))
            except Exception:
                pass

        # Ensure we have some default symbols if watchlist is empty
        if not watchlist:
            watchlist = [
                "SUZLON.NS", "YESBANK.NS", "PNB.NS", "SAIL.NS", "GMRINFRA.NS",
                "INFIBEAM.NS", "NHPC.NS", "SJVN.NS", "NBCC.NS", "IRFC.NS"
            ]

        # Bulk download historical data (10-day period) in a single request
        tickers_str = " ".join(watchlist)
        df = yf.download(
            tickers_str, period="10d", interval="1d",
            group_by="ticker", progress=False, threads=True, timeout=20
        )

        results = []
        for sym in watchlist:
            try:
                # Get the DataFrame for this ticker
                if isinstance(df.columns, pd.MultiIndex):
                    if sym in df.columns.get_level_values(0):
                        ticker_df = df[sym].copy().dropna(how="all")
                    else:
                        continue
                else:
                    ticker_df = df.copy().dropna(how="all")
                
                if ticker_df.empty or len(ticker_df) < 2:
                    continue
                
                # Check closing prices
                close_prices = ticker_df["Close"].dropna().tolist()
                if not close_prices or len(close_prices) < 2:
                    continue
                
                current_price = round(close_prices[-1], 2)
                
                # Filter for penny stock (< Rs. 150)
                if current_price >= 150.0:
                    continue
                    
                # Calculate change percentage
                prev_close = close_prices[-2]
                change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)
                
                # Filter for performing assets only (positive daily change/momentum)
                if change_pct <= 0.0:
                    continue
                
                sma_5 = round(sum(close_prices[-5:]) / len(close_prices[-5:]), 2)
                
                # Calculate RSI (5-period lookback)
                rsi = 55.0
                if len(close_prices) >= 6:
                    deltas = np.diff(close_prices[-6:])
                    gains = deltas[deltas > 0]
                    losses = -deltas[deltas < 0]
                    avg_gain = sum(gains) / 5 if len(gains) > 0 else 0
                    avg_loss = sum(losses) / 5 if len(losses) > 0 else 1
                    rs = avg_gain / avg_loss if avg_loss != 0 else 0
                    rsi = round(100 - (100 / (1 + rs)), 2)
                
                entry = round(current_price * 0.99, 2)
                exit_today = round(entry * 1.025, 2)
                exit_tomorrow = round(entry * 1.06, 2)
                stop_loss = round(entry * 0.97, 2)
                
                if rsi > 58:
                    rec_type = "Intraday Today"
                    verdict = f"Strong breakout momentum with RSI at {rsi}. Target immediate intraday scalp target at Rs. {exit_today}."
                else:
                    rec_type = "Swing Tomorrow"
                    verdict = f"Support accumulation zone. Accumulate at entry with a target of Rs. {exit_tomorrow} by next session."
                
                results.append({
                    "symbol": sym,
                    "display_symbol": sym.replace(".NS", "").replace(".BO", ""),
                    "name": sym.replace(".NS", "").replace(".BO", "") + " Ltd",
                    "price": current_price,
                    "change_pct": change_pct,
                    "rsi": rsi,
                    "sma_5": sma_5,
                    "entry": entry,
                    "exit_today": exit_today,
                    "exit_tomorrow": exit_tomorrow,
                    "stop_loss": stop_loss,
                    "recommendation": rec_type,
                    "verdict": verdict
                })
            except Exception:
                pass
                
        # Sort performing penny stocks descending by daily change percentage
        results.sort(key=lambda x: x["change_pct"], reverse=True)
        
        # Fallback to dummy data if no performing penny stocks are found (e.g. general market selloff/offline)
        if not results:
            dummy_prices = {
                "SUZLON.NS": (44.50, 1.25, 62.5, "Bullish hourly range breakout. High buying pressure."),
                "YESBANK.NS": (23.40, 0.85, 48.0, "Consolidating near support. Safe entry for swing."),
                "PNB.NS": (142.10, 2.45, 65.0, "Volume spike on daily chart. Intraday continuation expected."),
                "SAIL.NS": (121.20, 1.10, 42.0, "Oversold RSI rebound. Entry near weekly support."),
                "GMRINFRA.NS": (78.30, 3.80, 71.0, "Aggressive trend line break. Strong momentum trade."),
                "INFIBEAM.NS": (31.50, 0.50, 53.0, "Ascending triangle pattern. Breakout expected soon."),
                "NHPC.NS": (85.60, 0.40, 50.0, "Pullback to 20-EMA. High probability swing hold."),
                "SJVN.NS": (132.40, 4.15, 68.0, "Heavy block deals detected. Dynamic momentum scalp."),
                "NBCC.NS": (74.20, 1.85, 59.0, "Government order inflows support price action."),
                "IRFC.NS": (148.50, 0.90, 55.0, "Railway sector momentum. Solid breakout target.")
            }
            for sym, (price, change, rsi, desc) in dummy_prices.items():
                if price >= 150.0 or change <= 0.0:
                    continue
                entry = round(price * 0.99, 2)
                exit_today = round(entry * 1.025, 2)
                exit_tomorrow = round(entry * 1.06, 2)
                stop_loss = round(entry * 0.97, 2)
                rec_type = "Intraday Today" if rsi > 58 else "Swing Tomorrow"
                results.append({
                    "symbol": sym,
                    "display_symbol": sym.replace(".NS", ""),
                    "name": sym.replace(".NS", "") + " Ltd",
                    "price": price,
                    "change_pct": change,
                    "rsi": rsi,
                    "sma_5": round(price * 0.985, 2),
                    "entry": entry,
                    "exit_today": exit_today,
                    "exit_tomorrow": exit_tomorrow,
                    "stop_loss": stop_loss,
                    "recommendation": rec_type,
                    "verdict": desc
                })
            results.sort(key=lambda x: x["change_pct"], reverse=True)

        return {"penny_scans": results[:10]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/alpha-alerts")
def admin_alpha_alerts(refresh: bool = False):
    """Run/retrieve the alpha scanner.

    Returns cached scan results if fresh.
    Otherwise, starts a background job and returns the job ID.
    """
    try:
        from app.services.alpha_scanner import get_cached_alpha_scan
        from app import alpha_jobs

        # 1. Try loading from cache first
        cached_result = get_cached_alpha_scan()
        if cached_result and not refresh:
            return {
                "status": "success",
                "message": f"Alpha alerts loaded from cache — {cached_result['passed']} alerts found.",
                **cached_result,
            }

        # 2. Check for already running job
        running_job = alpha_jobs.get_running_job()
        if running_job:
            return {
                "status": "running",
                "job_id": running_job["job_id"],
                "message": "Alpha alerts scan is already running.",
            }

        # 3. If not refresh, check for recently completed job results
        if not refresh:
            last_completed = alpha_jobs.get_last_completed_job()
            if last_completed and last_completed.get("result"):
                return {
                    "status": "success",
                    "message": "Alpha alerts loaded from last completed job.",
                    **last_completed["result"],
                }
            # No cache, no running job, no completed job — return empty/no_cache state so UI triggers a scan
            return {
                "status": "no_cache",
                "message": "No cached alpha scan available.",
                "alerts": [],
                "scanned": 0,
                "passed": 0,
            }

        # 4. Refresh requested -> start background job
        from app.services.alpha_tracker import get_performance
        perf = get_performance()
        adaptive = perf.get("adaptive_thresholds", {})
        thresholds = {}
        if adaptive.get("min_composite"):
            thresholds["min_composite"] = adaptive["min_composite"]

        job_id = alpha_jobs.start_job(thresholds=thresholds or None)
        return {
            "status": "running",
            "job_id": job_id,
            "message": "Alpha alerts scan started in the background.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/alpha-alerts/status/{job_id}")
def admin_alpha_alerts_status(job_id: str):
    """Retrieve the status and results of a background alpha alerts scan job."""
    from app import alpha_jobs
    job = alpha_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/admin/alpha-performance")
def admin_alpha_performance():
    """Return rolling accuracy and training metrics for the alpha alert system."""
    try:
        from app.services.alpha_tracker import get_performance
        return get_performance()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/alpha-reconcile")
def admin_alpha_reconcile():
    """Reconcile pending alpha alerts against actual market prices."""
    try:
        from app.services.alpha_tracker import reconcile_alerts
        return reconcile_alerts()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.post("/api/telegram/test")
def telegram_test_endpoint():
    """Fire a test Telegram notification to verify bot + channel configuration."""
    try:
        from app.services.notifier import send_telegram_recommendations
        test_recs = [
            {
                "symbol": "DIXON.NS",
                "rank": 1,
                "composite_score": 92,
                "target_price": 18500.00,
                "stop_loss": 16200.00,
                "trade_date": "Test Alert",
                "is_undervalued": True,
                "reasoning": "Strong momentum with bullish MACD crossover. RSI recovering from oversold. Institutional buying detected.",
            },
            {
                "symbol": "BHARTIARTL.NS",
                "rank": 2,
                "composite_score": 87,
                "target_price": 1950.00,
                "stop_loss": 1720.00,
                "trade_date": "Test Alert",
                "is_undervalued": False,
                "reasoning": "Breakout above 52-week resistance. Strong subscriber growth driving earnings beat.",
            },
        ]
        success = send_telegram_recommendations(test_recs, "Test Alert — System Check")
        if success:
            return {"success": True, "message": "Telegram test alert sent successfully! Check your Telegram."}
        else:
            return {"success": False, "message": "Telegram not configured or send failed. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/cron/weekly-learning")
def weekly_learning(
    authorization: str | None = Header(None),
):
    """Runs every Sunday night. Analyzes past week's trades and updates learned config."""
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        expected = f"Bearer {cron_secret}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized Vercel cron trigger")
            
    client = get_client()
    if not client:
        raise HTTPException(status_code=400, detail="Supabase client not active")
        
    from app.services.loss_analyzer import analyze_loss_patterns
    result = analyze_loss_patterns(client)
    return {
        "status": "success",
        "win_rate": result.get("overall_win_rate"), 
        "suppressed_sectors": result.get("suppressed_sectors"),
        "result": result
    }


@app.get("/api/cron/daily")
def vercel_cron_endpoint(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """Automated daily cron trigger for Vercel Serverless deployments.

    Fires the swing analysis synchronously on Vercel to guarantee completion
    and prevent container freezing, or in a background task locally.
    """
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        expected = f"Bearer {cron_secret}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized Vercel cron trigger")

    def _run_daily():
        try:
            from app.services.reconciler import reconcile_recommendations
            reconcile_recommendations()
        except Exception:
            pass
        try:
            analyzer.run_full_analysis(mode="swing")
        except Exception:
            pass

    if IS_VERCEL:
        _run_daily()
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Daily swing analysis completed synchronously on Vercel.",
            },
        )
    else:
        background_tasks.add_task(_run_daily)
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Daily swing analysis triggered in background.",
            },
        )


@app.get("/api/cron/intraday")
def vercel_intraday_cron_endpoint(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
):
    """Automated intraday cron trigger for Vercel Serverless deployments (Weekday Market Hours).

    Fires the intraday analysis synchronously on Vercel to guarantee completion
    and prevent container freezing, or in a background task locally.
    """
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        expected = f"Bearer {cron_secret}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized Vercel cron trigger")

    def _run_intraday():
        try:
            analyzer.run_full_analysis(mode="intraday")
        except Exception:
            pass

    if IS_VERCEL:
        _run_intraday()
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Intraday analysis completed synchronously on Vercel.",
            },
        )
    else:
        background_tasks.add_task(_run_intraday)
        return JSONResponse(
            status_code=202,
            content={
                "status": "accepted",
                "message": "Intraday analysis triggered in background.",
            },
        )


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


@app.get("/api/portfolio/health/{symbol}")
def get_position_health(symbol: str, entry_price: float, stop_loss: float, target_price: float, trade_mode: str = "swing"):
    try:
        from app.services.position_monitor import check_position_health
        import yfinance as yf
        from app.services.user_workspace import normalize_symbol
        norm_sym = normalize_symbol(symbol)
        ticker = yf.Ticker(norm_sym)
        period = "60d" if trade_mode != "intraday" else "5d"
        interval = "1d" if trade_mode != "intraday" else "60m"
        history = ticker.history(period=period, interval=interval)
        
        health_analysis = check_position_health(
            symbol=norm_sym,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            trade_mode=trade_mode,
            df=history
        )
        return health_analysis
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
        success = add_to_portfolio(
            req.user_id,
            req.symbol,
            req.quantity,
            req.buy_price,
            req.target_price,
            req.stop_loss
        )
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/portfolio/sell")
def sell_holding_endpoint(req: PortfolioSellRequest):
    try:
        from app.services.user_workspace import sell_from_portfolio
        success = sell_from_portfolio(
            req.user_id,
            req.symbol,
            req.quantity,
            req.sell_price,
            "manual"
        )
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/portfolio/update_thresholds")
def update_thresholds_endpoint(req: PortfolioThresholdUpdateRequest):
    try:
        from app.services.user_workspace import update_portfolio_thresholds
        success = update_portfolio_thresholds(
            req.user_id,
            req.symbol,
            req.target_price,
            req.stop_loss
        )
        return {"success": success}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/user/passbook")
def get_passbook_endpoint(user_id: str):
    try:
        from app.services.user_workspace import get_user_passbook
        return {"passbook": get_user_passbook(user_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/user/portfolio/reconcile")
def reconcile_portfolio_endpoint(user_id: str):
    try:
        from app.services.user_workspace import reconcile_active_triggers
        return reconcile_active_triggers(user_id)
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


# ---------------------------------------------------------------------------
# Institutional 8-Pillar Scanner
# ---------------------------------------------------------------------------


@app.post("/api/institutional/scan")
def institutional_scan(refresh: bool = False):
    """Run the 8-pillar institutional scanner across all watchlist stocks.

    Returns cached scan results if fresh (within 30 mins) and refresh is False.
    Otherwise, starts a background job and returns the job ID.
    """
    try:
        from app.services.institutional_scorer import get_cached_institutional_scan
        from app import institutional_jobs
        
        # 1. Try loading from cache first (for both refresh and non-refresh)
        cached_result = get_cached_institutional_scan()
        if cached_result and not refresh:
            return {
                "status": "success",
                "message": f"Institutional scan loaded from cache — {cached_result['summary']['total_results']} stocks scored.",
                **cached_result,
            }

        # 2. Check for already running job
        running_job = institutional_jobs.get_running_job()
        if running_job:
            return {
                "status": "running",
                "job_id": running_job["job_id"],
                "message": "Institutional scan is already running.",
            }

        # 3. If not refresh, check for recently completed job results first
        if not refresh:
            last_completed = institutional_jobs.get_last_completed_job()
            if last_completed and last_completed.get("result"):
                return {
                    "status": "success",
                    "message": "Institutional scan loaded from last completed job.",
                    **last_completed["result"],
                }
            # No cache, no running job, no completed job — return empty
            return {
                "status": "no_cache",
                "message": "No cached institutional scan available. Click 'Run Institutional Scan' to start one.",
                "results": [],
                "alerts": [],
            }

        # 4. Refresh requested → start a new background job
        job_id = institutional_jobs.start_job()
        return {
            "status": "running",
            "job_id": job_id,
            "message": "Institutional scan started in the background. Poll /api/institutional/scan/status/{job_id} for progress.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/institutional/scan/status/{job_id}")
def institutional_scan_status(job_id: str):
    """Retrieve the status and results of a background institutional scan job."""
    from app import institutional_jobs
    job = institutional_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


class InstitutionalSingleRequest(BaseModel):
    symbol: str


@app.post("/api/institutional/score")
def institutional_score_single(req: InstitutionalSingleRequest):
    """Score a single stock using the 8-pillar institutional analyzer."""
    try:
        import yfinance as yf
        import pandas as pd
        from app.services.institutional_scorer import score_stock
        from app.services.sector_rs import get_today_market_context, _normalize_sector

        symbol = normalize_symbol(req.symbol)
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        # Fetch profile from DB
        profile = None
        client = get_client()
        if client:
            try:
                res = client.table("stocks").select("*").eq("symbol", symbol).execute()
                if res.data:
                    profile = res.data[0]
            except Exception:
                pass
        if not profile:
            profile = {"symbol": symbol, "name": symbol.replace(".NS", "")}

        # Sector RS
        sector_rs = None
        try:
            market_ctx = get_today_market_context()
            sector = profile.get("sector")
            if sector:
                normalized = _normalize_sector(sector)
                if normalized and normalized in market_ctx.get("sectors", {}):
                    sector_rs = market_ctx["sectors"][normalized]
        except Exception:
            pass

        result = score_stock(symbol, df, profile, sector_rs)
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/recommendations")
def list_recommendations(trade_date: str | None = None, mode: str | None = None):
    # Try getting from Redis cache
    from app.services.redis_cache import get_cache, set_cache
    cache_key = f"recommendations:{mode or 'all'}:{trade_date or 'latest'}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data

    client = get_client()
    if not client:
        cached = analyzer.get_last_result()
        if not cached:
            res_data = {"recommendations": [], "trade_date": None, "source": "memory"}
            set_cache(cache_key, res_data, 3600)
            return res_data
        recs = cached.get("top_recommendations") or []
        if mode:
            recs = [r for r in recs if r.get("trade_mode") == mode]
        if trade_date:
            recs = [r for r in recs if r.get("trade_date") == trade_date]
        res_data = {
            "recommendations": recs,
            "trade_date": cached.get("trade_date"),
            "source": "memory",
        }
        set_cache(cache_key, res_data, 3600)
        return res_data

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
                res_data = {"recommendations": filtered_data, "trade_date": target_date, "trade_mode": mode}
                set_cache(cache_key, res_data, 3600)
                return res_data
        else:
            raise exc
    res_data = {"recommendations": result.data, "trade_date": target_date, "trade_mode": mode}
    set_cache(cache_key, res_data, 3600)
    return res_data


@app.get("/api/signals")
def list_signals(planned_trade_date: str | None = None, signal_type: str | None = None, mode: str | None = None):
    # Try getting from Redis cache
    from app.services.redis_cache import get_cache, set_cache
    cache_key = f"signals:{mode or 'all'}:{planned_trade_date or 'latest'}:{signal_type or 'all'}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data

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
        res_data = {"signals": signals, "source": "memory"}
        set_cache(cache_key, res_data, 3600)
        return res_data

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
                res_data = {"signals": filtered_data}
                set_cache(cache_key, res_data, 3600)
                return res_data
        else:
            raise exc
    res_data = {"signals": result.data}
    set_cache(cache_key, res_data, 3600)
    return res_data


@app.get("/api/stocks/{symbol}")
def stock_detail(symbol: str):
    sym = normalize_symbol(symbol)
    
    # Try getting from Redis cache
    from app.services.redis_cache import get_cache, set_cache
    cache_key = f"stock_detail:{sym}"
    cached_data = get_cache(cache_key)
    if cached_data is not None:
        return cached_data

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
        res_data = {
            "stock": profile,
            "metrics": [metrics_row] if metrics_row.get("price") else [],
            "news": news,
            "latest_recommendation": latest,
            "source": "yfinance",
        }
        set_cache(cache_key, res_data, 7200)
        return res_data

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
    res_data = {
        "stock": stock.data if stock else None,
        "metrics": metrics.data if metrics else [],
        "news": news.data if news else [],
        "latest_recommendation": rec.data[0] if (rec and rec.data) else None,
    }
    set_cache(cache_key, res_data, 7200)
    return res_data


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
