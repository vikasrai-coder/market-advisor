import numpy as np
import pandas as pd


def compute_indicators(history: pd.DataFrame) -> dict[str, float | None]:
    if history.empty or "Close" not in history.columns:
        return _empty()

    close = history["Close"].astype(float)
    volume = history["Volume"].astype(float) if "Volume" in history.columns else pd.Series([0.0])

    rsi = _rsi(close, 14)
    macd_line, signal_line = _macd(close)
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    change_pct = ((price - prev) / prev * 100) if prev else 0.0
    vol = float(close.pct_change().dropna().std() * np.sqrt(252) * 100) if len(close) > 2 else 0.0

    trend_score = _trend_score(price, sma_20, sma_50, rsi, macd_line, signal_line)
    technical_score = _technical_score(rsi, macd_line, signal_line, change_pct)

    return {
        "price": price,
        "change_pct": round(change_pct, 2),
        "volume": int(volume.iloc[-1]) if len(volume) else 0,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd": round(macd_line, 4) if macd_line is not None else None,
        "macd_signal": round(signal_line, 4) if signal_line is not None else None,
        "sma_20": round(float(sma_20), 2) if sma_20 is not None and not np.isnan(sma_20) else None,
        "sma_50": round(float(sma_50), 2) if sma_50 is not None and not np.isnan(sma_50) else None,
        "sma_200": round(float(sma_200), 2) if sma_200 is not None and not np.isnan(sma_200) else None,
        "trend_score": round(trend_score, 2),
        "volatility": round(vol, 2),
        "technical_score": round(technical_score, 2),
    }


# ---------------------------------------------------------------------------
# Intraday indicators (60-min candle data)
# ---------------------------------------------------------------------------


def compute_intraday_indicators(history: pd.DataFrame) -> dict[str, float | None]:
    """Compute indicators on intraday (e.g. 60-min) candle data.

    Key signals (Chartink-inspired):
      - MACD(12,26,9) crossover on 60-min candles
      - RSI(14)
      - VWAP position
      - Volume spike detection
    """
    if history.empty or "Close" not in history.columns:
        return _empty_intraday()

    close = history["Close"].astype(float)
    high = history["High"].astype(float) if "High" in history.columns else close
    low = history["Low"].astype(float) if "Low" in history.columns else close
    volume = history["Volume"].astype(float) if "Volume" in history.columns else pd.Series([0.0] * len(close))

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    change_pct = ((price - prev) / prev * 100) if prev else 0.0

    rsi = _rsi(close, 14)
    macd_line, signal_line = _macd(close, fast=12, slow=26, signal_period=9)
    bullish_cross = detect_macd_crossover(close, direction="bullish")
    bearish_cross = detect_macd_crossover(close, direction="bearish")

    # VWAP
    vwap = _vwap(high, low, close, volume)

    # Volume spike: current volume vs 20-period average
    vol_sma = volume.rolling(20).mean()
    vol_spike = False
    if len(vol_sma) > 0 and vol_sma.iloc[-1] and vol_sma.iloc[-1] > 0:
        vol_spike = float(volume.iloc[-1]) > float(vol_sma.iloc[-1]) * 1.5

    # SMA 9 / 21 for intraday
    sma_9 = close.rolling(9).mean().iloc[-1] if len(close) >= 9 else None
    sma_21 = close.rolling(21).mean().iloc[-1] if len(close) >= 21 else None

    trend_score = _intraday_trend_score(price, sma_9, sma_21, rsi, macd_line, signal_line, bullish_cross, vwap)
    technical_score = _intraday_technical_score(rsi, macd_line, signal_line, bullish_cross, bearish_cross, vol_spike, change_pct)

    return {
        "price": price,
        "change_pct": round(change_pct, 2),
        "volume": int(volume.iloc[-1]) if len(volume) else 0,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd": round(macd_line, 4) if macd_line is not None else None,
        "macd_signal": round(signal_line, 4) if signal_line is not None else None,
        "sma_9": round(float(sma_9), 2) if sma_9 is not None and not np.isnan(sma_9) else None,
        "sma_21": round(float(sma_21), 2) if sma_21 is not None and not np.isnan(sma_21) else None,
        "vwap": round(vwap, 2) if vwap is not None else None,
        "bullish_crossover": bullish_cross,
        "bearish_crossover": bearish_cross,
        "volume_spike": vol_spike,
        "trend_score": round(trend_score, 2),
        "volatility": round(float(close.pct_change().dropna().std() * 100), 2) if len(close) > 2 else 0.0,
        "technical_score": round(technical_score, 2),
    }


# ---------------------------------------------------------------------------
# Long-term indicators (1Y daily data)
# ---------------------------------------------------------------------------


def compute_longterm_indicators(history: pd.DataFrame, profile: dict | None = None) -> dict[str, float | None]:
    """Compute long-term indicators on 1-year daily data.

    Key signals:
      - SMA 50/200 golden/death cross
      - 52-week range position
      - PE ratio and dividend yield scoring
    """
    if history.empty or "Close" not in history.columns:
        return _empty_longterm()

    close = history["Close"].astype(float)
    volume = history["Volume"].astype(float) if "Volume" in history.columns else pd.Series([0.0] * len(close))

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else price
    change_pct = ((price - prev) / prev * 100) if prev else 0.0

    rsi = _rsi(close, 14)
    macd_line, signal_line = _macd(close)

    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    sma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

    # Golden cross / death cross detection
    golden_cross = False
    death_cross = False
    if len(close) >= 200:
        sma50_series = close.rolling(50).mean()
        sma200_series = close.rolling(200).mean()
        if len(sma50_series) >= 2 and len(sma200_series) >= 2:
            prev_above = float(sma50_series.iloc[-2]) > float(sma200_series.iloc[-2])
            curr_above = float(sma50_series.iloc[-1]) > float(sma200_series.iloc[-1])
            if curr_above and not prev_above:
                golden_cross = True
            if not curr_above and prev_above:
                death_cross = True

    # 52-week range position (0-100%)
    high_52w = float(close.max())
    low_52w = float(close.min())
    range_52w = high_52w - low_52w
    range_position = ((price - low_52w) / range_52w * 100) if range_52w > 0 else 50.0

    vol = float(close.pct_change().dropna().std() * np.sqrt(252) * 100) if len(close) > 2 else 0.0

    # Fundamental scoring
    pe = profile.get("pe_ratio") if profile else None
    div_yield = profile.get("dividend_yield") if profile else None
    fundamental_score = _fundamental_score(pe, div_yield, range_position)

    trend_score = _longterm_trend_score(price, sma_50, sma_200, rsi, golden_cross, range_position)
    technical_score = _technical_score(rsi, macd_line, signal_line, change_pct)

    return {
        "price": price,
        "change_pct": round(change_pct, 2),
        "volume": int(volume.iloc[-1]) if len(volume) else 0,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "macd": round(macd_line, 4) if macd_line is not None else None,
        "macd_signal": round(signal_line, 4) if signal_line is not None else None,
        "sma_50": round(float(sma_50), 2) if sma_50 is not None and not np.isnan(sma_50) else None,
        "sma_200": round(float(sma_200), 2) if sma_200 is not None and not np.isnan(sma_200) else None,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "range_52w_pct": round(range_position, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "pe_ratio": pe,
        "dividend_yield": div_yield,
        "fundamental_score": round(fundamental_score, 2),
        "trend_score": round(trend_score, 2),
        "volatility": round(vol, 2),
        "technical_score": round(technical_score, 2),
    }


# ---------------------------------------------------------------------------
# Market Regime, ATR Levels, Volume Confirmation (Quant Filter Layer)
# ---------------------------------------------------------------------------


def get_market_regime(df: pd.DataFrame) -> dict:
    """Determine if stock is in uptrend, downtrend, or sideways regime.

    Uses SMA alignment (20/50/200) + ADX for trend strength.
    Returns: {"regime": "uptrend"|"downtrend"|"sideways", "adx": float, "tradeable": bool}
    """
    if df.empty or "Close" not in df.columns:
        return {"regime": "sideways", "adx": 0.0, "tradeable": True}

    close = df["Close"].astype(float)
    if len(close) < 20:
        return {"regime": "sideways", "adx": 0.0, "tradeable": True}

    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma20
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50
    current_price = close.iloc[-1]

    # ADX calculation
    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close

    try:
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)

        atr14 = tr.rolling(14).mean()

        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        # Zero out where the other direction dominates
        mask = plus_dm < minus_dm
        plus_dm[mask] = 0
        mask2 = minus_dm <= plus_dm
        minus_dm[mask2] = 0

        plus_di = 100 * (plus_dm.rolling(14).mean() / atr14.replace(0, float("nan")))
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr14.replace(0, float("nan")))

        di_sum = (plus_di + minus_di).replace(0, float("nan"))
        dx = 100 * ((plus_di - minus_di).abs() / di_sum)
        adx = float(dx.rolling(14).mean().iloc[-1])
        if pd.isna(adx):
            adx = 0.0
    except Exception:
        adx = 0.0

    # Regime classification
    if (not pd.isna(sma20) and not pd.isna(sma50) and not pd.isna(sma200)
            and sma20 > sma50 > sma200 and current_price > sma20 and adx > 25):
        regime = "uptrend"
    elif (not pd.isna(sma20) and not pd.isna(sma50) and not pd.isna(sma200)
            and sma20 < sma50 < sma200 and current_price < sma20 and adx > 25):
        regime = "downtrend"
    else:
        regime = "sideways"

    tradeable = regime == "uptrend" or (regime == "sideways" and adx > 20)

    return {"regime": regime, "adx": round(adx, 2), "tradeable": tradeable}


def get_atr_levels(
    df: pd.DataFrame,
    entry_price: float,
    atr_period: int = 14,
    sl_multiplier: float = 2.0,
    rr_ratio: float = 2.5,
) -> dict | None:
    """Compute ATR-based stop-loss and target price.

    sl_multiplier=2.0 → SL is 2x ATR below entry (respects volatility)
    rr_ratio=2.5      → Target is 2.5x the SL distance (enforces min 2.5:1 R:R)

    Returns None if signal is invalid (R:R < 2.0 or SL <= 0).
    """
    if df.empty or entry_price is None or entry_price <= 0:
        return None

    try:
        high = df["High"].astype(float) if "High" in df.columns else df["Close"].astype(float)
        low = df["Low"].astype(float) if "Low" in df.columns else df["Close"].astype(float)
        close = df["Close"].astype(float)

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)

        atr = float(tr.rolling(atr_period).mean().iloc[-1])
        if pd.isna(atr) or atr <= 0:
            return None

        stop_loss = round(entry_price - (sl_multiplier * atr), 2)
        sl_distance = entry_price - stop_loss
        if sl_distance <= 0:
            return None

        target_price = round(entry_price + (rr_ratio * sl_distance), 2)

        if stop_loss <= 0 or target_price <= entry_price:
            return None

        actual_rr = round((target_price - entry_price) / sl_distance, 2)
        if actual_rr < 2.0:
            return None  # Enforce minimum 2:1 R:R

        return {
            "stop_loss": stop_loss,
            "target_price": target_price,
            "atr": round(atr, 2),
            "risk_reward": actual_rr,
            "sl_distance_pct": round((sl_distance / entry_price) * 100, 2),
        }
    except Exception:
        return None


def get_volume_confirmation(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Confirm if current volume is meaningfully above its 20-day average.

    Breakout signals require volume >= 1.5x the lookback average.
    """
    if df.empty or "Volume" not in df.columns:
        return {"volume_ratio": 0.0, "confirmed": False, "strong": False}

    volume = df["Volume"].astype(float)
    avg_volume = volume.rolling(lookback).mean().iloc[-1]
    current_volume = float(volume.iloc[-1])

    if pd.isna(avg_volume) or avg_volume <= 0:
        return {"volume_ratio": 0.0, "confirmed": False, "strong": False}

    volume_ratio = round(current_volume / avg_volume, 2)

    return {
        "volume_ratio": volume_ratio,
        "confirmed": volume_ratio >= 1.5,
        "strong": volume_ratio >= 2.5,
    }


def get_vwap(df: pd.DataFrame) -> float | None:
    """Standard VWAP for intraday use."""
    if df.empty or "Volume" not in df.columns:
        return None
    high = df["High"].astype(float) if "High" in df.columns else df["Close"].astype(float)
    low = df["Low"].astype(float) if "Low" in df.columns else df["Close"].astype(float)
    close = df["Close"].astype(float)
    volume = df["Volume"].astype(float)
    return _vwap(high, low, close, volume)


# ---------------------------------------------------------------------------
# Enhancement #2 — Smart Money / Institutional Accumulation Detector
# ---------------------------------------------------------------------------


def get_smart_money_signals(df: pd.DataFrame) -> dict:
    """Detect institutional accumulation vs distribution using OBV + CMF.

    Signals:
      "accumulation"  → Institutions buying. High conviction to go long.
      "distribution"  → Institutions selling. Avoid or skip.
      "neutral"       → No clear institutional bias.

    OBV trend confirms whether volume is flowing in or out.
    CMF (Chaikin Money Flow) measures net buying vs selling pressure.
    Bearish divergence: price at high but OBV not → institutional selling
    into retail buying (most dangerous scenario).
    """
    if df.empty or "Close" not in df.columns or "Volume" not in df.columns:
        return {"signal": "neutral", "cmf": 0.0, "obv_trend": "flat",
                "bearish_divergence": False, "reason": "Insufficient data"}

    try:
        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)
        high = df["High"].astype(float) if "High" in df.columns else close
        low = df["Low"].astype(float) if "Low" in df.columns else close

        if len(close) < 21:
            return {"signal": "neutral", "cmf": 0.0, "obv_trend": "flat",
                    "bearish_divergence": False, "reason": "Not enough candles"}

        # OBV: +volume on up days, -volume on down days
        direction = ((close.diff() > 0).astype(float) * 2 - 1)
        direction.iloc[0] = 0  # no signal for first candle
        obv = (volume * direction).cumsum()
        obv_sma = obv.rolling(20).mean()
        obv_trend = "up" if float(obv.iloc[-1]) > float(obv_sma.iloc[-1]) else "down"

        # Bearish divergence: price near 20-day high but OBV is not
        price_high_20 = float(close.rolling(20).max().iloc[-1])
        obv_high_20 = float(obv.rolling(20).max().iloc[-1])
        price_at_high = float(close.iloc[-1]) >= price_high_20 * 0.98
        obv_at_high = float(obv.iloc[-1]) >= obv_high_20 * 0.95
        bearish_divergence = price_at_high and not obv_at_high

        # CMF (20-period Chaikin Money Flow)
        hl_range = (high - low).replace(0, float("nan"))
        money_flow_mult = ((close - low) - (high - close)) / hl_range
        money_flow_mult = money_flow_mult.fillna(0)
        mfv = money_flow_mult * volume
        vol_sum = volume.rolling(20).sum().replace(0, float("nan"))
        cmf = float((mfv.rolling(20).sum() / vol_sum).iloc[-1])
        if pd.isna(cmf):
            cmf = 0.0
        cmf = round(cmf, 4)

        # Classification
        if bearish_divergence:
            signal = "distribution"
            reason = "Price at 20-day high but OBV diverging — institutional selling into retail buying"
        elif obv_trend == "up" and cmf > 0.10:
            signal = "accumulation"
            reason = f"OBV rising, CMF={cmf} — net buying pressure detected"
        elif obv_trend == "down" or cmf < -0.10:
            signal = "distribution"
            reason = f"OBV falling, CMF={cmf} — net selling pressure"
        else:
            signal = "neutral"
            reason = f"CMF={cmf} — no clear institutional bias"

        return {
            "signal": signal,
            "cmf": cmf,
            "obv_trend": obv_trend,
            "bearish_divergence": bearish_divergence,
            "reason": reason,
        }

    except Exception as exc:
        return {"signal": "neutral", "cmf": 0.0, "obv_trend": "flat",
                "bearish_divergence": False, "reason": f"Error: {exc}"}


# ---------------------------------------------------------------------------
# Enhancement #3 — Candlestick Pattern Recognition (Entry Timing)
# ---------------------------------------------------------------------------


def get_candlestick_patterns(df: pd.DataFrame) -> dict:
    """Detect high-probability reversal and continuation patterns on last 3 candles.

    Only 6 patterns with proven statistical edge on NSE are included.
    Used for entry timing precision — not primary signal generation.

    score_delta: positive = bullish patterns detected, negative = bearish.
    Bearish patterns penalised more heavily (protection bias).
    """
    if df.empty or not all(c in df.columns for c in ["Open", "High", "Low", "Close"]):
        return {"patterns": [], "bullish_count": 0, "bearish_count": 0,
                "score_delta": 0, "primary_pattern": None}

    try:
        o = df["Open"].astype(float)
        h = df["High"].astype(float)
        l = df["Low"].astype(float)
        c = df["Close"].astype(float)

        if len(c) < 10:
            return {"patterns": [], "bullish_count": 0, "bearish_count": 0,
                    "score_delta": 0, "primary_pattern": None}

        body = (c - o).abs()
        upper_wick = h - c.where(c > o, o)
        lower_wick = c.where(c < o, o) - l
        avg_body = body.rolling(10).mean()

        patterns: list[dict] = []

        # 1. Bullish Engulfing — strong reversal
        if (c.iloc[-2] < o.iloc[-2]           # prev candle red
                and c.iloc[-1] > o.iloc[-1]   # current candle green
                and o.iloc[-1] < c.iloc[-2]   # opens below prev close
                and c.iloc[-1] > o.iloc[-2]):  # closes above prev open
            patterns.append({
                "name": "Bullish Engulfing",
                "type": "reversal_bullish",
                "strength": "high",
                "action": "Look for long entry",
            })

        # 2. Hammer — bullish reversal at support
        if (float(lower_wick.iloc[-1]) >= 2 * float(body.iloc[-1])
                and float(upper_wick.iloc[-1]) <= 0.3 * float(body.iloc[-1])
                and float(body.iloc[-1]) > 0):
            patterns.append({
                "name": "Hammer",
                "type": "reversal_bullish",
                "strength": "medium",
                "action": "Potential reversal — confirm with volume",
            })

        # 3. Shooting Star — bearish reversal (avoid longs)
        if (float(upper_wick.iloc[-1]) >= 2 * float(body.iloc[-1])
                and float(lower_wick.iloc[-1]) <= 0.3 * float(body.iloc[-1])
                and c.iloc[-1] < o.iloc[-1]):
            patterns.append({
                "name": "Shooting Star",
                "type": "reversal_bearish",
                "strength": "high",
                "action": "Avoid long entry — potential reversal down",
            })

        # 4. Bullish Marubozu — strong momentum continuation
        avg_b = float(avg_body.iloc[-1]) if not pd.isna(avg_body.iloc[-1]) else 1.0
        if (c.iloc[-1] > o.iloc[-1]
                and float(body.iloc[-1]) >= 1.5 * avg_b
                and float(upper_wick.iloc[-1]) <= 0.05 * float(body.iloc[-1])
                and float(lower_wick.iloc[-1]) <= 0.05 * float(body.iloc[-1])):
            patterns.append({
                "name": "Bullish Marubozu",
                "type": "continuation_bullish",
                "strength": "high",
                "action": "Strong momentum — enter on next pullback",
            })

        # 5. Doji at resistance — indecision, potential reversal
        if avg_b > 0 and float(body.iloc[-1]) <= 0.1 * avg_b:
            patterns.append({
                "name": "Doji",
                "type": "indecision",
                "strength": "medium",
                "action": "Wait for next candle direction confirmation",
            })

        # 6. Inside Bar — breakout setup
        if (h.iloc[-1] <= h.iloc[-2] and l.iloc[-1] >= l.iloc[-2]):
            patterns.append({
                "name": "Inside Bar",
                "type": "breakout_setup",
                "strength": "medium",
                "action": "Breakout trade — enter on break of mother bar high",
            })

        bullish = [p for p in patterns if "bullish" in p["type"]]
        bearish = [p for p in patterns if "bearish" in p["type"]]

        # Bearish patterns penalised more heavily (protection bias)
        score_delta = len(bullish) * 8 - len(bearish) * 15

        return {
            "patterns": patterns,
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "score_delta": score_delta,
            "primary_pattern": patterns[0]["name"] if patterns else None,
        }

    except Exception:
        return {"patterns": [], "bullish_count": 0, "bearish_count": 0,
                "score_delta": 0, "primary_pattern": None}


# ---------------------------------------------------------------------------
# Enhancement #6 — Support / Resistance Level Detection
# ---------------------------------------------------------------------------


def get_key_levels(df: pd.DataFrame, lookback: int = 60) -> dict:
    """Identify key support and resistance levels via swing highs/lows.

    Used to:
      1. Validate that stop-loss is placed BELOW a support level.
      2. Check that the target is not BLOCKED by a major resistance.

    A trade where the target sits inside a resistance zone has much lower
    probability of reaching it — the path is obstructed.
    """
    if df.empty or not all(c in df.columns for c in ["High", "Low", "Close"]):
        return {"nearest_support": None, "nearest_resistance": None,
                "target_blocked": False, "support_levels": [], "resistance_levels": []}

    try:
        close = df["Close"].astype(float).tail(lookback)
        high = df["High"].astype(float).tail(lookback)
        low = df["Low"].astype(float).tail(lookback)
        current_price = float(close.iloc[-1])

        swing_highs: list[float] = []
        swing_lows: list[float] = []

        for i in range(2, len(close) - 2):
            # Swing high: candle high > both neighbours on each side
            if (float(high.iloc[i]) > float(high.iloc[i - 1])
                    and float(high.iloc[i]) > float(high.iloc[i + 1])
                    and float(high.iloc[i]) > float(high.iloc[i - 2])
                    and float(high.iloc[i]) > float(high.iloc[i + 2])):
                swing_highs.append(float(high.iloc[i]))
            # Swing low: candle low < both neighbours on each side
            if (float(low.iloc[i]) < float(low.iloc[i - 1])
                    and float(low.iloc[i]) < float(low.iloc[i + 1])
                    and float(low.iloc[i]) < float(low.iloc[i - 2])
                    and float(low.iloc[i]) < float(low.iloc[i + 2])):
                swing_lows.append(float(low.iloc[i]))

        supports_below = sorted([s for s in swing_lows if s < current_price], reverse=True)
        resistances_above = sorted([r for r in swing_highs if r > current_price])

        nearest_support = supports_below[0] if supports_below else None
        nearest_resistance = resistances_above[0] if resistances_above else None

        # Target blocked: resistance is within 2% above current price
        target_blocked = bool(nearest_resistance and nearest_resistance < current_price * 1.02)

        return {
            "nearest_support": round(nearest_support, 2) if nearest_support else None,
            "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
            "target_blocked": target_blocked,
            "support_levels": [round(s, 2) for s in supports_below[:3]],
            "resistance_levels": [round(r, 2) for r in resistances_above[:3]],
        }

    except Exception:
        return {"nearest_support": None, "nearest_resistance": None,
                "target_blocked": False, "support_levels": [], "resistance_levels": []}


# ---------------------------------------------------------------------------
# MACD crossover detection (Chartink-inspired)
# ---------------------------------------------------------------------------


def detect_macd_crossover(close: pd.Series, direction: str = "bullish",
                          fast: int = 12, slow: int = 26, sig: int = 9) -> bool:
    """Detect MACD line crossing above (bullish) or below (bearish) signal line.

    This replicates the Chartink scanner logic:
      - Bullish: MACD line crossed_above MACD signal AND signal >= 0
      - Bearish: MACD line crossed_below MACD signal AND signal <= 0
    """
    if len(close) < slow + sig:
        return False

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=sig, adjust=False).mean()

    if len(macd) < 2:
        return False

    curr_macd = float(macd.iloc[-1])
    prev_macd = float(macd.iloc[-2])
    curr_signal = float(signal.iloc[-1])
    prev_signal = float(signal.iloc[-2])

    if direction == "bullish":
        crossed = prev_macd <= prev_signal and curr_macd > curr_signal
        return crossed and curr_signal >= 0
    else:  # bearish
        crossed = prev_macd >= prev_signal and curr_macd < curr_signal
        return crossed and curr_signal <= 0


# ---------------------------------------------------------------------------
# Core indicator computations
# ---------------------------------------------------------------------------


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] else 0
    return float(100 - (100 / (1 + rs)))


def _macd(close: pd.Series, fast: int = 12, slow: int = 26,
          signal_period: int = 9) -> tuple[float | None, float | None]:
    if len(close) < slow:
        return None, None
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1])


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float | None:
    """Volume-Weighted Average Price."""
    if len(close) == 0 or volume.sum() == 0:
        return None
    typical = (high + low + close) / 3
    cumvol = volume.cumsum()
    cumtp = (typical * volume).cumsum()
    if cumvol.iloc[-1] == 0:
        return None
    return float(cumtp.iloc[-1] / cumvol.iloc[-1])


# ---------------------------------------------------------------------------
# Scoring functions — Swing (existing)
# ---------------------------------------------------------------------------


def _trend_score(
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    rsi: float | None,
    macd: float | None,
    signal: float | None,
) -> float:
    score = 50.0
    if sma_20 and price > sma_20:
        score += 12
    elif sma_20:
        score -= 12
    if sma_50 and price > sma_50:
        score += 15
    elif sma_50:
        score -= 15
    if rsi is not None:
        if 45 <= rsi <= 65:
            score += 10
        elif rsi > 70:
            score -= 15
    if macd is not None and signal is not None:
        score += 10 if macd > signal else -10
    return max(0.0, min(100.0, score))


def _technical_score(rsi: float | None, macd: float | None, signal: float | None, change_pct: float) -> float:
    score = 50.0
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 15
        elif rsi > 75:
            score -= 20
    if macd is not None and signal is not None:
        score += 15 if macd > signal else -15
    if change_pct > 0:
        score += min(change_pct * 2, 15)
    else:
        score += max(change_pct * 2, -15)
    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Scoring functions — Intraday
# ---------------------------------------------------------------------------


def _intraday_trend_score(
    price: float,
    sma_9: float | None,
    sma_21: float | None,
    rsi: float | None,
    macd: float | None,
    signal: float | None,
    bullish_cross: bool,
    vwap: float | None,
) -> float:
    score = 50.0
    # MACD crossover is the primary signal (Chartink style)
    if bullish_cross:
        score += 20
    if sma_9 and price > sma_9:
        score += 8
    elif sma_9:
        score -= 8
    if sma_21 and price > sma_21:
        score += 10
    elif sma_21:
        score -= 10
    if rsi is not None:
        if 40 <= rsi <= 65:
            score += 8
        elif rsi > 75:
            score -= 15
        elif rsi < 25:
            score += 5  # oversold bounce potential
    if macd is not None and signal is not None:
        score += 8 if macd > signal else -8
    if vwap and price > vwap:
        score += 6
    elif vwap:
        score -= 6
    return max(0.0, min(100.0, score))


def _intraday_technical_score(
    rsi: float | None,
    macd: float | None,
    signal: float | None,
    bullish_cross: bool,
    bearish_cross: bool,
    vol_spike: bool,
    change_pct: float,
) -> float:
    score = 50.0
    if bullish_cross:
        score += 18
    if bearish_cross:
        score -= 18
    if vol_spike:
        score += 8
    if rsi is not None:
        if 45 <= rsi <= 60:
            score += 10
        elif rsi > 75:
            score -= 15
    if macd is not None and signal is not None:
        score += 10 if macd > signal else -10
    if change_pct > 0:
        score += min(change_pct * 3, 12)
    else:
        score += max(change_pct * 3, -12)
    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Scoring functions — Long-term
# ---------------------------------------------------------------------------


def _longterm_trend_score(
    price: float,
    sma_50: float | None,
    sma_200: float | None,
    rsi: float | None,
    golden_cross: bool,
    range_position: float,
) -> float:
    score = 50.0
    if golden_cross:
        score += 20
    if sma_50 and price > sma_50:
        score += 10
    elif sma_50:
        score -= 10
    if sma_200 and price > sma_200:
        score += 15
    elif sma_200:
        score -= 15
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 8
        elif rsi > 80:
            score -= 10
    # Prefer stocks not at extreme highs
    if range_position < 40:
        score += 5  # near 52w lows = value
    elif range_position > 90:
        score -= 5
    return max(0.0, min(100.0, score))


def _fundamental_score(pe: float | None, div_yield: float | None, range_position: float) -> float:
    """Score based on fundamental metrics."""
    score = 50.0
    if pe is not None:
        if 5 <= pe <= 20:
            score += 20  # reasonable valuation
        elif 20 < pe <= 35:
            score += 8
        elif pe > 50:
            score -= 15
        elif pe < 0:
            score -= 10  # loss-making
    if div_yield is not None:
        if div_yield > 0.03:
            score += 15  # 3%+ yield
        elif div_yield > 0.01:
            score += 8
    # Near 52-week low is value for long-term
    if range_position < 30:
        score += 10
    elif range_position > 85:
        score -= 5
    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Empty return templates
# ---------------------------------------------------------------------------


def _empty() -> dict[str, float | None]:
    return {
        "price": None,
        "change_pct": None,
        "volume": None,
        "rsi": None,
        "macd": None,
        "macd_signal": None,
        "sma_20": None,
        "sma_50": None,
        "trend_score": 50.0,
        "volatility": None,
        "technical_score": 50.0,
    }


def _empty_intraday() -> dict[str, float | None]:
    return {
        **_empty(),
        "sma_9": None,
        "sma_21": None,
        "vwap": None,
        "bullish_crossover": False,
        "bearish_crossover": False,
        "volume_spike": False,
    }


def _empty_longterm() -> dict[str, float | None]:
    return {
        **_empty(),
        "sma_200": None,
        "golden_cross": False,
        "death_cross": False,
        "range_52w_pct": 50.0,
        "high_52w": None,
        "low_52w": None,
        "pe_ratio": None,
        "dividend_yield": None,
        "fundamental_score": 50.0,
    }


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI series for the entire series."""
    if len(close) < period + 1:
        return pd.Series(50.0, index=close.index)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Use standard exponential moving average for RSI
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    
    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def get_optimal_entry_zone(df: pd.DataFrame, regime: dict, atr: float) -> dict:
    """
    Instead of entering immediately, identifies the OPTIMAL ENTRY ZONE
    using pullback-to-support logic.
    
    Philosophy:
    - In an uptrend, price moves in waves: impulse UP -> pullback -> impulse UP
    - The ideal entry is at the END of a pullback, not the start of one
    - We buy "dips within uptrends" not "breakouts at the top of the move"
    
    Entry Types:
    "immediate"  -> Price is in the sweet spot RIGHT NOW — enter today
    "wait_dip"   -> Price is extended — wait for pullback to entry zone
    "avoid"      -> Price is too extended — risk:reward destroyed
    """
    close = df['Close']
    current_price = close.iloc[-1]
    
    # EMA8 and EMA21 — fast and slow momentum EMAs
    ema8 = close.ewm(span=8,  adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
    sma20 = close.rolling(20).mean().iloc[-1]
    
    # Distance from EMA — how "extended" is price?
    distance_from_ema21_pct = ((current_price - ema21) / ema21) * 100 if ema21 else 0.0
    distance_from_sma20_pct = ((current_price - sma20) / sma20) * 100 if sma20 else 0.0
    
    # How many ATRs above the EMA8 is the price?
    atr_extension = (current_price - ema8) / atr if atr > 0 else 0.0
    
    # Ideal entry zone: price is near or slightly above EMA8/21
    # Not extended (< 1.5 ATR above EMA8)
    
    if atr_extension <= 0.5:
        # Price is AT or just above the fast EMA — ideal entry
        entry_type = "immediate"
        ideal_entry = current_price
        entry_note = "Price near EMA8 — low-risk entry point"
        
    elif atr_extension <= 1.5:
        # Price is slightly extended but acceptable
        entry_type = "immediate"
        ideal_entry = current_price
        entry_note = "Acceptable entry — mild extension from EMA8"
        
    elif atr_extension <= 3.0:
        # Price is extended — better to wait for a pullback
        ideal_entry_zone_low = round(ema8 * 1.002, 2)
        ideal_entry_zone_high = round(ema8 + (0.5 * atr), 2)
        entry_type = "wait_dip"
        ideal_entry = ideal_entry_zone_low
        entry_note = (f"Price extended {round(atr_extension, 1)}x ATR above EMA8. "
                      f"Wait for pullback to ₹{ideal_entry_zone_low}–₹{ideal_entry_zone_high}")
        
    else:
        # Price is massively extended — risk:reward is destroyed
        entry_type = "avoid"
        ideal_entry = None
        entry_note = f"Price {round(atr_extension, 1)}x ATR above EMA8 — chasing. Skip this setup."
    
    return {
        "entry_type": entry_type,
        "ideal_entry": ideal_entry,
        "atr_extension": round(atr_extension, 2),
        "distance_from_ema21_pct": round(distance_from_ema21_pct, 2),
        "entry_note": entry_note
    }


def get_stock_personality(stock_profile: dict, df: pd.DataFrame) -> dict:
    """
    Classifies the stock's trading personality to apply the right rule set.
    
    Profiles:
    "institutional"  -> Large-cap, high volume, tracks FII flows — use trend following
    "momentum"       -> Mid-cap growth, volume surges — use breakout rules
    "operator_risk"  -> Low volume, small-cap — high manipulation risk, tightest rules
    "avoid_today"    -> Illiquid — do not trade regardless of setup
    """
    cap_segment = stock_profile.get("cap_segment", "small")
    
    if len(df) < 20:
        # Insufficient history to determine personality, return conservative default
        return {
            "personality": "operator_risk",
            "avg_daily_value_cr": 0.0,
            "annualised_vol_pct": 30.0,
            "rules": {
                "min_composite_score": 78,
                "atr_sl_multiplier": 1.5,
                "min_volume_ratio": 2.0,
                "rsi_sweet_spot": (52, 68),
                "note": "Operator risk / short history. Tightest rules apply."
            }
        }
        
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    avg_price = df['Close'].rolling(20).mean().iloc[-1]
    
    # Average daily traded value (₹ crores) — liquidity proxy
    avg_daily_value_cr = (avg_volume * avg_price) / 1e7
    
    # Volatility profile
    daily_returns = df['Close'].pct_change().dropna()
    annualised_vol = daily_returns.std() * (252 ** 0.5) * 100 if len(daily_returns) > 0 else 30.0
    
    # Classification
    if avg_daily_value_cr < 1.0:
        # Less than ₹1 crore daily turnover — dangerous
        personality = "avoid_today"
        rules = {
            "min_composite_score": 999,  # Effectively blocked
            "atr_sl_multiplier": None,
            "note": "Illiquid — avg daily value ₹{:.1f}Cr. Skip.".format(avg_daily_value_cr)
        }
    
    elif cap_segment == "large" and avg_daily_value_cr > 100:
        personality = "institutional"
        rules = {
            "min_composite_score": 65,
            "atr_sl_multiplier": 2.0,    # Standard SL
            "min_volume_ratio": 1.3,     # Lower volume bar — already liquid
            "rsi_sweet_spot": (48, 68),  # Wider RSI band — less volatile
            "note": "Large-cap institutional. Trend-following rules apply."
        }
    
    elif cap_segment in ("mid", "large") and avg_daily_value_cr > 20:
        personality = "momentum"
        rules = {
            "min_composite_score": 68,
            "atr_sl_multiplier": 1.8,    # Slightly tighter
            "min_volume_ratio": 1.5,     # Needs real volume
            "rsi_sweet_spot": (50, 70),
            "note": "Mid-cap momentum stock. Breakout + volume required."
        }
    
    else:
        personality = "operator_risk"
        rules = {
            "min_composite_score": 78,   # Much higher bar
            "atr_sl_multiplier": 1.5,    # Tighter SL — these move fast
            "min_volume_ratio": 2.0,     # Needs 2x volume minimum
            "rsi_sweet_spot": (52, 68),  # Tighter RSI band
            "note": "Small-cap/operator risk. High bar required. ATR SL = 1.5x."
        }
    
    return {
        "personality": personality,
        "avg_daily_value_cr": round(avg_daily_value_cr, 2),
        "annualised_vol_pct": round(annualised_vol, 2),
        "rules": rules
    }
