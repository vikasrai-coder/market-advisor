"""Scan mode definitions — Intraday, Swing, Long-term, Future Date."""

from dataclasses import dataclass, field
from typing import Literal

TradeMode = Literal["intraday", "swing", "longterm", "future"]

VALID_MODES: set[str] = {"intraday", "swing", "longterm", "future"}


@dataclass(frozen=True)
class ScanConfig:
    """Configuration for a single scan mode."""

    mode: TradeMode
    label: str
    description: str

    # yfinance fetch params
    history_period: str  # e.g. "5d", "6mo", "1y"
    history_interval: str  # e.g. "60m", "1d"

    # scoring weights (must sum to 1.0)
    weight_trend: float
    weight_technical: float
    weight_news: float
    weight_fundamental: float = 0.0

    # indicator config
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_period: int = 14
    sma_short: int = 20
    sma_long: int = 50

    # selection
    top_picks: int = 10
    diversified: bool = True

    def __post_init__(self):
        total = self.weight_trend + self.weight_technical + self.weight_news + self.weight_fundamental
        assert abs(total - 1.0) < 0.001, f"ScanConfig weights must sum to 1.0, got {total:.4f}"


INTRADAY = ScanConfig(
    mode="intraday",
    label="Intraday",
    description="Same-day trades — 60-min MACD crossover signals",
    history_period="5d",
    history_interval="60m",
    weight_trend=0.50,
    weight_technical=0.40,
    weight_news=0.10,
    sma_short=9,
    sma_long=21,
)

SWING = ScanConfig(
    mode="swing",
    label="Swing Trade",
    description="Next-session picks — daily MACD + RSI + SMA analysis",
    history_period="1y",
    history_interval="1d",
    weight_trend=0.40,
    weight_technical=0.35,
    weight_news=0.25,
)

LONGTERM = ScanConfig(
    mode="longterm",
    label="Long-term",
    description="Hold 1-6 months — SMA 50/200 + fundamentals",
    history_period="1y",
    history_interval="1d",
    weight_trend=0.25,
    weight_technical=0.25,
    weight_news=0.10,
    weight_fundamental=0.40,
    sma_short=50,
    sma_long=200,
)

FUTURE = ScanConfig(
    mode="future",
    label="Future Date",
    description="Plan for a specific future date",
    history_period="1y",
    history_interval="1d",
    weight_trend=0.40,
    weight_technical=0.35,
    weight_news=0.25,
)


MODE_CONFIGS: dict[str, ScanConfig] = {
    "intraday": INTRADAY,
    "swing": SWING,
    "longterm": LONGTERM,
    "future": FUTURE,
}


def get_config(mode: str) -> ScanConfig:
    """Return the ScanConfig for a given mode string, defaulting to swing."""
    return MODE_CONFIGS.get(mode, SWING)
