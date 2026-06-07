"""Sector Relative Strength Engine + Market Breadth Signal.

Enhancement #1: Sector RS vs Nifty 50 — trade with rotation, not against it.
Enhancement #4: Market breadth / risk-environment gate — suppresses all buy
                signals on risk-off days (VIX spike, Nifty crash).

All data sourced from yfinance free tier. No paid APIs.
"""

import functools
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# NSE Sector proxies (yfinance-accessible indices)
# ---------------------------------------------------------------------------

NSE_SECTOR_PROXIES: dict[str, str] = {
    "IT":      "^CNXIT",
    "Bank":    "^NSEBANK",
    "Pharma":  "^CNXPHARMA",
    "Auto":    "^CNXAUTO",
    "FMCG":    "^CNXFMCG",
    "Metal":   "^CNXMETAL",
    "Energy":  "^CNXENERGY",
    "Realty":  "^CNXREALTY",
    "Infra":   "^CNXINFRA",
    "Market":  "^NSEI",      # Nifty 50 benchmark
}

# Canonical sector name mapping — normalises messy sector strings from yfinance profiles
SECTOR_ALIAS: dict[str, str] = {
    "information technology": "IT",
    "technology": "IT",
    "it": "IT",
    "banking": "Bank",
    "bank": "Bank",
    "financial services": "Bank",
    "pharmaceuticals": "Pharma",
    "pharma": "Pharma",
    "healthcare": "Pharma",
    "automobile": "Auto",
    "auto": "Auto",
    "consumer staples": "FMCG",
    "fmcg": "FMCG",
    "metals": "Metal",
    "metal": "Metal",
    "steel": "Metal",
    "energy": "Energy",
    "oil & gas": "Energy",
    "utilities": "Energy",
    "real estate": "Realty",
    "realty": "Realty",
    "infrastructure": "Infra",
    "infra": "Infra",
    "construction": "Infra",
}


def _normalize_sector(raw_sector: str | None) -> str | None:
    """Map raw yfinance/DB sector string to NSE proxy key."""
    if not raw_sector:
        return None
    return SECTOR_ALIAS.get(raw_sector.lower().strip())


def _safe_get_column(df: pd.DataFrame, col_name: str) -> pd.Series:
    """Safely extract a column from a DataFrame, handling MultiIndex columns gracefully."""
    if df.empty:
        return pd.Series(dtype=float)
    if col_name in df.columns:
        res = df[col_name]
        if isinstance(res, pd.DataFrame):
            if not res.empty:
                return res.iloc[:, 0]
            return pd.Series(dtype=float)
        return res
    if isinstance(df.columns, pd.MultiIndex):
        # Try to find the column at the first level
        for col in df.columns:
            if col[0] == col_name:
                res = df[col]
                if isinstance(res, pd.DataFrame):
                    if not res.empty:
                        return res.iloc[:, 0]
                    return pd.Series(dtype=float)
                return res
    return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Enhancement #1 — Sector Relative Strength
# ---------------------------------------------------------------------------


def get_sector_relative_strength(sector: str, period_days: int = 20) -> dict[str, Any]:
    """Measure how strongly a sector performs RELATIVE to Nifty 50.

    RS > 1.05  → Sector outperforming → Green light to trade stocks in this sector
    RS 0.95–1.05 → Neutral → Proceed with caution
    RS < 0.95  → Sector underperforming → Avoid longs in this sector

    Args:
        sector: NSE sector key (e.g. "IT", "Bank") or raw sector string.
        period_days: Lookback window in calendar days.

    Returns dict with rs_score, status, sector_return_pct, market_return_pct, sector_trend.
    """
    # Normalise if caller passes raw profile sector string
    normalized = _normalize_sector(sector) or sector
    sector_proxy = NSE_SECTOR_PROXIES.get(normalized)
    market_proxy = NSE_SECTOR_PROXIES["Market"]

    if not sector_proxy:
        return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown",
                "sector_return_pct": 0.0, "market_return_pct": 0.0}

    end = datetime.today()
    start = end - timedelta(days=period_days + 10)  # buffer for weekends

    try:
        sector_df = yf.download(sector_proxy, start=start, end=end, interval="1d", progress=False)
        market_df = yf.download(market_proxy, start=start, end=end, interval="1d", progress=False)

        if sector_df.empty or market_df.empty:
            return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown",
                    "sector_return_pct": 0.0, "market_return_pct": 0.0}

        sector_close = _safe_get_column(sector_df, "Close").dropna()
        market_close = _safe_get_column(market_df, "Close").dropna()

        if len(sector_close) < 2 or len(market_close) < 2:
            return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown",
                    "sector_return_pct": 0.0, "market_return_pct": 0.0}

        sector_return = float((sector_close.iloc[-1] / sector_close.iloc[0]) - 1)
        market_return = float((market_close.iloc[-1] / market_close.iloc[0]) - 1)

        # RS ratio: sector performance normalised vs market
        denom = 1 + market_return
        rs_score = round((1 + sector_return) / denom if denom != 0 else 1.0, 4)

        # Sector trend: is sector above its own 10-day SMA?
        sma10 = float(sector_close.rolling(10).mean().iloc[-1])
        sector_price = float(sector_close.iloc[-1])
        sector_trend = "up" if sector_price > sma10 else "down"

        if rs_score > 1.05 and sector_trend == "up":
            status = "leading"        # Best sectors to trade
        elif rs_score > 1.00:
            status = "outperforming"  # Acceptable
        elif rs_score > 0.95:
            status = "neutral"        # Caution
        else:
            status = "lagging"        # Avoid longs

        return {
            "rs_score": rs_score,
            "status": status,
            "sector_return_pct": round(sector_return * 100, 2),
            "market_return_pct": round(market_return * 100, 2),
            "sector_trend": sector_trend,
        }

    except Exception:
        return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown",
                "sector_return_pct": 0.0, "market_return_pct": 0.0}


def get_all_sector_rankings() -> list[dict[str, Any]]:
    """Return all NSE sectors ranked by relative strength, best first.

    Run once per morning at scan start — cache the result, not per-stock.
    """
    rankings: list[dict[str, Any]] = []
    for sector_name in NSE_SECTOR_PROXIES:
        if sector_name == "Market":
            continue
        rs = get_sector_relative_strength(sector_name)
        rankings.append({"sector": sector_name, **rs})
    return sorted(rankings, key=lambda x: x["rs_score"], reverse=True)


# ---------------------------------------------------------------------------
# Enhancement #4 — Market Breadth / Risk Environment Gate
# ---------------------------------------------------------------------------


def get_market_breadth_signal() -> dict[str, Any]:
    """Evaluate overall NSE market health — the daily risk gate.

    Uses:
      - Nifty 50 vs its 20-day SMA (above = healthy trend)
      - India VIX (fear gauge — >22 = elevated risk)
      - Nifty 50 daily return (extreme down days signal crash risk)

    Returns:
      environment: "risk_on" | "caution" | "risk_off"

    RULE: risk_off → suppress ALL buy recommendations.
    """
    try:
        nifty = yf.download("^NSEI", period="30d", interval="1d", progress=False)
        vix = yf.download("^INDIAVIX", period="5d", interval="1d", progress=False)

        if nifty.empty:
            return {"environment": "caution", "reason": "Could not fetch Nifty data",
                    "nifty_vs_sma20_pct": 0.0, "vix": 15.0, "nifty_daily_return": 0.0,
                    "reasons": []}

        nifty_close = _safe_get_column(nifty, "Close").dropna()
        nifty_price = float(nifty_close.iloc[-1])
        nifty_sma20 = float(nifty_close.rolling(20).mean().iloc[-1])
        nifty_prev = float(nifty_close.iloc[-2]) if len(nifty_close) > 1 else nifty_price
        nifty_daily_return = ((nifty_price / nifty_prev) - 1) * 100 if nifty_prev else 0.0

        vix_level = 15.0
        if not vix.empty:
            vix_close = _safe_get_column(vix, "Close").dropna()
            if len(vix_close) > 0:
                vix_level = float(vix_close.iloc[-1])

        risk_off_reasons: list[str] = []

        if nifty_price < nifty_sma20 * 0.97:
            risk_off_reasons.append(f"Nifty 3%+ below 20-SMA")

        if vix_level > 22:
            risk_off_reasons.append(f"India VIX={round(vix_level, 1)} — elevated fear")

        if nifty_daily_return < -1.5:
            risk_off_reasons.append(f"Nifty down {round(nifty_daily_return, 2)}% today")

        if len(risk_off_reasons) >= 2:
            environment = "risk_off"
        elif len(risk_off_reasons) == 1 or nifty_price < nifty_sma20 * 0.99:
            # Require at least 1% below SMA20 for caution (was 0% = any amount)
            environment = "caution"
        else:
            environment = "risk_on"

        return {
            "environment": environment,
            "nifty_vs_sma20_pct": round((nifty_price / nifty_sma20 - 1) * 100, 2),
            "vix": round(vix_level, 2),
            "nifty_daily_return": round(nifty_daily_return, 2),
            "reasons": risk_off_reasons,
        }

    except Exception as exc:
        return {"environment": "caution", "reason": str(exc),
                "nifty_vs_sma20_pct": 0.0, "vix": 15.0, "nifty_daily_return": 0.0,
                "reasons": []}


# ---------------------------------------------------------------------------
# Caching Layer — compute once per scan run, not per stock
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def get_cached_market_context(cache_key: str) -> dict[str, Any]:
    """Cache market breadth + all sector rankings keyed by today's date string.

    cache_key = date.today().isoformat() → forces refresh each new trading day.
    Sector data fetched once (11 API calls), not 90 times per scan.
    """
    breadth = get_market_breadth_signal()
    sector_rankings = get_all_sector_rankings()
    return {
        "breadth": breadth,
        "sectors": {s["sector"]: s for s in sector_rankings},
        "sector_rankings": sector_rankings,
    }


def get_today_market_context() -> dict[str, Any]:
    """Convenience wrapper — always returns today's cached market context."""
    today_key = date.today().isoformat()
    return get_cached_market_context(today_key)
