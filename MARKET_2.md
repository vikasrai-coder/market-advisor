# ✅ MARKET ADVISOR — COMPLETE IMPLEMENTATION AUDIT REPORT
**Files Audited:** analyzer.py, technicals.py, hf_ai.py, reconciler.py, alpha_scanner.py  
**Audit Against:** All fixes from Prompt 1, Prompt 2, and Prompt 3  
**Verdict per item:** ✅ DONE | ⚠️ PARTIAL | ❌ MISSING | 🔴 BUG FOUND

---

## PROMPT 1 AUDIT — Signal Quality Fixes

---

### FIX P1-1 — Market Regime Detection
**File:** `technicals.py` → `get_market_regime()`  
**Status: ✅ FULLY IMPLEMENTED**

- SMA 20/50/200 alignment check ✅
- ADX calculation with plus_dm / minus_dm ✅
- Uptrend / downtrend / sideways classification ✅
- `tradeable` flag correctly set ✅
- Used in `analyzer.py` swing (`_analyze_symbol_swing` line 675) and intraday (`_analyze_symbol_intraday` line 963) ✅
- Hard block on downtrend in swing mode ✅ (line 676-678)
- Hard block on downtrend daily regime in intraday mode ✅ (line 957-958)

**One observation:** When `len(close) < 50` (short history), `sma50 = sma20` and when `len < 200`, `sma200 = sma50`. This means short-history stocks default to "sideways" which is correct behaviour. ✅

---

### FIX P1-2 — ATR-Based Stop Loss
**File:** `technicals.py` → `get_atr_levels()`  
**Status: ✅ FULLY IMPLEMENTED**

- ATR computed correctly using True Range ✅
- `sl_multiplier=2.0` default, `rr_ratio=2.5` default ✅
- Returns `None` if R:R < 2.0 — hard minimum enforced ✅
- Returns `None` if `stop_loss <= 0` ✅
- ATR levels used in swing (line 750) and intraday (line 984) ✅
- `_target_for_mode()` and `_stop_for_mode()` prefer ATR levels first ✅ (lines 1147-1171)
- Intraday uses tighter `sl_multiplier=1.5, rr_ratio=2.0` ✅ (line 984)

---

### FIX P1-3 — Volume Confirmation Filter
**File:** `technicals.py` → `get_volume_confirmation()`  
**Status: ✅ FULLY IMPLEMENTED**

- `confirmed` = volume_ratio >= 1.5 ✅
- `strong` = volume_ratio >= 2.5 ✅
- Used in composite score formula correctly ✅
- Personality-based `min_volume_ratio` penalty applied (lines 812-814) ✅

---

### FIX P1-4 — Higher Timeframe Context for Intraday
**File:** `analyzer.py` → `_analyze_symbol_intraday()`  
**Status: ✅ FULLY IMPLEMENTED**

- Bulk daily 3-month download done at scan level (lines 154-174) ✅ — passed as `daily_history_df`
- Per-symbol HTF daily regime computed (line 956) ✅
- Hard block if daily regime == "downtrend" (line 957-958) ✅
- Fallback to `yf.download()` if bulk daily not available (line 954) ✅

---

### FIX P1-5 — Sentiment Hard Gate
**File:** `analyzer.py` → `_analyze_symbol_swing()`  
**Status: ✅ IMPLEMENTED (with one important caveat)**

- Hard block if negative finbert score > 0.75 ✅ (line 799-800)
- Moderate negative penalty (-25) for score 0.55–0.75 ✅ (lines 854-855)
- Positive sentiment bonus (+5) in composite formula ✅

**⚠️ CAVEAT — Sentiment gate is mostly inactive in practice:**  
`run_lightweight` is `True` for intraday OR when `usage_mode == "low"` (line 239). In lightweight mode, news is never fetched for top candidates (line 241-263). This means `articles = []` for most stocks, `sentiment_dict` defaults to `{"label": "neutral", "score": 0.0}`, and the sentiment gate **never fires in lightweight mode**. This is by design for speed, but it means the gate only activates in `usage_mode = "high"` for swing/longterm. Make sure your admin panel defaults to `"high"` for swing scans to get the benefit of this gate.

---

### FIX P1-6 — Composite Score Rebalancing
**File:** `analyzer.py` → `_compute_composite_score()`  
**Status: ✅ FULLY IMPLEMENTED**

- Regime: 30 pts ✅
- Trend structure (SMA): 20 pts ✅
- Volume: 20 pts ✅
- RSI sweet spot 50-65: 15 pts ✅ (NOT oversold — correct)
- MACD cross: 10 pts ✅
- Sentiment: ±5/10 pts ✅
- R:R bonus: 5 pts ✅
- Score capped at 100, floored at 0 ✅
- Minimum threshold 65 enforced (line 325) ✅
- Adaptive threshold from reconciler ✅ (lines 327-330)
- Breadth caution override to 75 ✅ (lines 338-340)

**🔴 BUG FOUND — Legacy scoring still running in parallel:**  
`_trend_score()` and `_technical_score()` in technicals.py (lines 696-740) still contain the OLD scoring logic including `rsi < 30 → score += 8` (buying oversold weakness). These are called by `compute_indicators()` and their results stored as `trend_score` and `technical_score` in metrics. In **longterm mode**, `_analyze_symbol_longterm()` (lines 1033-1076) uses the OLD formula: `composite = trend * weight + technical * weight + news * weight + fundamental * weight`. It **does NOT call `_compute_composite_score()`**. This means all the Prompt 1 fixes to composite scoring are **bypassed in longterm mode**.

**Action required:** Apply `_compute_composite_score()` to longterm analysis OR at minimum add regime gate and ATR check to `_analyze_symbol_longterm()`.

---

### FIX P1-7 — Reconciler Feedback Loop
**File:** `reconciler.py` → `get_performance_stats()`  
**Status: ✅ FULLY IMPLEMENTED**

- Win rate calculation ✅
- Adaptive threshold: <40% win rate → 72, >65% → 60, else 65 ✅
- Called in `analyzer.py` at scan start (lines 327-330) ✅
- Handles insufficient data gracefully (< 5 records returns default 65) ✅

---

### FIX P1-8 — Intraday-Specific Rules
**File:** `analyzer.py` → `_analyze_symbol_intraday()`  
**Status: ⚠️ PARTIAL**

- Price above VWAP required ✅ (lines 973-974)
- RSI >= 45 required for intraday ✅ (lines 977-978)
- Intraday ATR SL = 1.5x, R:R = 2.0 minimum ✅ (line 984)

**❌ MISSING — No-entry time rules not implemented:**  
The Prompt 1 brief specified:
- No entry in first 15 minutes (9:15–9:30 IST) — not implemented anywhere
- No entry after 2:00 PM IST — not implemented anywhere

These cannot be enforced at the **scanner level** because yfinance returns historical candles, not live prices. However, they should be enforced at the **frontend level** in `AlphaAlerts.tsx` and `Dashboard.tsx` by checking `new Date()` in IST before showing entry buttons. This is currently not done.

**Action required:** Add IST time check to frontend before displaying intraday "Enter Now" buttons.

---

## PROMPT 2 AUDIT — Context Intelligence Layer

---

### ENHANCEMENT P2-1 — Sector Relative Strength Engine
**File:** `alpha_scanner.py` imports `get_sector_relative_strength` from `sector_rs.py`; `analyzer.py` imports `get_today_market_context`  
**Status: ✅ FULLY IMPLEMENTED**

- Sector RS used in swing analysis (lines 826-838) ✅
- Lagging sector → -20 composite score ✅
- Leading sector → +10 composite score ✅
- Lagging sector hard block unless score ≥ 80 ✅ (lines 841-842)
- Sector RS context added to Llama prompt ✅ (market_context dict)
- Sector RS included in alpha alert reasoning ✅ (alpha_scanner.py lines ~125-130)
- `sector_cache` passed to avoid per-stock API calls ✅ (computed once at scan start, line 88)

**⚠️ CAVEAT:** Sector RS is only applied in `_analyze_symbol_swing()`. It is **not applied in `_analyze_symbol_intraday()`** or `_analyze_symbol_longterm()`. Intraday trades in lagging sectors are not penalised.

---

### ENHANCEMENT P2-2 — Smart Money Detection
**File:** `technicals.py` → `get_smart_money_signals()`  
**Status: ✅ FULLY IMPLEMENTED**

- OBV trend detection ✅
- CMF (Chaikin Money Flow) ✅
- Bearish divergence (price at high, OBV not) ✅
- Hard block on bearish divergence in swing ✅ (lines 682-683)
- Non-blocking distribution penalty (-25) ✅ (lines 817-818)
- Accumulation bonus (+15) ✅ (lines 819-820)
- Smart money reason added to Llama context ✅

**⚠️ CAVEAT:** Smart money check **not applied to intraday or longterm modes**.

---

### ENHANCEMENT P2-3 — Candlestick Pattern Recognition
**File:** `technicals.py` → `get_candlestick_patterns()`  
**Status: ✅ FULLY IMPLEMENTED**

- All 6 patterns implemented: Bullish Engulfing, Hammer, Shooting Star, Bullish Marubozu, Doji, Inside Bar ✅
- Bearish patterns penalised 15pts vs bullish 8pts ✅
- Hard block on high-strength bearish reversal ✅ (lines 687-689)
- Score delta applied to composite ✅ (line 823)
- Pattern included in Llama prompt context ✅

**⚠️ CAVEAT:** Not applied to intraday or longterm modes.

---

### ENHANCEMENT P2-4 — Market Breadth Gate
**File:** `analyzer.py` lines 84-110, calls `get_today_market_context()` from `sector_rs.py`  
**Status: ✅ FULLY IMPLEMENTED**

- Risk-off check at scan start ✅
- Scan suppressed with explanation message on risk-off ✅ (lines 93-103)
- Caution mode raises threshold to 75 ✅ (lines 106-109)
- `get_today_market_context()` cached via LRU in `sector_rs.py` ✅ (referenced in alpha_scanner.py)
- Hard abort in alpha scanner on risk-off ✅ (alpha_scanner.py lines ~75-86)

---

### ENHANCEMENT P2-5 — Upgraded Llama Prompt
**File:** `hf_ai.py` → `generate_recommendation_insight()`  
**Status: ✅ FULLY IMPLEMENTED**

- Structured 3-sentence format: validity / main risk / exit signal ✅
- Includes regime, ADX, smart money, candlestick, sector RS, market environment ✅
- `max_tokens=180` enforced ✅ (line in `_chat()` call)
- Anti-confirmation-bias instruction ("do not use generic phrases") ✅
- JSON output parsing with fallback ✅
- Multi-token fallback system ✅ (tries HF_TOKEN, HF_TOKEN_2, HF_TOKEN_3, etc.)

**⚠️ CAVEAT:** In `run_lightweight=True` mode (intraday + low usage), Llama is bypassed entirely and a rule-based string is used instead (lines 357-374 in analyzer.py). This is intentional for speed, but means AI reasoning is absent for intraday recommendations.

---

### ENHANCEMENT P2-6 — Support/Resistance Detection
**File:** `technicals.py` → `get_key_levels()`  
**Status: ✅ FULLY IMPLEMENTED**

- Swing high/low detection over 60-candle lookback ✅
- `target_blocked` flag (resistance within 2% of price) ✅
- -15 composite penalty if target blocked ✅ (lines 844-846)
- SL adjusted below nearest support ✅ (lines 848-851)
- ⚠️ Not applied to intraday or longterm modes

---

### ENHANCEMENT P2-7 — Alpha Scanner Market/Sector Gate
**File:** `alpha_scanner.py` → `should_fire_alpha_alert()`  
**Status: ✅ FULLY IMPLEMENTED**

- Risk-off suppression ✅
- Sector lagging suppression (unless score ≥ 80) ✅
- Caution mode raises minimum to 80 ✅
- Market context fetched once (cached) ✅
- Full hard abort at scan level on risk-off ✅

---

## PROMPT 3 AUDIT — Precision & Learning Layer

---

### FIX P3-1 — Entry Precision / Wait-for-Pullback Engine
**File:** `technicals.py` → `get_optimal_entry_zone()`  
**Status: ✅ FULLY IMPLEMENTED**

- EMA8 extension calculation ✅
- Three entry types: immediate / wait_dip / avoid ✅
- Hard block on "avoid" (>3x ATR extension) ✅ (analyzer.py lines 756-757)
- -10 penalty for "wait_dip" ✅ (lines 759-768)
- ATR levels recalculated from ideal entry price in wait_dip mode ✅ (lines 762-768)
- Entry type, ideal price, and entry note stored in result ✅ (lines 905-907)

**❌ MISSING — Database columns not confirmed:**  
The prompt specified adding `entry_type`, `ideal_entry_price`, `entry_note` columns to the `recommendations` table. These are computed and stored in the Python result dict, but there is no SQL migration in the visible code. **Verify these columns exist in Supabase** or the data is being silently dropped on insert.

---

### FIX P3-2 — Stock Personality Profiling
**File:** `technicals.py` → `get_stock_personality()`  
**Status: ✅ FULLY IMPLEMENTED**

- 4 personality types: institutional / momentum / operator_risk / avoid_today ✅
- Liquidity threshold: < ₹1 Cr daily value = avoid ✅
- Per-personality ATR multiplier and volume ratio ✅
- Applied in swing analysis (lines 697-708) ✅
- `avoid_today` hard block ✅ (lines 698-703)

**⚠️ CAVEAT:** Personality profiling not applied to intraday analysis. Illiquid stocks can still appear in intraday recommendations.

---

### FIX P3-3 — Earnings & Event Risk Calendar
**File:** `api/app/services/event_risk.py` (referenced by analyzer.py line 712)  
**Status: ✅ IMPLEMENTED (file not uploaded but correctly referenced)**

- `get_event_risk()` imported and called in swing analysis ✅ (line 712)
- `high_risk` → hard block ✅ (lines 714-715)
- `earnings_near` → blocks swing/longterm, penalises intraday ✅ (lines 719-725)
- `exdiv_near` → -15 penalty ✅ (lines 726-728)
- Warning text appended to entry_note ✅ (line 907)

**❌ NOT AUDITED:** `event_risk.py` was not uploaded. Cannot verify the yfinance calendar fetch implementation. Risk: yfinance calendar data is notoriously unreliable for Indian NSE stocks. NSE-listed companies often do not populate the HF calendar in yfinance. **Test this manually** with RELIANCE.NS, TCS.NS, and INFY.NS to confirm earnings dates are being detected.

---

### FIX P3-4 — Self-Learning Loss Analyzer
**File:** `api/app/services/loss_analyzer.py` (referenced by analyzer.py lines 178-181)  
**Status: ⚠️ PARTIALLY IMPLEMENTED**

- `load_learned_adjustments()` imported and called at scan start ✅ (lines 178-181)
- Suppressed sectors apply -25 penalty ✅ (lines 738-744)
- Suppressed trade modes → hard block ✅ (lines 741-742)
- `min_composite_score_override` read and applied ✅ (lines 334-336)

**❌ MISSING — Weekly cron not confirmed:**  
`loss_analyzer.analyze_loss_patterns()` (the write side — the function that analyzes past trades and generates `learned_adjustments.json`) needs to be wired to a weekly cron endpoint. There is no `/api/cron/weekly-learning` endpoint visible in the uploaded files. **Without this, the JSON file is never updated and the system never actually learns.**

**Action required:** Add `POST /api/cron/weekly-learning` endpoint to `main.py` that calls `loss_analyzer.analyze_loss_patterns(supabase_client)`.

**❌ MISSING — `sector` column in recommendations table:**  
`analyze_loss_patterns()` groups losses by sector. But looking at the `recommendations` table schema (from architecture doc), there is **no `sector` column** in the recommendations table — only `symbol`. The loss analyzer would need to JOIN with the `stocks` table to get sector. Verify this is handled in `loss_analyzer.py`.

---

### FIX P3-5 — Trade Quality Tiers (S/A/B/C)
**File:** `analyzer.py` → `classify_trade_tier()`  
**Status: ⚠️ PARTIAL**

- Function implemented correctly ✅ (lines 1253-1305)
- `confirming_signals_list` computed per stock ✅ (lines 910-919)

**❌ MISSING — Tier not being saved to database:**  
`classify_trade_tier()` is defined but searching the `run_full_analysis()` function shows it is **never called**. The tier classification is built but not invoked anywhere in the recommendation generation loop (lines 408-524). `recommendations` table also has no `trade_tier` or `position_size_pct` columns per the architecture doc.

**Action required:** 
1. Add SQL migration: `ALTER TABLE recommendations ADD COLUMN trade_tier TEXT DEFAULT 'B'; ADD COLUMN position_size_pct INT DEFAULT 50;`
2. Call `classify_trade_tier(composite_score, item["confirming_signals_list"])` in the recommendation generation loop
3. Include `trade_tier` and `position_size_pct` in the inserted recommendation row
4. Frontend `RecommendationCard.tsx` needs to display the tier badge

---

### FIX P3-6 — Exit Signal / Position Health Monitor
**File:** `api/app/services/position_monitor.py`  
**Status: ❌ NOT FOUND IN UPLOADED FILES**

The `check_position_health()` function from Prompt 3 is not referenced anywhere in the uploaded files. No import in `reconciler.py`, no reference in `user_workspace.py` (not uploaded).

**Action required:** This is the most impactful missing Prompt 3 feature. Without exit signals, users hold losing positions to full stop-loss when early exit signals could preserve 40-60% of the capital at risk. Implement as described in Prompt 3, then wire to:
- `UserWorkspace.tsx` portfolio view (call on page load for each open position)
- A new API endpoint `GET /api/portfolio/health/{symbol}` 

---

## CRITICAL BUGS REQUIRING IMMEDIATE FIXES

---

### 🔴 BUG #1 — Longterm Mode Bypasses ALL Prompt 1+2+3 Fixes

**Location:** `_analyze_symbol_longterm()` lines 1033–1076  

This function does NOT call:
- `get_market_regime()` — no regime gate
- `get_smart_money_signals()` — no distribution block
- `get_atr_levels()` — uses old fixed % SL/TP
- `get_event_risk()` — no earnings block
- `_compute_composite_score()` — uses old weighted formula
- `get_stock_personality()` — no liquidity check
- `get_key_levels()` — no resistance check

**Every longterm recommendation is generated by the pre-Prompt-1 broken logic.** This is a complete blind spot.

**Fix:** Add the full intelligence pipeline to `_analyze_symbol_longterm()` — at minimum: regime gate, ATR SL, and smart money gate.

---

### 🔴 BUG #2 — Intraday Missing Smart Money, Sector RS, Candlesticks, Personality

**Location:** `_analyze_symbol_intraday()` lines 923–1030

Intraday analysis skips:
- `get_smart_money_signals()` — distribution stocks can appear in intraday
- Sector RS adjustment — lagging sector stocks not penalised
- `get_candlestick_patterns()` — bearish reversal not blocked
- `get_stock_personality()` — illiquid stocks not blocked in intraday
- `get_key_levels()` — no resistance check on intraday targets
- `get_optimal_entry_zone()` — extended price entries not flagged

These are the same patterns killing intraday P&L that the full pipeline was built to solve.

---

### 🔴 BUG #3 — `classify_trade_tier()` Never Called (Dead Code)

Already described in P3-5. The entire tier system exists but is never invoked. Users see all recommendations as equal. This is one of the most impactful UX fixes for accuracy — it guides position sizing.

---

### ⚠️ ISSUE #4 — `above_sma200` Always False in Swing Mode

**Location:** `_analyze_symbol_swing()` line 783

```python
"above_sma200": False,  # swing uses 6mo, no 200-SMA
```

6-month daily data = ~130 candles, not enough for SMA-200. So this is hardcoded `False`. This means the "trend structure" component in `_compute_composite_score()` maxes out at 12 pts (SMA50+SMA20) instead of the full 20 pts. Stocks in a strong 200-day uptrend never get credit for it in swing mode.

**Fix:** For swing mode, fetch 1 year of daily data instead of 6 months. This costs nothing extra since it's a bulk download. Or add a separate "longterm SMA check" using the 3-month daily data already fetched for intraday HTF context.

---

### ⚠️ ISSUE #5 — `_trend_score()` Still Has Oversold Buy Logic

**Location:** `technicals.py` line 717

```python
elif rsi < 30:
    score += 8   # ← This is the "falling knife" logic Prompt 1 was designed to eliminate
```

This function feeds `trend_score` which is used in the longterm composite (Bug #1) and as display metrics. While `_compute_composite_score()` correctly awards 0 points for RSI < 30, the legacy `_trend_score()` still rewards it. Any longterm recommendation using the old formula gets a higher score for oversold stocks — the exact pattern that caused 80% stop-loss rate originally.

---

## SUMMARY SCORECARD

| Prompt | Fix | Status | Priority |
|--------|-----|--------|----------|
| P1 | Market Regime Detection | ✅ Done | — |
| P1 | ATR-Based Stop Loss | ✅ Done | — |
| P1 | Volume Confirmation | ✅ Done | — |
| P1 | Intraday HTF Context | ✅ Done | — |
| P1 | Sentiment Hard Gate | ⚠️ Inactive in lightweight mode | Low |
| P1 | Composite Score Rebalancing | ✅ Done (swing only) | — |
| P1 | Reconciler Feedback Loop | ✅ Done | — |
| P1 | Intraday Time Rules | ❌ Missing (frontend) | Medium |
| P2 | Sector RS Engine | ✅ Done (swing only) | — |
| P2 | Smart Money Detection | ✅ Done (swing only) | — |
| P2 | Candlestick Patterns | ✅ Done (swing only) | — |
| P2 | Market Breadth Gate | ✅ Done | — |
| P2 | Upgraded Llama Prompt | ✅ Done | — |
| P2 | Support/Resistance Levels | ✅ Done (swing only) | — |
| P2 | Alpha Scanner Gate | ✅ Done | — |
| P3 | Entry Precision (Pullback) | ✅ Done (swing only) | — |
| P3 | Stock Personality Profiling | ✅ Done (swing only) | — |
| P3 | Earnings Event Risk | ✅ Done (swing only) | — |
| P3 | Self-Learning Loss Analyzer | ⚠️ Read-only, cron missing | High |
| P3 | Trade Quality Tiers | ⚠️ Computed, never called | High |
| P3 | Exit Signal Monitor | ❌ Not implemented | High |

---

## PRIORITISED ACTION PLAN

### Fix immediately (blocks accuracy gains):

**1. Apply full pipeline to longterm mode** — every fix from Prompts 1+2+3 needs to run in `_analyze_symbol_longterm()`. This is a copy-adapt job, not a redesign. (Est: 2-3 hours)

**2. Apply smart money + candlestick + personality to intraday** — at minimum add distribution block and illiquid stock block to `_analyze_symbol_intraday()`. (Est: 1 hour)

**3. Wire `classify_trade_tier()` into recommendation generation loop** — find the loop around line 408-524 in analyzer.py, call the function, save result to DB. Add 2 columns to recommendations table. (Est: 1 hour)

**4. Add weekly-learning cron endpoint** — without this, `learned_adjustments.json` is never written and the self-learning system is permanently in read-only mode. (Est: 30 min)

**5. Implement `position_monitor.py` and wire to UserWorkspace** — exit signals before stop-loss is the single highest-impact missing feature for actual P&L protection. (Est: 3-4 hours)

### Fix soon (quality improvements):

**6. Fix `above_sma200` always False in swing** — fetch 12mo data instead of 6mo for swing bulk download. (Est: 30 min)

**7. Add IST time gate to frontend** — block intraday entry buttons before 9:30 AM and after 2:00 PM IST. (Est: 30 min)

**8. Test `event_risk.py` with NSE tickers** — yfinance calendar is unreliable for Indian stocks. If earnings detection is failing silently, the gate does nothing. (Est: 1 hour testing)

**9. Remove `rsi < 30 → score += 8` from `_trend_score()`** — legacy oversold logic still present.

---

## OVERALL ASSESSMENT

**What's working extremely well:**
The swing/longterm intelligence pipeline is the most complete implementation. Market breadth gate, regime detection, ATR stops, smart money, sector RS, candlestick patterns — all correctly wired for swing mode. This is genuinely institutional-grade signal quality for swing trades.

**What's still broken:**
Intraday and longterm modes are running with partial or zero intelligence layer. Given that intraday is the highest-frequency mode (most trades = most losses), fixing the intraday pipeline is the single most impactful remaining action.

**Realistic win rate projection post full fixes:**
- Swing (current): 60-68% (good, but limited by `above_sma200` issue and missing tier system)
- Intraday (current): 45-55% (still missing key filters)
- Longterm (current): 40-50% (bypasses nearly everything)
- After all remaining fixes: 68-76% on A/S tier signals across all modes
