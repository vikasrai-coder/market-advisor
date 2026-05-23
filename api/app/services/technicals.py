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
        elif rsi < 30:
            score += 8
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
        elif rsi < 35:
            score += 5
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
        elif rsi < 30:
            score += 12  # deep value
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
