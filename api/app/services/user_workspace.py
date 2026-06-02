"""Service to manage user watchlists and share holdings portfolios with both Supabase and memory fallbacks."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import yfinance as yf

from app.services.supabase_store import get_client
from app.symbols import normalize_symbol, display_symbol

logger = logging.getLogger(__name__)

USER_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_workspace_cache.json")

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_IN_MEMORY_USER_CACHE: Dict[str, Any] = {}


def _is_valid_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _read_local_cache() -> Dict[str, Any]:
    global _IN_MEMORY_USER_CACHE
    if _IN_MEMORY_USER_CACHE:
        return _IN_MEMORY_USER_CACHE

    # Try /tmp fallback cache file first (Vercel runtime environment)
    tmp_file = "/tmp/user_workspace_cache.json"
    if os.path.exists(tmp_file):
        try:
            with open(tmp_file, "r") as f:
                data = json.load(f)
                _IN_MEMORY_USER_CACHE = data
                return data
        except Exception:
            pass

    if not os.path.exists(USER_CACHE_FILE):
        return {"user_watchlists": {}, "user_portfolios": {}, "user_passbook": {}}
    try:
        with open(USER_CACHE_FILE, "r") as f:
            data = json.load(f)
            _IN_MEMORY_USER_CACHE = data
            return data
    except Exception:
        return {"user_watchlists": {}, "user_portfolios": {}, "user_passbook": {}}


def _write_local_cache(data: Dict[str, Any]) -> None:
    global _IN_MEMORY_USER_CACHE
    _IN_MEMORY_USER_CACHE = data
    # 1. Try writing to original settings file
    try:
        with open(USER_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as main_exc:
        # 2. Try writing to /tmp folder in read-only environment
        try:
            tmp_file = "/tmp/user_workspace_cache.json"
            with open(tmp_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as tmp_exc:
            logger.error(f"Failed to write user workspace cache fallback to /tmp: {tmp_exc} | Local write failed: {main_exc}")


def _split_symbol(symbol: str) -> Tuple[str, str]:
    """Return (bare_symbol, exchange) e.g. ('KAYNES', 'NSE') or ('AAPL', 'US')."""
    s = symbol.strip().upper()
    if s.endswith(".NS"):
        return s.replace(".NS", ""), "NSE"
    if s.endswith(".BO"):
        return s.replace(".BO", ""), "BSE"
    return s, "US"


def _fetch_stock_profile(norm_sym: str) -> Dict[str, Any]:
    """Fetch yfinance data and return a dict of valid stocks-table columns."""
    profile: Dict[str, Any] = {"symbol": norm_sym}
    try:
        ticker = yf.Ticker(norm_sym)
        info = ticker.info or {}
        if info.get("longName") or info.get("shortName"):
            profile["name"] = info.get("longName") or info.get("shortName") or norm_sym
        if info.get("sector"):
            profile["sector"] = info["sector"]
        if info.get("industry"):
            profile["industry"] = info["industry"]
        if info.get("marketCap"):
            profile["market_cap"] = info["marketCap"]
        if info.get("trailingPE"):
            profile["pe_ratio"] = info["trailingPE"]
        if info.get("dividendYield"):
            profile["dividend_yield"] = info["dividendYield"]
        if info.get("fiftyTwoWeekHigh"):
            profile["fifty_two_week_high"] = info["fiftyTwoWeekHigh"]
        if info.get("fiftyTwoWeekLow"):
            profile["fifty_two_week_low"] = info["fiftyTwoWeekLow"]
        profile["exchange"] = "NSE" if norm_sym.endswith(".NS") else ("BSE" if norm_sym.endswith(".BO") else "US")
        profile["currency"] = info.get("currency", "INR" if ".NS" in norm_sym else "USD")
    except Exception:
        pass
    return profile


# ---------------------------------------------------------------------------
# Watchlist Services
# ---------------------------------------------------------------------------

def get_user_watchlist(user_id: str) -> List[Dict[str, Any]]:
    import pandas as pd
    client = get_client()
    raw_symbols: List[str] = []

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            res = client.table("user_watchlists").select("symbol").eq("user_id", user_id).execute()
            for row in res.data:
                raw_symbols.append(row["symbol"])
        except Exception as exc:
            logger.error(f"Failed to fetch user watchlist from Supabase: {exc}")
            cache = _read_local_cache()
            raw_symbols = cache.get("user_watchlists", {}).get(user_id, [])
    else:
        cache = _read_local_cache()
        raw_symbols = cache.get("user_watchlists", {}).get(user_id, [])

    if not raw_symbols:
        return []

    symbols_list = [normalize_symbol(sym) for sym in raw_symbols]

    # 1. Bulk fetch stock profiles from DB to avoid slow sequential ticker.info calls
    db_profiles = {}
    if client:
        try:
            res = client.table("stocks").select("*").in_("symbol", symbols_list).execute()
            for row in res.data:
                db_profiles[row["symbol"]] = row
        except Exception as exc:
            logger.error(f"Error bulk fetching stock profiles: {exc}")

    # 2. Bulk download price history (5d period is enough to get last close and previous close)
    bulk_history = {}
    try:
        tickers_str = " ".join(symbols_list)
        df = yf.download(tickers_str, period="5d", group_by="ticker", progress=False, threads=True)
        for sym in symbols_list:
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    if sym in df.columns.get_level_values(0):
                        sym_df = df[sym].copy().dropna(how="all")
                        if not sym_df.empty:
                            bulk_history[sym] = sym_df
                else:
                    sym_df = df.copy().dropna(how="all")
                    if not sym_df.empty:
                        bulk_history[sym] = sym_df
            except Exception:
                pass
    except Exception as exc:
        logger.error(f"Failed to bulk download history for watchlist: {exc}")

    # Assemble items
    watchlist_items = []
    for sym in symbols_list:
        profile = db_profiles.get(sym) or {}
        name = profile.get("name") or display_symbol(sym)
        sector = profile.get("sector") or "Unclassified"

        history = bulk_history.get(sym)
        price = 0.0
        change_pct = 0.0

        if history is not None and not history.empty:
            try:
                if len(history) >= 2:
                    price = float(history["Close"].iloc[-1])
                    prev_close = float(history["Close"].iloc[-2])
                    change_pct = round(((price - prev_close) / prev_close * 100), 2) if prev_close else 0.0
                else:
                    price = float(history["Close"].iloc[-1])
            except Exception:
                pass

        watchlist_items.append({
            "symbol": sym,
            "display_symbol": display_symbol(sym),
            "name": name,
            "sector": sector,
            "price": price,
            "change_pct": change_pct,
        })
    return watchlist_items


def add_to_watchlist(user_id: str, symbol: str) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()

    # Enrich stocks table with live yfinance data
    stock_profile = _fetch_stock_profile(norm_sym)

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            # Upsert stock info (schema-valid columns only)
            client.table("stocks").upsert(stock_profile).execute()
            # user_watchlists stores normalized symbol
            client.table("user_watchlists").upsert({
                "user_id": user_id,
                "symbol": norm_sym,
            }).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to add to user watchlist on Supabase: {exc}")
            raise exc

    # Local cache fallback (always save full .NS symbol)
    cache = _read_local_cache()
    if user_id not in cache["user_watchlists"]:
        cache["user_watchlists"][user_id] = []
    if norm_sym not in cache["user_watchlists"][user_id]:
        cache["user_watchlists"][user_id].append(norm_sym)
        _write_local_cache(cache)
    return True


def remove_from_watchlist(user_id: str, symbol: str) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            client.table("user_watchlists").delete().eq("user_id", user_id).eq("symbol", norm_sym).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to remove from user watchlist on Supabase: {exc}")
            raise exc

    # Local cache fallback
    cache = _read_local_cache()
    if user_id in cache["user_watchlists"]:
        wl = cache["user_watchlists"][user_id]
        to_remove = [s for s in wl if s == norm_sym]
        for s in to_remove:
            wl.remove(s)
        _write_local_cache(cache)
    return True


# ---------------------------------------------------------------------------
# Portfolio Holdings Services
# ---------------------------------------------------------------------------

def get_user_portfolio(user_id: str) -> Dict[str, Any]:
    import pandas as pd
    client = get_client()
    holdings = []

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            res = client.table("user_portfolios").select("*").eq("user_id", user_id).execute()
            holdings = res.data
        except Exception as exc:
            logger.error(f"Failed to fetch user portfolio from Supabase: {exc}")
            cache = _read_local_cache()
            holdings = cache.get("user_portfolios", {}).get(user_id, [])
    else:
        cache = _read_local_cache()
        holdings = cache.get("user_portfolios", {}).get(user_id, [])

    if not holdings:
        return {
            "summary": {
                "total_investment": 0.0,
                "total_current_value": 0.0,
                "total_profit_loss": 0.0,
                "total_profit_loss_pct": 0.0,
            },
            "holdings": [],
        }

    symbols_list = [normalize_symbol(item["symbol"]) for item in holdings if item.get("symbol")]

    # 1. Bulk fetch stock profiles from DB to avoid slow sequential ticker.info calls
    db_profiles = {}
    if client and symbols_list:
        try:
            res = client.table("stocks").select("*").in_("symbol", symbols_list).execute()
            for row in res.data:
                db_profiles[row["symbol"]] = row
        except Exception as exc:
            logger.error(f"Error bulk fetching stock profiles: {exc}")

    # 2. Bulk download price histories (60d) in a single request
    bulk_history = {}
    if symbols_list:
        try:
            tickers_str = " ".join(symbols_list)
            df = yf.download(tickers_str, period="60d", group_by="ticker", progress=False, threads=True)
            for sym in symbols_list:
                try:
                    if isinstance(df.columns, pd.MultiIndex):
                        if sym in df.columns.get_level_values(0):
                            sym_df = df[sym].copy().dropna(how="all")
                            if not sym_df.empty:
                                bulk_history[sym] = sym_df
                    else:
                        sym_df = df.copy().dropna(how="all")
                        if not sym_df.empty:
                            bulk_history[sym] = sym_df
                except Exception:
                    pass
        except Exception as exc:
            logger.error(f"Failed to bulk download history for portfolio: {exc}")

    total_investment = 0.0
    total_current_value = 0.0
    holdings_items = []

    for item in holdings:
        sym = item.get("symbol")
        qty = float(item.get("shares_quantity") or 0.0)
        buy_price = float(item.get("buy_price") or 0.0)
        target_price = float(item.get("target_price") or 0.0) if item.get("target_price") else None
        stop_loss = float(item.get("stop_loss") or 0.0) if item.get("stop_loss") else None

        if not sym or qty <= 0:
            continue

        norm_sym = normalize_symbol(sym)
        profile = db_profiles.get(norm_sym) or {}
        name = profile.get("name") or display_symbol(norm_sym)

        history = bulk_history.get(norm_sym)
        current_price = buy_price
        if history is not None and not history.empty:
            try:
                current_price = float(history["Close"].iloc[-1])
            except Exception:
                pass

        try:
            investment = round(qty * buy_price, 2)
            current_value = round(qty * current_price, 2)
            profit_loss = round(current_value - investment, 2)
            profit_loss_pct = round(((current_price - buy_price) / buy_price * 100), 2) if buy_price > 0 else 0.0

            total_investment += investment
            total_current_value += current_value

            # Position health monitoring
            health_analysis = None
            if history is not None and not history.empty:
                try:
                    from app.services.position_monitor import check_position_health
                    health_analysis = check_position_health(
                        symbol=norm_sym,
                        entry_price=buy_price,
                        stop_loss=stop_loss if stop_loss else (buy_price * 0.95),
                        target_price=target_price if target_price else (buy_price * 1.15),
                        trade_mode=item.get("trade_mode", "swing"),
                        df=history
                    )
                except Exception as health_exc:
                    logger.error(f"Failed to check health for {norm_sym}: {health_exc}")

            holdings_items.append({
                "symbol": norm_sym,
                "display_symbol": display_symbol(norm_sym),
                "name": name,
                "shares_quantity": qty,
                "buy_price": buy_price,
                "current_price": current_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "investment": investment,
                "current_value": current_value,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "health_analysis": health_analysis,
            })
        except Exception:
            investment = round(qty * buy_price, 2)
            holdings_items.append({
                "symbol": norm_sym,
                "display_symbol": display_symbol(norm_sym),
                "name": name,
                "shares_quantity": qty,
                "buy_price": buy_price,
                "current_price": buy_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "investment": investment,
                "current_value": investment,
                "profit_loss": 0.0,
                "profit_loss_pct": 0.0,
            })

    total_profit_loss = round(total_current_value - total_investment, 2)
    total_profit_loss_pct = round((total_profit_loss / total_investment * 100), 2) if total_investment > 0 else 0.0

    return {
        "summary": {
            "total_investment": total_investment,
            "total_current_value": total_current_value,
            "total_profit_loss": total_profit_loss,
            "total_profit_loss_pct": total_profit_loss_pct,
        },
        "holdings": holdings_items,
    }


def add_to_portfolio(
    user_id: str,
    symbol: str,
    quantity: float,
    buy_price: float,
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None
) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()

    # Enrich stocks table with yfinance data
    stock_profile = _fetch_stock_profile(norm_sym)

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            # Ensure stock exists in stocks table (valid columns only)
            client.table("stocks").upsert(stock_profile).execute()

            # Check if holding already exists
            existing = client.table("user_portfolios").select("*").eq("user_id", user_id).eq("symbol", norm_sym).maybe_single().execute()
            if existing and existing.data:
                old_qty = float(existing.data["shares_quantity"])
                old_price = float(existing.data["buy_price"])
                new_qty = old_qty + quantity
                new_price = round(((old_qty * old_price) + (quantity * buy_price)) / new_qty, 2)
                client.table("user_portfolios").update({
                    "shares_quantity": new_qty,
                    "buy_price": new_price,
                    "target_price": target_price if target_price else existing.data.get("target_price"),
                    "stop_loss": stop_loss if stop_loss else existing.data.get("stop_loss"),
                }).eq("id", existing.data["id"]).execute()
            else:
                client.table("user_portfolios").insert({
                    "user_id": user_id,
                    "symbol": norm_sym,
                    "shares_quantity": quantity,
                    "buy_price": buy_price,
                    "target_price": target_price,
                    "stop_loss": stop_loss,
                }).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to add portfolio holding on Supabase: {exc}")

    # Local cache fallback
    cache = _read_local_cache()
    if "user_portfolios" not in cache:
        cache["user_portfolios"] = {}
    if user_id not in cache["user_portfolios"]:
        cache["user_portfolios"][user_id] = []

    found = False
    for item in cache["user_portfolios"][user_id]:
        if item["symbol"] == norm_sym:
            old_qty = float(item["shares_quantity"])
            old_price = float(item["buy_price"])
            new_qty = old_qty + quantity
            new_price = round(((old_qty * old_price) + (quantity * buy_price)) / new_qty, 2)
            item["shares_quantity"] = new_qty
            item["buy_price"] = new_price
            if target_price:
                item["target_price"] = target_price
            if stop_loss:
                item["stop_loss"] = stop_loss
            found = True
            break

    if not found:
        cache["user_portfolios"][user_id].append({
            "symbol": norm_sym,
            "shares_quantity": quantity,
            "buy_price": buy_price,
            "target_price": target_price,
            "stop_loss": stop_loss,
        })

    _write_local_cache(cache)
    return True


def sell_from_portfolio(
    user_id: str,
    symbol: str,
    quantity: float,
    sell_price: Optional[float] = None,
    execution_type: str = "manual"
) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()

    use_supabase = client and _is_valid_uuid(user_id)
    
    # 1. Resolve actual sell price
    actual_sell_price = 0.0
    if sell_price is not None:
        actual_sell_price = sell_price
    else:
        try:
            ticker = yf.Ticker(norm_sym)
            history = ticker.history(period="1d")
            actual_sell_price = float(history["Close"].iloc[-1]) if not history.empty else 0.0
        except Exception:
            actual_sell_price = 0.0

    buy_price = 0.0
    shares_sold = 0.0
    holding_resolved = False

    # 2. Retrieve existing holding detail
    if use_supabase:
        try:
            existing = client.table("user_portfolios").select("*").eq("user_id", user_id).eq("symbol", norm_sym).maybe_single().execute()
            if existing and existing.data:
                buy_price = float(existing.data["buy_price"])
                old_qty = float(existing.data["shares_quantity"])
                shares_sold = min(quantity, old_qty)
                
                # Perform the active holdings subtraction / deletion
                if shares_sold >= old_qty:
                    client.table("user_portfolios").delete().eq("id", existing.data["id"]).execute()
                else:
                    client.table("user_portfolios").update({
                        "shares_quantity": old_qty - shares_sold,
                    }).eq("id", existing.data["id"]).execute()
                holding_resolved = True
        except Exception as exc:
            logger.error(f"Failed to fetch/delete portfolio holding on Supabase: {exc}")

    if not holding_resolved:
        # Resolve via local cache fallback
        cache = _read_local_cache()
        if user_id in cache["user_portfolios"]:
            for item in list(cache["user_portfolios"][user_id]):
                if item["symbol"] == norm_sym:
                    buy_price = float(item["buy_price"])
                    old_qty = float(item["shares_quantity"])
                    shares_sold = min(quantity, old_qty)
                    
                    if shares_sold >= old_qty:
                        cache["user_portfolios"][user_id].remove(item)
                    else:
                        item["shares_quantity"] = old_qty - shares_sold
                    _write_local_cache(cache)
                    holding_resolved = True
                    break

    if not holding_resolved or shares_sold <= 0:
        return False

    # 3. Calculate profit/loss
    investment = shares_sold * buy_price
    realized_value = shares_sold * actual_sell_price
    profit_loss = round(realized_value - investment, 2)
    profit_loss_pct = round(((actual_sell_price - buy_price) / buy_price * 100), 2) if buy_price > 0 else 0.0

    # 4. Insert into Passbook (History)
    if use_supabase:
        try:
            client.table("user_passbook").insert({
                "user_id": user_id,
                "symbol": norm_sym,
                "shares_quantity": shares_sold,
                "buy_price": buy_price,
                "sell_price": actual_sell_price,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "execution_type": execution_type,
            }).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to record completed trade on Supabase passbook: {exc}")

    # Local cache fallback for Passbook
    cache = _read_local_cache()
    if "user_passbook" not in cache:
        cache["user_passbook"] = {}
    if user_id not in cache["user_passbook"]:
        cache["user_passbook"][user_id] = []

    import datetime
    cache["user_passbook"][user_id].append({
        "symbol": norm_sym,
        "shares_quantity": shares_sold,
        "buy_price": buy_price,
        "sell_price": actual_sell_price,
        "profit_loss": profit_loss,
        "profit_loss_pct": profit_loss_pct,
        "execution_type": execution_type,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    })
    _write_local_cache(cache)
    return True


def get_user_passbook(user_id: str) -> List[Dict[str, Any]]:
    client = get_client()
    use_supabase = client and _is_valid_uuid(user_id)
    records = []

    if use_supabase:
        try:
            res = client.table("user_passbook").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            records = res.data
        except Exception as exc:
            logger.error(f"Failed to fetch user passbook from Supabase: {exc}")
            cache = _read_local_cache()
            records = cache.get("user_passbook", {}).get(user_id, [])
    else:
        cache = _read_local_cache()
        records = cache.get("user_passbook", {}).get(user_id, [])

    # Format output items cleanly
    formatted = []
    for item in records:
        sym = item.get("symbol")
        formatted.append({
            "id": item.get("id"),
            "symbol": sym,
            "display_symbol": display_symbol(sym) if sym else "",
            "shares_quantity": float(item.get("shares_quantity") or 0.0),
            "buy_price": float(item.get("buy_price") or 0.0),
            "sell_price": float(item.get("sell_price") or 0.0),
            "profit_loss": float(item.get("profit_loss") or 0.0),
            "profit_loss_pct": float(item.get("profit_loss_pct") or 0.0),
            "execution_type": item.get("execution_type", "manual"),
            "created_at": item.get("created_at"),
        })
    # Sort locally if retrieved from fallback cache
    if not use_supabase:
        formatted.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return formatted


def reconcile_active_triggers(user_id: str) -> Dict[str, Any]:
    """Fetch live stock prices and automatically execute active stop-loss/target triggers."""
    portfolio = get_user_portfolio(user_id)
    holdings = portfolio.get("holdings", [])
    triggered = []

    for item in holdings:
        sym = item["symbol"]
        qty = item["shares_quantity"]
        current_price = item["current_price"]
        target_price = item.get("target_price")
        stop_loss = item.get("stop_loss")

        # Check Target trigger
        if target_price and target_price > 0 and current_price >= target_price:
            success = sell_from_portfolio(
                user_id=user_id,
                symbol=sym,
                quantity=qty,
                sell_price=target_price,
                execution_type="target_trigger"
            )
            if success:
                triggered.append({
                    "symbol": sym,
                    "display_symbol": item["display_symbol"],
                    "qty": qty,
                    "type": "target_trigger",
                    "trigger_price": target_price,
                    "profit_loss": round((target_price - item["buy_price"]) * qty, 2),
                })
            continue

        # Check Stop Loss trigger
        if stop_loss and stop_loss > 0 and current_price <= stop_loss:
            success = sell_from_portfolio(
                user_id=user_id,
                symbol=sym,
                quantity=qty,
                sell_price=stop_loss,
                execution_type="stop_loss_trigger"
            )
            if success:
                triggered.append({
                    "symbol": sym,
                    "display_symbol": item["display_symbol"],
                    "qty": qty,
                    "type": "stop_loss_trigger",
                    "trigger_price": stop_loss,
                    "profit_loss": round((stop_loss - item["buy_price"]) * qty, 2),
                })

    return {
        "success": True,
        "reconciled_count": len(holdings),
        "triggered_count": len(triggered),
        "triggered": triggered,
    }


def update_portfolio_thresholds(
    user_id: str,
    symbol: str,
    target_price: Optional[float] = None,
    stop_loss: Optional[float] = None
) -> bool:
    """Update target price and stop loss thresholds for an active portfolio holding."""
    norm_sym = normalize_symbol(symbol)
    client = get_client()
    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            client.table("user_portfolios").update({
                "target_price": target_price,
                "stop_loss": stop_loss,
            }).eq("user_id", user_id).eq("symbol", norm_sym).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to update portfolio thresholds on Supabase: {exc}")
            raise exc

    # Local cache fallback
    cache = _read_local_cache()
    if "user_portfolios" in cache and user_id in cache["user_portfolios"]:
        for item in cache["user_portfolios"][user_id]:
            if item["symbol"] == norm_sym:
                item["target_price"] = target_price
                item["stop_loss"] = stop_loss
                break
        _write_local_cache(cache)
        return True
    return False


