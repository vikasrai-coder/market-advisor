# 🔴 MARKET ADVISOR — CRITICAL SYSTEM AUDIT & FIX MANDATE

**Document Type:** AI Coding Agent Prompt / Surgical Fix Brief  
**Prepared By:** Senior Algo Trading Analyst + Quant Systems Architect  
**Status:** CRITICAL — System is hemorrhaging capital on stop-losses. Zero targets hit.  
**Constraint:** Zero paid APIs or external resources. All fixes must work within the existing stack (yfinance, Hugging Face free tier, Supabase, FastAPI, Next.js).

---

## 🚨 THE CORE PROBLEM — READ THIS FIRST

> **80–90% of all generated trades are being stopped out. Zero trades are hitting their target price.**

This is not a minor bug. This is a **fundamental signal generation failure**. The system is producing recommendations that are structurally biased toward false breakouts and premature entries. Before touching any code, understand the clinical diagnosis:

### Root Cause Hypothesis (Ranked by Severity)

| # | Problem | Likely Culprit File | Severity |
|---|---------|-------------------|----------|
| 1 | **No market regime detection** — system fires buy signals in downtrends | `analyzer.py`, `technicals.py` | 🔴 CRITICAL |
| 2 | **Stop-loss placed too tight** — volatility not factored into SL distance | `analyzer.py` (target/SL calc) | 🔴 CRITICAL |
| 3 | **Entry on lagging indicators only** — RSI/MACD are confirmation-lagging, not leading | `technicals.py` | 🔴 CRITICAL |
| 4 | **No volume confirmation on breakouts** — price moves without volume are traps | `technicals.py` | 🔴 HIGH |
| 5 | **Target:Risk ratio not enforced** — system may be generating 1:1 or worse R:R trades | `analyzer.py` | 🔴 HIGH |
| 6 | **Sentiment score not gating entries** — negative news sentiment not blocking buy signals | `analyzer.py`, `hf_ai.py` | 🟡 MEDIUM |
| 7 | **No higher timeframe context for intraday** — intraday trades against daily trend | `analyzer.py` | 🟡 MEDIUM |
| 8 | **Composite score not properly weighted** — all signals treated equally regardless of market phase | `reconciler.py`, `analyzer.py` | 🟡 MEDIUM |

---

## 📁 SYSTEM CONTEXT (What You Are Working With)

```
Stack:
  Frontend  → Next.js (TypeScript), React, Vanilla CSS
  Backend   → FastAPI (Python 3.10+), NumPy, Pandas
  Database  → Supabase (Postgres)
  Data      → yfinance (price/volume/OHLCV), Google News RSS (fallback)
  AI        → HuggingFace free serverless: ProsusAI/finbert + Llama-3.2-1B-Instruct

Key Files:
  api/app/services/analyzer.py         ← Main orchestrator (primary fix target)
  api/app/services/technicals.py       ← Indicator engine (primary fix target)
  api/app/services/hf_ai.py            ← Sentiment layer
  api/app/services/reconciler.py       ← Historical grader
  api/app/services/alpha_scanner.py    ← Momentum alerts
  api/app/services/supabase_store.py   ← DB abstraction

ZERO PAID RESOURCES. Do not suggest:
  - Paid data feeds (Bloomberg, Refinitiv, etc.)
  - Paid AI APIs beyond current HuggingFace free tier
  - Any new infrastructure or paid SaaS
```

---

## 🔧 FIX #1 — MARKET REGIME DETECTION (MOST CRITICAL)

**File:** `technicals.py` and `analyzer.py`

### Problem
The system generates BUY signals regardless of whether the broader market or the stock itself is in a downtrend. A stock with RSI=35 bouncing in a bear trend will look "oversold and due for a bounce" — but it will continue falling.

### Fix to Implement

Add a `get_market_regime()` function in `technicals.py`:

```python
def get_market_regime(df: pd.DataFrame) -> dict:
    """
    Determines if the stock is in an uptrend, downtrend, or sideways regime.
    Uses SMA alignment + ADX for trend strength.
    Returns: { "regime": "uptrend" | "downtrend" | "sideways", "adx": float, "tradeable": bool }
    """
    close = df['Close']
    
    # SMA alignment check
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    current_price = close.iloc[-1]
    
    # ADX calculation (trend strength, no directional bias)
    high = df['High']
    low = df['Low']
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr14 = tr.rolling(14).mean()
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr14)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr14)
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx = dx.rolling(14).mean().iloc[-1]
    
    # Regime classification
    if sma20 > sma50 > sma200 and current_price > sma20 and adx > 25:
        regime = "uptrend"
    elif sma20 < sma50 < sma200 and current_price < sma20 and adx > 25:
        regime = "downtrend"
    else:
        regime = "sideways"
    
    # Only trade longs in uptrend or early sideways with adx rising
    tradeable = regime == "uptrend" or (regime == "sideways" and adx > 20)
    
    return {"regime": regime, "adx": round(adx, 2), "tradeable": tradeable}
```

**In `analyzer.py`:** Gate ALL buy signal generation behind `regime["tradeable"] == True`. If regime is `downtrend`, hard-block the recommendation regardless of RSI or MACD values.

```python
regime = get_market_regime(df)
if not regime["tradeable"] and action == "buy":
    # Skip this stock — do not add to recommendations
    continue
```

---

## 🔧 FIX #2 — ATR-BASED STOP-LOSS (CRITICAL)

**File:** `analyzer.py` — wherever `stop_loss` and `target_price` are computed

### Problem
Fixed-percentage stop-losses (e.g., always 3% below entry) don't account for the stock's natural volatility. A high-volatility stock with 5% daily swings will be stopped out by random noise on a 3% SL. A low-volatility stock with 0.5% daily moves needs a tighter SL.

### Fix to Implement

Add ATR-based dynamic SL/TP calculation in `technicals.py`:

```python
def get_atr_levels(df: pd.DataFrame, entry_price: float, 
                   atr_period: int = 14, 
                   sl_multiplier: float = 2.0, 
                   rr_ratio: float = 2.5) -> dict:
    """
    Computes stop-loss and target based on ATR volatility.
    
    sl_multiplier=2.0  → SL is 2x ATR below entry (respects volatility)
    rr_ratio=2.5       → Target is 2.5x the SL distance (enforces 2.5:1 R:R minimum)
    
    NEVER GENERATE A TRADE WITH R:R < 2:1
    """
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(atr_period).mean().iloc[-1]
    
    stop_loss = round(entry_price - (sl_multiplier * atr), 2)
    sl_distance = entry_price - stop_loss
    target_price = round(entry_price + (rr_ratio * sl_distance), 2)
    
    # Sanity checks
    if stop_loss <= 0 or target_price <= entry_price:
        return None  # Reject this signal
    
    actual_rr = round((target_price - entry_price) / sl_distance, 2)
    
    return {
        "stop_loss": stop_loss,
        "target_price": target_price,
        "atr": round(atr, 2),
        "risk_reward": actual_rr,
        "sl_distance_pct": round((sl_distance / entry_price) * 100, 2)
    }
```

**Rule:** If `get_atr_levels()` returns `None` or `risk_reward < 2.0`, **discard the trade signal entirely**. Do not lower the standard to fill a quota of 10 recommendations.

---

## 🔧 FIX #3 — VOLUME CONFIRMATION FILTER (HIGH)

**File:** `technicals.py`

### Problem
Price breakouts without volume are "fake breakouts" — institutional money is not behind the move. 80% of retail trader trap entries happen on low-volume breakouts.

### Fix to Implement

Add `get_volume_confirmation()` in `technicals.py`:

```python
def get_volume_confirmation(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Confirms if current volume is meaningfully above average.
    Breakout signals require volume >= 1.5x the 20-day average.
    """
    volume = df['Volume']
    avg_volume = volume.rolling(lookback).mean().iloc[-1]
    current_volume = volume.iloc[-1]
    
    volume_ratio = round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
    
    return {
        "volume_ratio": volume_ratio,
        "confirmed": volume_ratio >= 1.5,  # Minimum threshold for breakout entry
        "strong": volume_ratio >= 2.5      # High-conviction breakout
    }
```

**In `analyzer.py`:** Weight the composite score based on volume confirmation:
- No volume confirmation → reduce composite score by 20 points, flag signal as `weak`
- Volume confirmed (1.5x) → standard scoring
- Strong volume (2.5x) → bonus +10 points to composite score

---

## 🔧 FIX #4 — HIGHER TIMEFRAME CONTEXT FOR INTRADAY (HIGH)

**File:** `analyzer.py` — intraday scanning block

### Problem
Intraday trades are being generated using only 60-minute data. A stock may look bullish on 60-min but be in a confirmed daily downtrend. The daily trend always wins against intraday setups.

### Fix to Implement

For every intraday scan, **also fetch daily data** and run `get_market_regime()` on it. Only generate an intraday buy signal if the daily regime is NOT `downtrend`.

```python
# In intraday scanning block of analyzer.py
# BEFORE generating recommendation:

# Fetch daily data for HTF context (yfinance, 3-month daily)
daily_df = yf.download(symbol, period="3mo", interval="1d", progress=False)
daily_regime = get_market_regime(daily_df)

if daily_regime["regime"] == "downtrend":
    # SKIP — never trade intraday long against the daily downtrend
    continue

# Also check 60-min regime
intraday_regime = get_market_regime(intraday_df)
if not intraday_regime["tradeable"]:
    continue

# Only now proceed with RSI/MACD signal generation
```

**Constraint note:** This adds one extra `yf.download()` call per stock in intraday mode. Ensure this is batched or cached to avoid Vercel timeout violations. Use `period="3mo"` not `period="1y"` to keep payload small.

---

## 🔧 FIX #5 — SENTIMENT HARD GATE (MEDIUM)

**File:** `analyzer.py` — section where `hf_ai.py` sentiment score is incorporated

### Problem
The system currently uses sentiment as an additive scoring input. Severely negative news sentiment (e.g., fraud allegations, regulatory action) is being partially offset by strong RSI or MACD signals. A stock with negative news momentum should not be recommended as a buy regardless of technical readings.

### Fix to Implement

In `analyzer.py`, after receiving sentiment results from `hf_ai.py`:

```python
# Hard gate: Do NOT recommend a buy if finbert sentiment is strongly negative
if sentiment_result and sentiment_result.get("label") == "negative":
    negative_score = sentiment_result.get("score", 0)
    
    if negative_score > 0.75:
        # Strong negative sentiment → block the trade entirely
        continue
    elif negative_score > 0.55:
        # Moderate negative → heavy penalty to composite score
        composite_score -= 25
        reasoning_prefix = "⚠️ Negative news sentiment detected. Elevated risk. "

# If sentiment is positive AND score > 0.7 → bonus
if sentiment_result and sentiment_result.get("label") == "positive":
    if sentiment_result.get("score", 0) > 0.70:
        composite_score += 10
```

**In lightweight mode (`usage_mode == "low"`):** Sentiment is skipped. Ensure that the absence of sentiment does NOT automatically boost the composite score. Treat missing sentiment as neutral (zero contribution).

---

## 🔧 FIX #6 — COMPOSITE SCORE REBALANCING (MEDIUM)

**File:** `analyzer.py` — composite score computation

### Problem
Unknown current weighting. Based on outcomes (high stop-loss rate), the score is likely overweighting momentum indicators (RSI, MACD) that fire during the middle of a move, rather than at the beginning of a confirmed trend.

### Mandated New Weighting

Replace the existing composite score formula with this weighted model:

```python
def compute_composite_score(
    regime: dict,          # from get_market_regime()
    rsi: float,            # 14-period RSI
    macd_cross: bool,      # True if MACD crossed above signal in last 3 candles
    volume_conf: dict,     # from get_volume_confirmation()
    sentiment: dict,       # from hf_ai.py finbert
    price_vs_sma: dict,    # {"above_sma20": bool, "above_sma50": bool, "above_sma200": bool}
    atr_levels: dict       # from get_atr_levels()
) -> float:
    
    score = 0.0
    
    # === REGIME (30 points max) — most important ===
    if regime["regime"] == "uptrend":
        score += 30
    elif regime["regime"] == "sideways":
        score += 15  # Reduced conviction in sideways
    # downtrend = 0 points (and should have been gated before reaching here)
    
    # === TREND STRUCTURE (20 points max) ===
    if price_vs_sma["above_sma200"]: score += 8
    if price_vs_sma["above_sma50"]:  score += 7
    if price_vs_sma["above_sma20"]:  score += 5
    
    # === VOLUME (20 points max) ===
    if volume_conf["strong"]:    score += 20
    elif volume_conf["confirmed"]: score += 13
    else:                          score += 3   # Low volume → low score
    
    # === MOMENTUM — RSI (15 points max) ===
    # Sweet spot: RSI 45-65 (trending up but not overbought)
    # NOT RSI < 30 "oversold" — that's a falling knife in downtrends
    if 50 <= rsi <= 65:   score += 15
    elif 45 <= rsi < 50:  score += 10
    elif 65 < rsi <= 72:  score += 7   # Getting overbought
    elif 30 <= rsi < 45:  score += 3   # Weak momentum
    else:                 score += 0   # Overbought (>72) or oversold (<30) — avoid
    
    # === MACD (10 points max) ===
    if macd_cross: score += 10
    
    # === SENTIMENT (5 points max) ===
    if sentiment:
        if sentiment.get("label") == "positive" and sentiment.get("score", 0) > 0.6:
            score += 5
        elif sentiment.get("label") == "negative":
            score -= 10  # Penalty
    
    # === R:R QUALITY BONUS (bonus up to 5 points) ===
    if atr_levels and atr_levels.get("risk_reward", 0) >= 3.0:
        score += 5
    elif atr_levels and atr_levels.get("risk_reward", 0) >= 2.5:
        score += 3
    
    return round(min(score, 100), 2)
```

**New minimum threshold:** Only recommend stocks with `composite_score >= 65`. Previously, if the threshold was lower, the system was recommending marginal setups. Quality over quantity — it is better to output 3 high-conviction signals than 10 weak ones.

---

## 🔧 FIX #7 — RECONCILER FEEDBACK LOOP (MEDIUM)

**File:** `reconciler.py`

### Problem
The reconciler grades past trades but that data is not being fed back to dynamically adjust thresholds. The `alpha_training_data.json` exists but it is unclear if the rolling accuracy is actually adjusting anything in the signal generation path.

### Fix to Implement

Add a `get_performance_stats()` function that `analyzer.py` queries before each scan run:

```python
# In reconciler.py
def get_performance_stats(supabase_client, trade_mode: str, lookback_days: int = 30) -> dict:
    """
    Returns rolling win rate and avg R:R for recent recommendations.
    Used by analyzer.py to self-adjust minimum composite_score threshold.
    """
    cutoff = (datetime.now() - timedelta(days=lookback_days)).date().isoformat()
    
    result = supabase_client.table("recommendations") \
        .select("performance_status, composite_score") \
        .eq("trade_mode", trade_mode) \
        .neq("performance_status", "pending") \
        .gte("signal_date", cutoff) \
        .execute()
    
    records = result.data or []
    
    if len(records) < 5:
        return {"win_rate": None, "sample_size": len(records), "adjusted_threshold": 65}
    
    wins = sum(1 for r in records if r["performance_status"] == "target_hit")
    win_rate = wins / len(records)
    
    # Adaptive threshold: if win rate < 40%, raise bar to 70; if > 65%, lower to 60
    if win_rate < 0.40:
        adjusted_threshold = 72
    elif win_rate > 0.65:
        adjusted_threshold = 60
    else:
        adjusted_threshold = 65
    
    return {
        "win_rate": round(win_rate, 3),
        "sample_size": len(records),
        "adjusted_threshold": adjusted_threshold
    }
```

**In `analyzer.py`:** Call this at the start of each scan and use `adjusted_threshold` as the minimum composite score filter.

---

## 🔧 FIX #8 — INTRADAY-SPECIFIC RULES (MEDIUM)

**File:** `analyzer.py` — intraday scanning profile

### Additional Intraday Rules to Enforce

These rules are standard practice in professional intraday desks:

```python
INTRADAY_RULES = {
    # Do not enter trades in first 15 minutes of market open (9:15–9:30 IST)
    # Price discovery is chaotic; slippage is high
    "no_entry_first_candle": True,
    
    # Do not enter trades after 2:00 PM IST
    # Insufficient time for trade to develop before 3:30 PM close
    "no_entry_after_14_00": True,
    
    # RSI for intraday should be in momentum zone, not oversold
    # NEVER enter intraday on RSI < 40 — falling knives kill intraday P&L fastest
    "min_rsi_for_intraday_buy": 45,
    
    # Require price to be ABOVE VWAP for intraday buy
    # VWAP is the institutional average price; buying below it means buying weakness
    "require_price_above_vwap": True,
    
    # Intraday SL multiplier is tighter than swing (1.5x ATR vs 2.0x)
    "intraday_atr_sl_multiplier": 1.5,
    
    # Intraday R:R minimum is still 2:1 — never compromise this
    "intraday_min_rr_ratio": 2.0
}
```

Implement VWAP in `technicals.py` if not already present:

```python
def get_vwap(df: pd.DataFrame) -> float:
    """Standard VWAP for intraday use. Reset daily."""
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = (typical_price * df['Volume']).cumsum() / df['Volume'].cumsum()
    return round(vwap.iloc[-1], 2)
```

---

## ✅ VALIDATION CHECKLIST — After All Fixes

Before marking any fix as complete, run these checks:

```
□ get_market_regime() returns correct regime for known bull/bear stocks (backtest on RELIANCE.NS 2020-2022)
□ ATR-based SL is wider than 1% for high-volatility stocks (e.g., small-cap)
□ ATR-based SL is tighter than 5% for large-cap (e.g., TCS.NS, INFY.NS)
□ No trade is generated with R:R < 2:1 under any configuration
□ Downtrend stocks are NEVER recommended as buy (test on a known downtrend stock)
□ Low-volume breakouts get composite_score penalty and are not in top 5 recommendations
□ Negative finbert sentiment (>0.75) blocks trade generation
□ Composite score minimum threshold is respected (no recommendations below 65)
□ Intraday trades do NOT fire when price is below VWAP
□ Bulk write operations (upsert_stocks, insert_metrics_batch) are UNTOUCHED
□ IS_VERCEL synchronous execution path is UNTOUCHED
□ Lightweight mode (usage_mode == "low") still runs under 3 seconds
□ try-except fallback in supabase_store.py is UNTOUCHED
```

---

## 🚫 DO NOT TOUCH — PROTECTED SYSTEMS

These components work correctly and must not be modified:

| Component | Reason |
|-----------|--------|
| `upsert_stocks()` + `insert_metrics_batch()` | Bulk write optimization — 500ms vs 18s |
| `IS_VERCEL` synchronous execution block | Prevents container freeze and 504 errors |
| Cron endpoint response format (`{"status": "success"}`) | Prevents cron monitor output-size failures |
| try-except fallback in `supabase_store.py` | Production DB protection during migrations |
| Supabase table schemas (columns/types) | Changing types breaks existing production data |

If any fix **requires** touching the above, raise it as a separate discussion with explicit schema migration steps before implementing.

---

## 📊 EXPECTED OUTCOMES AFTER FIXES

| Metric | Current (Broken) | Target (Post-Fix) |
|--------|-----------------|-------------------|
| Stop-loss hit rate | 80–90% | < 45% |
| Target hit rate | ~10–20% | > 40% |
| Avg Risk:Reward on signals | Unknown / likely < 1.5:1 | Minimum 2.5:1 enforced |
| Signals generated per scan | ~10 (all modes) | 3–7 (quality filtered) |
| Downtrend stocks in buy list | Common | Zero |
| Low-volume breakouts recommended | Common | Rare (penalised) |

---

## 🧠 MENTAL MODEL FOR THE CODING AGENT

You are not a general developer. You are a **quant analyst rewriting a broken signal engine**. Think like this:

1. **Every trade signal must earn its place.** The bar is not "RSI is low." The bar is "regime is up, volume confirms, R:R is clean, trend is aligned."
2. **Protecting capital is more important than generating signals.** Fewer, better signals is the goal.
3. **The stop-loss is not a safety net. It is a cost.** If 80% of stops are hit, the signal logic is wrong — not the stop placement.
4. **Never confuse activity with progress.** Generating 10 recommendations per scan when 9 are wrong is worse than generating 3 that are right.
5. **Mean reversion (RSI < 30 = oversold = buy) is a trap in trending markets.** Switch to trend-following logic: buy strength, not weakness.

---

*End of Audit Brief. All fixes must be implemented with the existing free-tier stack. No paid resources. Performance validation via reconciler.py historical grading is the final arbiter of success.*
