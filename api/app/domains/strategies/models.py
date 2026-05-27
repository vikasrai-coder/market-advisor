from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


StrategyVisibility = Literal["private", "unlisted", "public"]
StrategyStatus = Literal["draft", "active", "archived"]


class StrategyValidationRequest(BaseModel):
    definition: dict[str, Any]


class StrategyCreateRequest(BaseModel):
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    visibility: StrategyVisibility = "private"
    status: StrategyStatus = "draft"
    definition: dict[str, Any]


class StrategyVersionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    definition: dict[str, Any]
    notes: str | None = Field(default=None, max_length=1000)


class StrategyCloneRequest(BaseModel):
    user_id: str = Field(min_length=1)
    name: str | None = Field(default=None, max_length=120)


class StrategyValidationResult(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str] = []


ALLOWED_TIMEFRAMES = {"1m", "3m", "5m", "10m", "15m", "30m", "1h", "1d"}
ALLOWED_MARKETS = {"NSE", "BSE", "NFO", "BFO"}
ALLOWED_UNIVERSE_TYPES = {"watchlist", "symbols", "scanner"}
ALLOWED_OPERATORS = {">", ">=", "<", "<=", "=", "==", "!=", "crosses_above", "crosses_below"}
ALLOWED_INDICATORS = {
    "price",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rsi",
    "ema",
    "sma",
    "macd",
    "supertrend",
    "bollinger_upper",
    "bollinger_middle",
    "bollinger_lower",
    "vwap",
    "atr",
}
ALLOWED_CANDLE_PATTERNS = {
    "doji",
    "hammer",
    "shooting_star",
    "engulfing_bullish",
    "engulfing_bearish",
    "morning_star",
    "evening_star",
    "inside_bar",
    "outside_bar",
}
ALLOWED_CROSS_DIRECTIONS = {"above", "below"}
ALLOWED_SIZING = {"fixed_quantity", "fixed_capital", "fixed_risk", "percent_capital"}


def validate_strategy_definition(definition: dict[str, Any]) -> StrategyValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(definition, dict):
        return StrategyValidationResult(valid=False, errors=["Strategy definition must be a JSON object."])

    meta = definition.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta object is required.")
    else:
        if not str(meta.get("name") or "").strip():
            errors.append("meta.name is required.")
        market = str(meta.get("market") or "NSE").upper()
        if market not in ALLOWED_MARKETS:
            errors.append(f"meta.market must be one of {sorted(ALLOWED_MARKETS)}.")
        timeframe = str(meta.get("timeframe") or "")
        if timeframe not in ALLOWED_TIMEFRAMES:
            errors.append(f"meta.timeframe must be one of {sorted(ALLOWED_TIMEFRAMES)}.")

    universe = definition.get("universe")
    if not isinstance(universe, dict):
        errors.append("universe object is required.")
    else:
        universe_type = str(universe.get("type") or "")
        if universe_type not in ALLOWED_UNIVERSE_TYPES:
            errors.append(f"universe.type must be one of {sorted(ALLOWED_UNIVERSE_TYPES)}.")
        symbols = universe.get("symbols")
        if universe_type in {"watchlist", "symbols"} and (not isinstance(symbols, list) or not symbols):
            errors.append("universe.symbols must contain at least one symbol for watchlist/symbol strategies.")

    _validate_rule_group(definition.get("entry"), "entry", errors)
    _validate_rule_group(definition.get("exit"), "exit", errors)

    position = definition.get("position")
    if not isinstance(position, dict):
        errors.append("position object is required.")
    else:
        sizing = str(position.get("sizing") or "")
        if sizing not in ALLOWED_SIZING:
            errors.append(f"position.sizing must be one of {sorted(ALLOWED_SIZING)}.")
        if sizing == "fixed_risk" and _as_float(position.get("risk_per_trade_pct")) <= 0:
            errors.append("position.risk_per_trade_pct must be greater than 0 for fixed_risk sizing.")
        if sizing == "percent_capital" and _as_float(position.get("capital_pct")) <= 0:
            errors.append("position.capital_pct must be greater than 0 for percent_capital sizing.")

    reentry = definition.get("reentry")
    if reentry is not None:
        if not isinstance(reentry, dict):
            errors.append("reentry must be an object when provided.")
        elif reentry.get("enabled") is True:
            if _as_int(reentry.get("max_count")) < 1:
                errors.append("reentry.max_count must be at least 1 when reentry is enabled.")
            if _as_int(reentry.get("cooldown_candles")) < 0:
                errors.append("reentry.cooldown_candles cannot be negative.")

    if not errors:
        if _uses_options(definition) and str((meta or {}).get("market") or "").upper() not in {"NFO", "BFO"}:
            warnings.append("Options legs detected. Use NFO/BFO market for live options strategies.")
        if not definition.get("risk"):
            warnings.append("No explicit risk object found. Deployment will require risk limits later.")

    return StrategyValidationResult(valid=not errors, errors=errors, warnings=warnings)


def _validate_rule_group(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} object is required.")
        return

    groups = [key for key in ("all", "any") if key in value]
    if not groups:
        errors.append(f"{path} must contain all or any conditions.")
        return
    if len(groups) > 1:
        errors.append(f"{path} cannot contain both all and any at the same level.")

    key = groups[0]
    conditions = value.get(key)
    if not isinstance(conditions, list) or not conditions:
        errors.append(f"{path}.{key} must contain at least one condition.")
        return

    for index, condition in enumerate(conditions):
        _validate_condition(condition, f"{path}.{key}[{index}]", errors)


def _validate_condition(condition: Any, path: str, errors: list[str]) -> None:
    if not isinstance(condition, dict):
        errors.append(f"{path} must be an object.")
        return

    if "all" in condition or "any" in condition:
        _validate_rule_group(condition, path, errors)
        return

    if "crosses" in condition:
        crosses = condition.get("crosses")
        if not isinstance(crosses, dict):
            errors.append(f"{path}.crosses must be an object.")
            return
        if not crosses.get("left") or not crosses.get("right"):
            errors.append(f"{path}.crosses requires left and right values.")
        if crosses.get("direction") not in ALLOWED_CROSS_DIRECTIONS:
            errors.append(f"{path}.crosses.direction must be above or below.")
        return

    if "target_pct" in condition or "stop_loss_pct" in condition or "trailing_stop_pct" in condition:
        for key in ("target_pct", "stop_loss_pct", "trailing_stop_pct"):
            if key in condition and _as_float(condition.get(key)) <= 0:
                errors.append(f"{path}.{key} must be greater than 0.")
        return

    if "candle_pattern" in condition:
        if condition.get("candle_pattern") not in ALLOWED_CANDLE_PATTERNS:
            errors.append(f"{path}.candle_pattern must be one of {sorted(ALLOWED_CANDLE_PATTERNS)}.")
        return

    indicator = condition.get("indicator")
    if indicator not in ALLOWED_INDICATORS:
        errors.append(f"{path}.indicator must be one of {sorted(ALLOWED_INDICATORS)}.")
    if condition.get("operator") not in ALLOWED_OPERATORS:
        errors.append(f"{path}.operator must be one of {sorted(ALLOWED_OPERATORS)}.")
    if "value" not in condition:
        errors.append(f"{path}.value is required.")
    if "period" in condition and _as_int(condition.get("period")) <= 0:
        errors.append(f"{path}.period must be greater than 0.")


def _uses_options(definition: dict[str, Any]) -> bool:
    raw = str(definition).lower()
    return any(word in raw for word in ("straddle", "strangle", "iron_condor", "option_type", "strike"))


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
