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


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] else 0
    return float(100 - (100 / (1 + rs)))


def _macd(close: pd.Series) -> tuple[float | None, float | None]:
    if len(close) < 26:
        return None, None
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1])


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
