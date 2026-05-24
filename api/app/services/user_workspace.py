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


def _is_valid_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _read_local_cache() -> Dict[str, Any]:
    if not os.path.exists(USER_CACHE_FILE):
        return {"user_watchlists": {}, "user_portfolios": {}}
    try:
        with open(USER_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"user_watchlists": {}, "user_portfolios": {}}


def _write_local_cache(data: Dict[str, Any]) -> None:
    try:
        with open(USER_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.error(f"Failed to write user workspace cache: {exc}")


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

    # Fetch live price metrics for watchlisted symbols
    watchlist_items = []
    for sym in raw_symbols:
        try:
            norm_sym = normalize_symbol(sym)
            ticker = yf.Ticker(norm_sym)
            info = ticker.info or {}

            history = ticker.history(period="1d")
            price = float(history["Close"].iloc[-1]) if not history.empty else 0.0
            prev_close = float(info.get("previousClose") or price)
            change_pct = round(((price - prev_close) / prev_close * 100), 2) if prev_close else 0.0

            watchlist_items.append({
                "symbol": norm_sym,
                "display_symbol": display_symbol(norm_sym),
                "name": info.get("longName") or info.get("shortName") or display_symbol(norm_sym),
                "sector": info.get("sector") or "Unclassified",
                "price": price,
                "change_pct": change_pct,
            })
        except Exception:
            watchlist_items.append({
                "symbol": sym,
                "display_symbol": display_symbol(sym),
                "name": display_symbol(sym),
                "sector": "Unclassified",
                "price": 0.0,
                "change_pct": 0.0,
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

    total_investment = 0.0
    total_current_value = 0.0
    holdings_items = []

    for item in holdings:
        sym = item.get("symbol")
        qty = float(item.get("shares_quantity") or 0.0)
        buy_price = float(item.get("buy_price") or 0.0)
        if not sym or qty <= 0:
            continue

        try:
            norm_sym = normalize_symbol(sym)
            ticker = yf.Ticker(norm_sym)
            history = ticker.history(period="1d")
            current_price = float(history["Close"].iloc[-1]) if not history.empty else buy_price

            investment = round(qty * buy_price, 2)
            current_value = round(qty * current_price, 2)
            profit_loss = round(current_value - investment, 2)
            profit_loss_pct = round(((current_price - buy_price) / buy_price * 100), 2) if buy_price > 0 else 0.0

            total_investment += investment
            total_current_value += current_value

            holdings_items.append({
                "symbol": norm_sym,
                "display_symbol": display_symbol(norm_sym),
                "name": ticker.info.get("longName") or ticker.info.get("shortName") or display_symbol(norm_sym),
                "shares_quantity": qty,
                "buy_price": buy_price,
                "current_price": current_price,
                "investment": investment,
                "current_value": current_value,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
            })
        except Exception:
            investment = round(qty * buy_price, 2)
            holdings_items.append({
                "symbol": sym,
                "display_symbol": display_symbol(sym),
                "name": display_symbol(sym),
                "shares_quantity": qty,
                "buy_price": buy_price,
                "current_price": buy_price,
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


def add_to_portfolio(user_id: str, symbol: str, quantity: float, buy_price: float) -> bool:
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
                }).eq("id", existing.data["id"]).execute()
            else:
                client.table("user_portfolios").insert({
                    "user_id": user_id,
                    "symbol": norm_sym,
                    "shares_quantity": quantity,
                    "buy_price": buy_price,
                }).execute()
            return True
        except Exception as exc:
            logger.error(f"Failed to add portfolio holding on Supabase: {exc}")

    # Local cache fallback
    cache = _read_local_cache()
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
            found = True
            break

    if not found:
        cache["user_portfolios"][user_id].append({
            "symbol": norm_sym,
            "shares_quantity": quantity,
            "buy_price": buy_price,
        })

    _write_local_cache(cache)
    return True


def sell_from_portfolio(user_id: str, symbol: str, quantity: float) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()

    use_supabase = client and _is_valid_uuid(user_id)

    if use_supabase:
        try:
            existing = client.table("user_portfolios").select("*").eq("user_id", user_id).eq("symbol", norm_sym).maybe_single().execute()
            if existing and existing.data:
                old_qty = float(existing.data["shares_quantity"])
                if quantity >= old_qty:
                    client.table("user_portfolios").delete().eq("id", existing.data["id"]).execute()
                else:
                    new_qty = old_qty - quantity
                    client.table("user_portfolios").update({
                        "shares_quantity": new_qty,
                    }).eq("id", existing.data["id"]).execute()
                return True
        except Exception as exc:
            logger.error(f"Failed to sell portfolio holding on Supabase: {exc}")

    # Local cache fallback
    cache = _read_local_cache()
    if user_id in cache["user_portfolios"]:
        for item in list(cache["user_portfolios"][user_id]):
            if item["symbol"] == norm_sym:
                old_qty = float(item["shares_quantity"])
                if quantity >= old_qty:
                    cache["user_portfolios"][user_id].remove(item)
                else:
                    item["shares_quantity"] = old_qty - quantity
                _write_local_cache(cache)
                break
    return True
