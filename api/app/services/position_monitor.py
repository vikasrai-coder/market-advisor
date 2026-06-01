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
