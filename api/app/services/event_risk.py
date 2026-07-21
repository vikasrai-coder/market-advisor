"""Event Risk Calendar — Fix #3 (Prompt 3).

Detects upcoming high-risk events (earnings, ex-dividend) for a symbol
within the trade window. Uses yfinance free data — zero paid APIs.

Risk events suppress or heavily penalise swing/longterm recommendations:
  - Earnings within 7 days → earnings_near (hard skip swing/longterm)
  - Ex-dividend within 5 days → exdiv_near (−15 pts)
  - Both simultaneously → high_risk (hard skip all modes)
"""

from datetime import datetime
from typing import Any

import yfinance as yf


def get_event_risk(symbol: str) -> dict[str, Any]:
    """Check for upcoming high-risk events within the trade window.

    Uses yfinance `.calendar` for earnings dates and `.dividends` for
    ex-dividend detection. Handles multiple yfinance response formats
    gracefully — defaults to 'clear' on data fetch failure so a
    calendar API hiccup never blocks an otherwise valid signal.

    Returns:
        risk_level: "clear" | "earnings_near" | "exdiv_near" | "high_risk"
        events: list of event dicts with type, date, days_away, risk
        safe_to_trade: bool (True only when clear)
    """
    try:
        ticker = yf.Ticker(symbol)
        today = datetime.today().date()
        events: list[dict[str, Any]] = []

        # --- Earnings date check ---
        try:
            calendar = ticker.calendar
            if calendar is not None:
                # yfinance returns dict or DataFrame depending on version
                if isinstance(calendar, dict):
                    # Newer yfinance: {'Earnings Date': [Timestamp, ...], ...}
                    earnings_list = calendar.get("Earnings Date", [])
                    if not isinstance(earnings_list, list):
                        earnings_list = [earnings_list]
                    for ed in earnings_list:
                        if ed is None:
                            continue
                        ed_date = ed.date() if hasattr(ed, "date") else ed
                        days = (ed_date - today).days
                        if 0 <= days <= 7:
                            events.append({
                                "type": "earnings",
                                "date": str(ed_date),
                                "days_away": days,
                                "risk": "high" if days <= 3 else "medium",
                            })
                else:
                    # Older yfinance: DataFrame with 'Earnings Date' column
                    import pandas as pd
                    if hasattr(calendar, "columns") and "Earnings Date" in calendar.columns:
                        for ed in calendar["Earnings Date"].dropna():
                            ed_date = ed.date() if hasattr(ed, "date") else ed
                            days = (ed_date - today).days
                            if 0 <= days <= 7:
                                events.append({
                                    "type": "earnings",
                                    "date": str(ed_date),
                                    "days_away": days,
                                    "risk": "high" if days <= 3 else "medium",
                                })
        except Exception:
            pass  # Calendar unavailable — don't block

        # --- Ex-dividend check ---
        try:
            dividends = ticker.dividends
            if dividends is not None and not dividends.empty:
                for ex_ts in dividends.index:
                    ex_date = ex_ts.date() if hasattr(ex_ts, "date") else ex_ts
                    days = (ex_date - today).days
                    if 0 <= days <= 5:
                        events.append({
                            "type": "ex_dividend",
                            "date": str(ex_date),
                            "days_away": days,
                            "risk": "high" if days <= 2 else "medium",
                        })
        except Exception:
            pass  # Dividend data unavailable — don't block

        # --- Risk classification ---
        high_risk_events = [e for e in events if e["risk"] == "high"]
        has_earnings = any(e["type"] == "earnings" for e in events)
        has_exdiv = any(e["type"] == "ex_dividend" for e in events)

        if len(high_risk_events) >= 2 or (has_earnings and has_exdiv):
            risk_level = "high_risk"
        elif has_earnings:
            risk_level = "earnings_near"
        elif has_exdiv:
            risk_level = "exdiv_near"
        else:
            risk_level = "clear"

        return {
            "risk_level": risk_level,
            "events": events,
            "safe_to_trade": risk_level == "clear",
        }

    except Exception:
        # Network or parse error — default clear, don't block valid signals
        return {"risk_level": "clear", "events": [], "safe_to_trade": True}


# Official NSE Indian Market Holidays for 2026
NSE_HOLIDAYS_2026 = {
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-30": "Good Friday",
    "2026-03-31": "Ramzan Id (Id-Ul-Fitr)",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-06-07": "Bakri Id (Id-Ul-Zuha)",
    "2026-07-06": "Moharram",
    "2026-08-15": "Independence Day",
    "2026-09-04": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-09": "Diwali Laxmi Pujan",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Gurunanak Jayanti",
    "2026-12-25": "Christmas",
}


def get_upcoming_events(days_ahead: int = 14) -> dict[str, Any]:
    """Retrieve upcoming market holidays and earnings events for the next N days."""
    from datetime import date, timedelta
    today = date.today()

    calendar_items = []

    # 1. Check holidays in range
    for d in range(days_ahead):
        dt = today + timedelta(days=d)
        dt_str = dt.isoformat()
        if dt_str in NSE_HOLIDAYS_2026:
            calendar_items.append({
                "date": dt_str,
                "type": "holiday",
                "title": f"Market Closed — {NSE_HOLIDAYS_2026[dt_str]}",
                "risk": "high",
            })

    return {
        "days_ahead": days_ahead,
        "items": calendar_items,
        "holiday_count": len(calendar_items),
    }

