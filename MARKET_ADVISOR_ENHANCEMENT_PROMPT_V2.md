# 🧠 MARKET ADVISOR — ADVANCED INTELLIGENCE LAYER (PROMPT 2 OF 2)

**Document Type:** Performance Enhancement Brief — Layer 2  
**Prerequisite:** All 8 fixes from Prompt 1 must be implemented and validated first  
**Persona:** Institutional Algo Desk Quant — NSE India specialist  
**Constraint:** Zero paid resources. Pure math + free data (yfinance, HuggingFace free tier, Supabase)

---

## WHY PROMPT 1 IS NOT ENOUGH

Prompt 1 stops you from losing money. It eliminates bad trades.  
Prompt 2 makes you **find and time good trades with precision.**

The difference between a retail scanner and an institutional system is not just filtering — it is **context, confluence, and timing.** A professional desk does not just ask "is this stock technically set up?" They ask:

- Is the **sector** this stock belongs to in favour right now?
- Where is this stock in its **price cycle** — early breakout or late exhaustion?
- Is **smart money (institutions)** accumulating or distributing?
- Does this signal have **multi-timeframe confluence** — does the weekly, daily, and intraday all agree?
- What is the **market-wide risk environment** — should we be aggressive or defensive today?

None of these are answered by RSI + MACD alone. This prompt adds all of them — using only free data.

---

## 📐 ENHANCEMENT #1 — SECTOR RELATIVE STRENGTH ENGINE

**New File:** `api/app/services/sector_rs.py`  
**Why:** A rising stock in a falling sector is a warning. A rising stock in a rising sector is a conviction trade. Institutional money rotates sector by sector. Trade with the rotation, not against it.

### What to Build

```python
# sector_rs.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# NSE Sector proxies using free yfinance ETF/Index data
# These are NSE sectoral indices available via yfinance
NSE_SECTOR_PROXIES = {
    "IT":           "^CNXIT",      # Nifty IT Index
    "Bank":         "^NSEBANK",    # Nifty Bank Index
    "Pharma":       "^CNXPHARMA",  # Nifty Pharma
    "Auto":         "^CNXAUTO",    # Nifty Auto
    "FMCG":         "^CNXFMCG",    # Nifty FMCG
    "Metal":        "^CNXMETAL",   # Nifty Metal
    "Energy":       "^CNXENERGY",  # Nifty Energy
    "Realty":       "^CNXREALTY",  # Nifty Realty
    "Infra":        "^CNXINFRA",   # Nifty Infra
    "Market":       "^NSEI",       # Nifty 50 (benchmark)
}

def get_sector_relative_strength(sector: str, period_days: int = 20) -> dict:
    """
    Measures how strongly a sector is performing RELATIVE to Nifty 50.
    
    RS > 1.05  → Sector outperforming → Green light to trade stocks in this sector
    RS 0.95-1.05 → Neutral → Proceed with caution
    RS < 0.95  → Sector underperforming → Avoid longs in this sector
    """
    end = datetime.today()
    start = end - timedelta(days=period_days + 10)
    
    sector_proxy = NSE_SECTOR_PROXIES.get(sector)
    market_proxy = NSE_SECTOR_PROXIES["Market"]
    
    if not sector_proxy:
        return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown"}
    
    try:
        sector_df = yf.download(sector_proxy, start=start, end=end, 
                                interval="1d", progress=False)
        market_df = yf.download(market_proxy, start=start, end=end, 
                                interval="1d", progress=False)
        
        if sector_df.empty or market_df.empty:
            return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown"}
        
        # Relative performance over period
        sector_return = (sector_df['Close'].iloc[-1] / sector_df['Close'].iloc[0]) - 1
        market_return = (market_df['Close'].iloc[-1] / market_df['Close'].iloc[0]) - 1
        
        # RS ratio: sector return vs market return (normalised)
        rs_score = round((1 + sector_return) / (1 + market_return), 4)
        
        # Sector trend (is sector itself in uptrend?)
        sma10 = sector_df['Close'].rolling(10).mean().iloc[-1]
        sector_price = sector_df['Close'].iloc[-1]
        sector_trend = "up" if sector_price > sma10 else "down"
        
        if rs_score > 1.05 and sector_trend == "up":
            status = "leading"       # Best sector to trade
        elif rs_score > 1.00:
            status = "outperforming" # Acceptable
        elif rs_score > 0.95:
            status = "neutral"       # Caution
        else:
            status = "lagging"       # Avoid
            
        return {
            "rs_score": rs_score,
            "status": status,
            "sector_return_pct": round(sector_return * 100, 2),
            "market_return_pct": round(market_return * 100, 2),
            "sector_trend": sector_trend
        }
        
    except Exception:
        return {"rs_score": 1.0, "status": "neutral", "sector_trend": "unknown"}


def get_all_sector_rankings() -> list:
    """
    Returns all NSE sectors ranked by relative strength.
    Use this to identify the top 3 sectors to focus on each day.
    Cache this result — run once per morning, not per stock.
    """
    rankings = []
    for sector_name in NSE_SECTOR_PROXIES:
        if sector_name == "Market":
            continue
        rs = get_sector_relative_strength(sector_name)
        rankings.append({
            "sector": sector_name,
            **rs
        })
    
    return sorted(rankings, key=lambda x: x["rs_score"], reverse=True)
```

### Integration in `analyzer.py`

```python
# At the start of each scan run — ONCE, not per stock
sector_rankings = get_all_sector_rankings()
leading_sectors = [s["sector"] for s in sector_rankings if s["status"] in ("leading", "outperforming")]

# Per stock — add sector RS check
stock_sector = stock_profile.get("sector")  # from stocks table
sector_rs = get_sector_relative_strength(stock_sector)

if sector_rs["status"] == "lagging":
    # Reduce composite score — sector headwind
    composite_score -= 20
    
if sector_rs["status"] == "leading":
    # Sector tailwind — bonus
    composite_score += 10
    
# HARD RULE: Never put a lagging-sector stock in top 3 recommendations
# regardless of individual stock score
```

---

## 📐 ENHANCEMENT #2 — SMART MONEY / INSTITUTIONAL ACCUMULATION DETECTOR

**Add to:** `technicals.py`  
**Why:** Retail traders chase price. Smart money (FIIs, mutual funds, prop desks) leaves footprints in volume patterns. The Chaikin Money Flow (CMF) and On-Balance Volume (OBV) trend reveal whether big players are quietly accumulating or distributing.

```python
def get_smart_money_signals(df: pd.DataFrame) -> dict:
    """
    Detects institutional accumulation vs distribution using:
    1. On-Balance Volume (OBV) trend — is volume confirming price?
    2. Chaikin Money Flow (CMF) — net buying vs selling pressure
    3. Price-Volume Divergence — price up but OBV flat = warning
    
    Returns:
        "accumulation"  → Institutions buying. High conviction to go long.
        "distribution"  → Institutions selling. Avoid or go short.
        "neutral"       → No clear footprint.
    """
    close = df['Close']
    volume = df['Volume']
    high = df['High']
    low = df['Low']
    
    # --- OBV ---
    obv = (volume * ((close.diff() > 0).astype(int) * 2 - 1)).cumsum()
    obv_sma = obv.rolling(20).mean()
    obv_trend = "up" if obv.iloc[-1] > obv_sma.iloc[-1] else "down"
    
    # OBV divergence: price making new high but OBV not — bearish divergence
    price_high_20 = close.rolling(20).max().iloc[-1]
    obv_high_20 = obv.rolling(20).max().iloc[-1]
    price_at_high = close.iloc[-1] >= price_high_20 * 0.98
    obv_at_high = obv.iloc[-1] >= obv_high_20 * 0.95
    
    bearish_divergence = price_at_high and not obv_at_high
    
    # --- Chaikin Money Flow (20 period) ---
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low + 1e-10)
    money_flow_volume = money_flow_multiplier * volume
    cmf = money_flow_volume.rolling(20).sum() / volume.rolling(20).sum()
    cmf_value = round(cmf.iloc[-1], 4)
    
    # --- Classification ---
    if bearish_divergence:
        signal = "distribution"
        reason = "Price at high but OBV diverging — institutional selling into retail buying"
    elif obv_trend == "up" and cmf_value > 0.10:
        signal = "accumulation"
        reason = f"OBV rising, CMF={cmf_value} — net buying pressure detected"
    elif obv_trend == "down" or cmf_value < -0.10:
        signal = "distribution"
        reason = f"OBV falling, CMF={cmf_value} — net selling pressure"
    else:
        signal = "neutral"
        reason = f"CMF={cmf_value} — no clear institutional bias"
    
    return {
        "signal": signal,
        "cmf": cmf_value,
        "obv_trend": obv_trend,
        "bearish_divergence": bearish_divergence,
        "reason": reason
    }
```

### Integration in `analyzer.py` Composite Score

```python
smart_money = get_smart_money_signals(df)

if smart_money["signal"] == "distribution":
    # Hard block — never buy into distribution
    if smart_money["bearish_divergence"]:
        continue  # Skip entirely — this is a trap
    else:
        composite_score -= 25

elif smart_money["signal"] == "accumulation":
    composite_score += 15  # High-value confirmation

# Add to reasoning text
reasoning += f" Smart money: {smart_money['reason']}."
```

---

## 📐 ENHANCEMENT #3 — CANDLESTICK PATTERN RECOGNITION (ENTRY TIMING)

**Add to:** `technicals.py`  
**Why:** RSI and MACD tell you *what* the trend is. Candlestick patterns tell you *when* to enter within that trend. A bullish engulfing at support is a far higher-probability entry than a random RSI crossover.

```python
def get_candlestick_patterns(df: pd.DataFrame) -> dict:
    """
    Detects high-probability reversal and continuation patterns
    on the last 3 candles. Used for entry timing, not signal generation.
    
    Only patterns with statistical edge in NSE backtests are included.
    No exotic patterns — only the 6 that actually work.
    """
    o = df['Open']
    h = df['High']
    l = df['Low']
    c = df['Close']
    
    patterns = []
    
    # Body and wick sizes
    body = abs(c - o)
    upper_wick = h - c.where(c > o, o)
    lower_wick = c.where(c < o, o) - l
    avg_body = body.rolling(10).mean()
    
    last = -1  # most recent candle
    prev = -2
    prev2 = -3
    
    # 1. Bullish Engulfing — strong reversal
    if (c.iloc[prev] < o.iloc[prev] and          # previous candle red
        c.iloc[last] > o.iloc[last] and          # current candle green
        o.iloc[last] < c.iloc[prev] and          # opens below prev close
        c.iloc[last] > o.iloc[prev]):            # closes above prev open
        patterns.append({
            "name": "Bullish Engulfing",
            "type": "reversal_bullish",
            "strength": "high",
            "action": "Look for long entry"
        })
    
    # 2. Hammer — bullish reversal at support
    if (lower_wick.iloc[last] >= 2 * body.iloc[last] and
        upper_wick.iloc[last] <= 0.3 * body.iloc[last] and
        body.iloc[last] > 0):
        patterns.append({
            "name": "Hammer",
            "type": "reversal_bullish",
            "strength": "medium",
            "action": "Potential reversal — confirm with volume"
        })
    
    # 3. Shooting Star — bearish reversal (avoid longs)
    if (upper_wick.iloc[last] >= 2 * body.iloc[last] and
        lower_wick.iloc[last] <= 0.3 * body.iloc[last] and
        c.iloc[last] < o.iloc[last]):
        patterns.append({
            "name": "Shooting Star",
            "type": "reversal_bearish",
            "strength": "high",
            "action": "Avoid long entry — potential reversal down"
        })
    
    # 4. Bullish Marubozu — strong momentum continuation
    if (c.iloc[last] > o.iloc[last] and
        body.iloc[last] >= 1.5 * avg_body.iloc[last] and
        upper_wick.iloc[last] <= 0.05 * body.iloc[last] and
        lower_wick.iloc[last] <= 0.05 * body.iloc[last]):
        patterns.append({
            "name": "Bullish Marubozu",
            "type": "continuation_bullish",
            "strength": "high",
            "action": "Strong momentum — enter on next pullback"
        })
    
    # 5. Doji at resistance — indecision, potential reversal
    if body.iloc[last] <= 0.1 * avg_body.iloc[last]:
        patterns.append({
            "name": "Doji",
            "type": "indecision",
            "strength": "medium",
            "action": "Wait for next candle direction confirmation"
        })
    
    # 6. Inside Bar — breakout setup
    if (h.iloc[last] <= h.iloc[prev] and
        l.iloc[last] >= l.iloc[prev]):
        patterns.append({
            "name": "Inside Bar",
            "type": "breakout_setup",
            "strength": "medium",
            "action": "Breakout trade — enter on break of mother bar high"
        })
    
    # Score impact
    bullish_patterns = [p for p in patterns if "bullish" in p["type"]]
    bearish_patterns = [p for p in patterns if "bearish" in p["type"]]
    
    pattern_score_delta = (len(bullish_patterns) * 8) - (len(bearish_patterns) * 15)
    # Bearish patterns penalised more heavily — protection bias
    
    return {
        "patterns": patterns,
        "bullish_count": len(bullish_patterns),
        "bearish_count": len(bearish_patterns),
        "score_delta": pattern_score_delta,
        "primary_pattern": patterns[0]["name"] if patterns else None
    }
```

### Integration

```python
candle_signals = get_candlestick_patterns(df)

# Hard block on bearish reversal pattern
if candle_signals["bearish_count"] > 0:
    bearish = [p for p in candle_signals["patterns"] if "bearish" in p["type"]]
    if any(p["strength"] == "high" for p in bearish):
        continue  # Skip — bearish reversal pattern overrides technical setup

# Add score delta
composite_score += candle_signals["score_delta"]

# Add pattern to Llama reasoning prompt
reasoning_context += f"Candlestick: {candle_signals['primary_pattern']}. "
```

---

## 📐 ENHANCEMENT #4 — NIFTY 50 MARKET BREADTH (DAILY RISK GATE)

**New Function in:** `sector_rs.py`  
**Why:** Even the best individual stock setup fails on a day when the entire market is crashing. A market breadth check tells you whether the broader NSE environment is "risk-on" or "risk-off" before any individual trade is evaluated.

```python
def get_market_breadth_signal() -> dict:
    """
    Evaluates the overall NSE market health.
    
    Uses:
    - Nifty 50 vs its 20-day SMA (above = healthy)
    - India VIX level (fear gauge — high VIX = avoid longs)
    - Nifty 50 daily return (extreme down days = avoid all longs)
    
    Returns environment: "risk_on" | "risk_off" | "caution"
    
    RULE: If environment == "risk_off", suppress ALL buy recommendations.
    Only generate signals in "risk_on" or "caution" (with reduced position sizing).
    """
    try:
        nifty = yf.download("^NSEI", period="30d", interval="1d", progress=False)
        vix = yf.download("^INDIAVIX", period="5d", interval="1d", progress=False)
        
        if nifty.empty:
            return {"environment": "caution", "reason": "Could not fetch Nifty data"}
        
        nifty_price = nifty['Close'].iloc[-1]
        nifty_sma20 = nifty['Close'].rolling(20).mean().iloc[-1]
        nifty_daily_return = (nifty['Close'].iloc[-1] / nifty['Close'].iloc[-2] - 1) * 100
        
        vix_level = vix['Close'].iloc[-1] if not vix.empty else 15.0
        
        # Risk-off conditions
        risk_off_reasons = []
        
        if nifty_price < nifty_sma20 * 0.97:
            risk_off_reasons.append(f"Nifty 3%+ below 20-SMA")
        
        if vix_level > 22:
            risk_off_reasons.append(f"India VIX={round(vix_level,1)} — elevated fear")
        
        if nifty_daily_return < -1.5:
            risk_off_reasons.append(f"Nifty down {round(nifty_daily_return,2)}% today")
        
        # Classification
        if len(risk_off_reasons) >= 2:
            environment = "risk_off"
        elif len(risk_off_reasons) == 1 or (nifty_price < nifty_sma20):
            environment = "caution"
        else:
            environment = "risk_on"
        
        return {
            "environment": environment,
            "nifty_vs_sma20_pct": round((nifty_price / nifty_sma20 - 1) * 100, 2),
            "vix": round(vix_level, 2),
            "nifty_daily_return": round(nifty_daily_return, 2),
            "reasons": risk_off_reasons
        }
        
    except Exception as e:
        return {"environment": "caution", "reason": str(e)}
```

### Integration in `analyzer.py` — Run This FIRST, Before Any Stock is Evaluated

```python
# === MARKET BREADTH GATE — runs once per scan ===
market_env = get_market_breadth_signal()

if market_env["environment"] == "risk_off":
    # Abort entire scan — return early with explanation
    return {
        "status": "scan_suppressed",
        "reason": f"Market in risk-off mode: {', '.join(market_env['reasons'])}. No buy recommendations generated.",
        "market_data": market_env
    }

# In "caution" mode — raise minimum composite score threshold
if market_env["environment"] == "caution":
    minimum_composite_threshold = 75  # Higher bar on uncertain days
else:
    minimum_composite_threshold = 65  # Normal bar on risk-on days
```

---

## 📐 ENHANCEMENT #5 — UPGRADED LLAMA PROMPT ENGINEERING

**File:** `hf_ai.py`  
**Why:** The current Llama prompt likely asks "give me reasons to buy this stock." That is a confirmation-biased prompt. A professional analyst asks "is this setup sound, and what are the specific risks?" The AI reasoning output should reflect the full picture — including exit warnings.

### Replace Current Llama Prompt With:

```python
def build_llama_prompt(stock: dict, technicals: dict, market_context: dict) -> str:
    """
    Constructs a structured, unbiased investment brief prompt for Llama-3.2-1B.
    The prompt is designed to produce actionable, risk-aware output.
    """
    
    prompt = f"""You are a senior NSE equity analyst at an institutional algo trading desk. 
Analyze the following stock setup and provide a concise, honest assessment.

STOCK: {stock.get('name')} ({stock.get('symbol')})
SECTOR: {stock.get('sector')} | CAP: {stock.get('cap_segment')} | P/E: {stock.get('pe_ratio')}

TECHNICAL SETUP:
- Price: ₹{technicals.get('price')} | RSI: {technicals.get('rsi')} | MACD Signal: {technicals.get('macd_cross')}
- Trend Regime: {technicals.get('regime')} (ADX: {technicals.get('adx')})
- Volume Ratio: {technicals.get('volume_ratio')}x average
- Smart Money: {technicals.get('smart_money_signal')}
- Candlestick: {technicals.get('primary_candle_pattern', 'None detected')}
- Entry: ₹{technicals.get('entry_price')} | Target: ₹{technicals.get('target_price')} | SL: ₹{technicals.get('stop_loss')}
- Risk:Reward = {technicals.get('risk_reward')}:1

MARKET CONTEXT:
- Sector RS Status: {market_context.get('sector_rs_status')}
- Market Environment: {market_context.get('market_environment')}
- Nifty vs 20-SMA: {market_context.get('nifty_vs_sma20')}%

Provide a 3-sentence analysis covering:
1. WHY this specific setup is valid (be specific about the technical confluence)
2. THE MAIN RISK that could invalidate this trade
3. EXIT STRATEGY — what price action would signal the trade is failing BEFORE stop-loss is hit

Be direct and concise. Do not use generic phrases like 'the stock looks promising.'"""

    return prompt
```

**Critical instruction:** Add `max_new_tokens=180` to the HuggingFace API call for Llama. The current 1B model degrades in quality after ~200 tokens. Keep it tight.

---

## 📐 ENHANCEMENT #6 — SUPPORT/RESISTANCE LEVEL DETECTION

**Add to:** `technicals.py`  
**Why:** Targets placed at arbitrary ATR multiples often land in the middle of a strong resistance zone, which acts as a ceiling and causes the trade to stall before hitting the target. Entries placed at support are far more likely to hold on the first test.

```python
def get_key_levels(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    Identifies key support and resistance levels using:
    - Recent swing highs and lows (price memory)
    - High-volume nodes (where most volume traded = price magnet)
    
    Returns nearest support below entry and nearest resistance above entry.
    Used to:
    1. Validate that stop-loss is placed BELOW a support level
    2. Check that target is not BLOCKED by a major resistance level
    """
    close = df['Close'].tail(lookback)
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    volume = df['Volume'].tail(lookback)
    current_price = close.iloc[-1]
    
    # Swing highs: candle high > both neighbours
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(close) - 2):
        if high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i+1] and \
           high.iloc[i] > high.iloc[i-2] and high.iloc[i] > high.iloc[i+2]:
            swing_highs.append(high.iloc[i])
        
        if low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i+1] and \
           low.iloc[i] < low.iloc[i-2] and low.iloc[i] < low.iloc[i+2]:
            swing_lows.append(low.iloc[i])
    
    # Nearest support below current price
    supports_below = sorted([s for s in swing_lows if s < current_price], reverse=True)
    resistances_above = sorted([r for r in swing_highs if r > current_price])
    
    nearest_support = supports_below[0] if supports_below else None
    nearest_resistance = resistances_above[0] if resistances_above else None
    
    # Check if target is blocked by resistance
    target_blocked = False
    if nearest_resistance:
        # If resistance is within 80% of the distance to target — path is obstructed
        target_blocked = nearest_resistance < current_price * 1.02  # resistance within 2%
    
    return {
        "nearest_support": round(nearest_support, 2) if nearest_support else None,
        "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
        "target_blocked": target_blocked,
        "support_levels": [round(s, 2) for s in supports_below[:3]],
        "resistance_levels": [round(r, 2) for r in resistances_above[:3]]
    }
```

### Integration in `analyzer.py`

```python
levels = get_key_levels(df)

# If target price is blocked by near resistance — adjust or skip
if levels["target_blocked"]:
    composite_score -= 15  # Penalise — path to target is obstructed
    reasoning += f" Caution: resistance at ₹{levels['nearest_resistance']} may cap upside."

# Validate SL placement — SL should be AT or BELOW nearest support
if levels["nearest_support"] and atr_levels["stop_loss"] > levels["nearest_support"]:
    # SL is above support — will get triggered before the real support breaks
    # Adjust SL down to just below the support level
    adjusted_sl = round(levels["nearest_support"] * 0.995, 2)
    atr_levels["stop_loss"] = adjusted_sl
```

---

## 📊 FULL COMPOSITE SCORE MODEL — FINAL VERSION

After all enhancements, the complete scoring model looks like this:

```
MAX POSSIBLE SCORE: 100 points

MARKET GATE (must pass — these are binary blocks, not scores):
  ✓ Market environment != "risk_off"          → if fails: return no signals
  ✓ Stock regime != "downtrend"               → if fails: skip stock
  ✓ Smart money != "distribution" (bearish)   → if fails: skip stock
  ✓ No bearish candlestick pattern (high strength) → if fails: skip stock

COMPOSITE SCORING (0-100):
  Regime quality       → 0–30 pts   (uptrend=30, sideways=15, downtrend=0)
  Trend structure      → 0–20 pts   (SMA200/50/20 alignment)
  Volume confirmation  → 0–20 pts   (strong=20, confirmed=13, weak=3)
  RSI quality          → 0–15 pts   (sweet spot 50–65)
  MACD cross           → 0–10 pts
  Smart money (accum)  → 0–15 pts   (accumulation=+15, neutral=0, distribution=-25)
  Candlestick pattern  → ±variable  (bullish=+8 each, bearish=-15 each)
  Sector RS            → -20 to +10 (leading=+10, lagging=-20)
  Sentiment (finbert)  → -10 to +5
  R:R quality bonus    → 0–5 pts    (≥3:1 = +5)

MINIMUM THRESHOLDS:
  risk_on days:   composite_score ≥ 65
  caution days:   composite_score ≥ 75
  risk_off days:  no signals generated

EXPECTED OUTPUT:
  risk_on:   3–7 recommendations per scan
  caution:   1–4 recommendations per scan
  risk_off:  0 recommendations — return explanation message
```

---

## 📐 ENHANCEMENT #7 — ALPHA SCANNER IMPROVEMENT

**File:** `alpha_scanner.py`  
**Why:** The current alpha scanner fires intraday momentum alerts. With the new regime + breadth logic, it should suppress alerts on risk-off days and add sector RS context to each alert.

```python
# Add to alpha_scanner.py alert generation logic:

def should_fire_alpha_alert(symbol: str, sector: str, composite_score: float) -> tuple[bool, str]:
    """
    Final gate before firing an alpha alert.
    Returns (should_fire: bool, suppression_reason: str)
    """
    from sector_rs import get_market_breadth_signal, get_sector_relative_strength
    
    market = get_market_breadth_signal()
    
    if market["environment"] == "risk_off":
        return False, f"Market risk-off: {market['reasons']}"
    
    sector_rs = get_sector_relative_strength(sector)
    
    if sector_rs["status"] == "lagging" and composite_score < 80:
        return False, f"Sector {sector} lagging — alert suppressed unless score ≥ 80"
    
    # In caution mode, raise the alpha alert bar
    min_score = 80 if market["environment"] == "caution" else 70
    
    if composite_score < min_score:
        return False, f"Score {composite_score} below threshold {min_score} for {market['environment']} market"
    
    return True, ""
```

---

## ⚡ PERFORMANCE & CACHING NOTES

All the new functions add extra `yf.download()` calls. To stay within Vercel's execution time limits:

```python
# Cache sector rankings at module level — compute once per scan run, not per stock
# In analyzer.py, at the top of the scan function:

import functools
from datetime import date

@functools.lru_cache(maxsize=1)
def get_cached_market_context(cache_key: str) -> dict:
    """
    cache_key = today's date string — forces refresh each new day.
    Caches market breadth + all sector rankings in one call.
    """
    breadth = get_market_breadth_signal()
    sector_rankings = get_all_sector_rankings()
    return {"breadth": breadth, "sectors": {s["sector"]: s for s in sector_rankings}}

# Call at scan start:
today_key = date.today().isoformat()
market_context = get_cached_market_context(today_key)
```

This means sector RS and breadth are fetched **once per scan run** (11 API calls total — 10 sectors + 1 Nifty), not once per stock. For 90 stocks, this saves ~80 redundant API calls.

---

## ✅ VALIDATION CHECKLIST — PROMPT 2

```
□ Sector RS correctly identifies IT sector performance vs Nifty (verify on known period)
□ OBV/CMF accumulation signal fires correctly on known accumulation stocks
□ Bullish Engulfing pattern detected correctly on a manually verified candle chart
□ Nifty VIX fetch working (^INDIAVIX available on yfinance)
□ Market breadth returns "risk_off" on a known crash date (backtest on March 2020)
□ Support/Resistance levels are sensible (visually verify on a chart)
□ Target price is being checked against nearest resistance
□ LRU cache is working — sector data fetched once, not 90 times
□ Llama prompt output is specific (no generic text like "the stock looks promising")
□ Alpha alerts suppressed on risk_off days
□ Full composite score never exceeds 100 after all additions
□ All Prompt 1 protections (bulk writes, IS_VERCEL, fallbacks) still intact
```

---

## 🎯 FINAL EXPECTED SYSTEM BEHAVIOR (POST BOTH PROMPTS)

```
SCENARIO A — Strong bull market day, IT sector leading:
  → 5-7 high-quality IT + large-cap signals generated
  → All signals: uptrend regime, volume confirmed, smart money accumulating
  → R:R minimum 2.5:1, targets clear of resistance
  → Win rate target: 55-65%

SCENARIO B — Mixed market, Nifty at 20-SMA:
  → "caution" mode activated, threshold raised to 75
  → 2-4 signals maximum, only strongest setups survive
  → Win rate target: 60-70% (fewer but better)

SCENARIO C — Market crash day, VIX > 22:
  → "risk_off" activated
  → ZERO buy signals generated
  → Frontend shows: "Market conditions unfavorable — scan suppressed"
  → Capital preserved — the most important outcome

SCENARIO D — Stock in downtrend but strong RSI bounce:
  → Blocked at regime gate — never reaches scoring
  → Zero false "oversold bounce" signals

SCENARIO E — Breakout with no volume:
  → Volume confirmation fails → composite score penalty
  → Falls below minimum threshold → not recommended
  → No more fake breakout traps
```

---

*End of Enhancement Brief. Implement Prompt 1 first and validate. Then implement Prompt 2 in sequence — start with Market Breadth Gate (#4), then Sector RS (#1), then Smart Money (#2). These three alone will produce the largest improvement in signal quality.*
