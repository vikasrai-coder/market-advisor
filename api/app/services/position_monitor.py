"""Position Health Monitor — Fix #6 (Prompt 3).

Monitors open positions and fires early exit warnings when the technical
structure of a trade is deteriorating — BEFORE the stop-loss is hit.

5 warning triggers:
  1. Regime shifted to downtrend since entry
  2. Smart money shifted to distribution
  3. Price broke EMA8 on high volume (momentum death)
  4. Bearish RSI divergence (price high but RSI lower)
  5. High-strength bearish candlestick pattern appeared
  + Profit protection: trailing floor breached when >60% of target gained

Does NOT close trades automatically — returns warnings and a recommended
action string for the frontend/notifier to surface to the user.
"""

from typing import Any

import pandas as pd


def check_position_health(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    trade_mode: str,
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Check if an open trade is still healthy or showing exit signals.

    Args:
        symbol: NSE ticker (e.g. "RELIANCE.NS")
        entry_price: Price at which the trade was entered
        stop_loss: Original stop-loss level
        target_price: Original target price
        trade_mode: "intraday" | "swing" | "longterm"
        df: Price/volume DataFrame (same format as technicals functions expect)

    Returns:
        health: "healthy" | "caution" | "exit_now"
        warnings: list of warning dicts with signal, severity, message
        current_price: latest close
        current_pnl_pct: P&L% from entry
        action: human-readable recommended action string
    """
    from app.services.technicals import (
        get_market_regime,
        get_smart_money_signals,
        get_candlestick_patterns,
        compute_rsi,
    )

    if df is None or df.empty or "Close" not in df.columns:
        return {
            "health": "healthy",
            "warnings": [],
            "current_price": entry_price,
            "current_pnl_pct": 0.0,
            "action": "HOLD — insufficient data to evaluate",
        }

    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df.columns else pd.Series(dtype=float)
    current_price = float(close.iloc[-1])
    warnings: list[dict[str, Any]] = []

    # 1. Regime check
    try:
        regime = get_market_regime(df)
        if regime.get("regime") == "downtrend":
            warnings.append({
                "signal": "regime_broken",
                "severity": "high",
                "message": "Stock regime shifted to downtrend since entry",
            })
        elif regime.get("regime") == "sideways" and trade_mode == "intraday":
            warnings.append({
                "signal": "momentum_lost",
                "severity": "medium",
                "message": "Intraday momentum faded — trend went sideways",
            })
    except Exception:
        pass

    # 2. Smart money distribution
    try:
        sm = get_smart_money_signals(df)
        if sm.get("signal") == "distribution":
            warnings.append({
                "signal": "distribution_detected",
                "severity": "high",
                "message": f"Smart money distribution: {sm.get('reason', 'OBV/CMF negative')}",
            })
    except Exception:
        pass

    # 3. EMA8 breakdown on high volume
    try:
        ema8 = float(close.ewm(span=8, adjust=False).mean().iloc[-1])
        if not volume.empty:
            avg_vol = float(volume.rolling(20).mean().iloc[-1])
            last_vol = float(volume.iloc[-1])
            if current_price < ema8 and avg_vol > 0 and last_vol > avg_vol * 1.5:
                warnings.append({
                    "signal": "ema8_breakdown",
                    "severity": "high",
                    "message": "Price broke EMA8 on high volume — momentum structure broken",
                })
    except Exception:
        pass

    # 4. RSI divergence — price near high but RSI making lower highs
    try:
        rsi_series = compute_rsi(close, 14)
        if len(rsi_series) >= 12:
            current_rsi = float(rsi_series.iloc[-1])
            prev_rsi_high = float(rsi_series.rolling(10).max().iloc[-2])
            price_near_high = current_price >= float(close.rolling(10).max().iloc[-2]) * 0.98
            rsi_lower = current_rsi < prev_rsi_high - 5
            if price_near_high and rsi_lower:
                warnings.append({
                    "signal": "rsi_divergence",
                    "severity": "medium",
                    "message": (
                        f"Bearish RSI divergence — price near high but RSI "
                        f"{round(current_rsi, 1)} vs prev high {round(prev_rsi_high, 1)}"
                    ),
                })
    except Exception:
        pass

    # 5. High-strength bearish candlestick pattern
    try:
        candles = get_candlestick_patterns(df)
        if candles.get("bearish_count", 0) > 0:
            bearish_pats = [p for p in candles.get("patterns", []) if "bearish" in p.get("type", "")]
            if any(p.get("strength") == "high" for p in bearish_pats):
                name = bearish_pats[0]["name"] if bearish_pats else "bearish pattern"
                warnings.append({
                    "signal": "bearish_candle",
                    "severity": "medium",
                    "message": f"{name} appeared — potential reversal forming",
                })
    except Exception:
        pass

    # 6. Profit protection — trailing floor when >60% of target gained
    try:
        if target_price > entry_price:
            current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
            max_gain_pct = ((target_price - entry_price) / entry_price) * 100
            if current_pnl_pct > max_gain_pct * 0.6:
                trailing_floor = entry_price + (current_price - entry_price) * 0.5
                if current_price < trailing_floor:
                    warnings.append({
                        "signal": "profit_protection",
                        "severity": "high",
                        "message": (
                            f"Giving back profits — trailing floor ₹{round(trailing_floor, 2)} "
                            f"breached. Lock in gains."
                        ),
                    })
        else:
            current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
    except Exception:
        current_pnl_pct = 0.0

    # 7. Supertrend reversal — trend structure broken (institutional exit trigger)
    try:
        from app.services.technicals import compute_supertrend, compute_ema_alignment
        st = compute_supertrend(df)
        if st.get("trend") == "bearish" and st.get("flipped"):
            ema = compute_ema_alignment(close)
            if ema.get("ema20") and current_price < ema["ema20"]:
                warnings.append({
                    "signal": "supertrend_reversal",
                    "severity": "high",
                    "message": (
                        f"Supertrend FLIPPED bearish at ₹{st['supertrend_value']:.2f} "
                        f"+ price below EMA20 (₹{ema['ema20']:.2f}) — trend structure broken"
                    ),
                })
                # Fire Telegram alert
                try:
                    from app.services.notifier import send_trend_reversal_exit_alert
                    send_trend_reversal_exit_alert(symbol, current_price, {
                        "supertrend_value": st["supertrend_value"],
                        "ema20": ema["ema20"],
                    })
                except Exception:
                    pass
    except Exception:
        pass

    # 8. Momentum collapse — all oscillators bearish simultaneously
    try:
        from app.services.technicals import compute_stochastic_rsi
        rsi_series = compute_rsi(close, 14)
        current_rsi = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else 50
        stoch = compute_stochastic_rsi(close)
        stoch_k = stoch.get("stoch_k", 50)

        # MACD histogram
        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = float(macd_line.iloc[-1] - macd_signal.iloc[-1])
        prev_macd_hist = float(macd_line.iloc[-2] - macd_signal.iloc[-2]) if len(macd_line) > 1 else macd_hist

        if current_rsi < 40 and stoch_k < 20 and macd_hist < prev_macd_hist and macd_hist < 0:
            warnings.append({
                "signal": "momentum_collapse",
                "severity": "high",
                "message": (
                    f"MOMENTUM COLLAPSE — RSI {current_rsi:.1f}, "
                    f"Stoch RSI %K {stoch_k:.1f}, MACD histogram declining. "
                    f"All oscillators bearish simultaneously."
                ),
            })
            # Fire Telegram alert
            try:
                from app.services.notifier import send_momentum_collapse_alert
                send_momentum_collapse_alert(symbol, current_price, {
                    "rsi": current_rsi,
                    "stoch_k": stoch_k,
                    "macd_histogram": macd_hist,
                })
            except Exception:
                pass
    except Exception:
        pass

    # --- Classification ---
    high_warnings = [w for w in warnings if w["severity"] == "high"]

    if len(high_warnings) >= 2 or len(warnings) >= 3:
        health = "exit_now"
    elif warnings:
        health = "caution"
    else:
        health = "healthy"

    action_map = {
        "exit_now": "EXIT IMMEDIATELY — multiple warning signals detected",
        "caution": "MONITOR CLOSELY — one warning signal detected",
        "healthy": "HOLD — trade developing normally",
    }

    return {
        "symbol": symbol,
        "health": health,
        "warnings": warnings,
        "current_price": current_price,
        "current_pnl_pct": round(current_pnl_pct, 2),
        "action": action_map[health],
        "warning_count": len(warnings),
        "high_severity_count": len(high_warnings),
    }


def get_portfolio_rebalance_suggestions(user_id: str) -> dict[str, Any]:
    """Scan user holdings for deteriorating positions and suggest high-conviction replacements."""
    from app.services.user_workspace import getUserPortfolio
    from app.services.supabase_store import get_client

    portfolio_data = getUserPortfolio(user_id)
    holdings = portfolio_data.get("holdings", [])

    rebalance_items = []
    client = get_client()

    # Pre-fetch top recommendations for replacements
    top_recs = []
    if client:
        try:
            res = (
                client.table("recommendations")
                .select("symbol, composite_score, target_price, stop_loss, reasoning, trade_mode, stocks(sector)")
                .gte("composite_score", 80)
                .order("composite_score", desc=True)
                .limit(10)
                .execute()
            )
            top_recs = res.data or []
        except Exception:
            pass

    for h in holdings:
        sym = h.get("symbol")
        pnl_pct = float(h.get("pnl_pct") or 0.0)
        current_price = float(h.get("current_price") or h.get("buy_price") or 100)

        # Quick check for deteriorating positions
        health = "healthy"
        warnings_list = []
        if pnl_pct < -8.0:
            health = "exit_now"
            warnings_list.append("Position down over 8% — severe drawdown warning")
        elif pnl_pct < -4.0:
            health = "caution"
            warnings_list.append("Position down over 4% — trend weakening")

        # Find replacement candidates if unhealthy
        replacements = []
        if health in ("caution", "exit_now") and top_recs:
            for r in top_recs:
                if r.get("symbol") != sym and len(replacements) < 2:
                    replacements.append({
                        "symbol": r.get("symbol"),
                        "display_symbol": r.get("symbol", "").replace(".NS", ""),
                        "composite_score": float(r.get("composite_score") or 80),
                        "target_price": float(r.get("target_price") or 0),
                        "stop_loss": float(r.get("stop_loss") or 0),
                        "reasoning": r.get("reasoning", "")[:100] + "...",
                    })

        rebalance_items.append({
            "symbol": sym,
            "display_symbol": h.get("display_symbol", sym),
            "shares": h.get("shares"),
            "buy_price": h.get("buy_price"),
            "current_price": current_price,
            "current_value": h.get("current_value"),
            "pnl": h.get("pnl"),
            "pnl_pct": pnl_pct,
            "health": health,
            "warnings": warnings_list,
            "replacement_picks": replacements,
        })

    unhealthy_count = sum(1 for item in rebalance_items if item["health"] in ("caution", "exit_now"))

    return {
        "user_id": user_id,
        "total_holdings": len(holdings),
        "unhealthy_count": unhealthy_count,
        "items": rebalance_items,
    }

