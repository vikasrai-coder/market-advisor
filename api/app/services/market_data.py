from typing import Any

import yfinance as yf

from app.config import settings
from app.symbols import display_symbol, normalize_symbol
from app.watchlists import get_cap_segment


def fetch_stock_profile(symbol: str) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    exchange = info.get("exchange") or ("NSE" if symbol.endswith(".NS") else "BSE" if symbol.endswith(".BO") else "IN")
    currency = info.get("currency") or "INR"
    return {
        "symbol": symbol,
        "display_symbol": display_symbol(symbol),
        "name": info.get("longName") or info.get("shortName") or display_symbol(symbol),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": exchange,
        "currency": currency,
        "market": settings.market,
        "cap_segment": get_cap_segment(symbol),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }


def fetch_price_history(symbol: str, period: str = "6mo") -> Any:
    symbol = normalize_symbol(symbol)
    history = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if history.empty and symbol.endswith(".NS"):
        # Fallback: some tickers resolve better on BSE
        alt = symbol.replace(".NS", ".BO")
        history = yf.Ticker(alt).history(period=period, auto_adjust=True)
    return history


def fetch_news(symbol: str, limit: int = 8) -> list[dict[str, Any]]:
    symbol = normalize_symbol(symbol)
    ticker = yf.Ticker(symbol)
    articles: list[dict[str, Any]] = []
    for item in (ticker.news or [])[:limit]:
        articles.append(
            {
                "symbol": symbol,
                "title": item.get("title", ""),
                "summary": (item.get("summary") or item.get("description") or "")[:2000],
                "url": item.get("link") or item.get("url"),
                "source": item.get("publisher") or item.get("source"),
                "published_at": _ts(item.get("providerPublishTime") or item.get("published")),
            }
        )
    return articles


def _ts(value: Any) -> str | None:
    if value is None:
        return None
    try:
        from datetime import datetime

        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(value).isoformat()
    except (ValueError, OSError):
        pass
    return None


def get_watchlist() -> list[str]:
    return [normalize_symbol(s) for s in settings.watchlist]
