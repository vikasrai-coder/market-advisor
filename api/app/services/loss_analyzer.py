"""Loss Pattern Analyzer — Fix #4 (Prompt 3) — Self-Learning Brain.

Analyzes 30-day rolling stop-loss hits to detect systematic weaknesses:
  - Sectors with win rate < 35% → suppressed_sectors
  - Trade modes underperforming → suppressed_trade_modes
  - Systemic signal quality failure → raises min composite override to 85

Writes findings to learned_adjustments.json (read at every scan start).
Runs weekly via /api/cron/weekly-learning endpoint.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

# Path is relative to the api/ working directory (where uvicorn runs from)
_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
LEARNING_CONFIG_PATH = os.path.join(_CONFIG_DIR, "learned_adjustments.json")

_DEFAULT_CONFIG: dict[str, Any] = {
    "generated_at": "2000-01-01T00:00:00",
    "overall_win_rate": None,
    "sample_size": 0,
    "suppressed_sectors": [],
    "suppressed_trade_modes": [],
    "min_composite_score_override": None,
    "sector_win_rates": {},
    "mode_win_rates": {},
}


def _ensure_config_dir() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)


def analyze_loss_patterns(supabase_client: Any) -> dict[str, Any]:
    """Examine last 30 days of resolved recommendations for systematic failures.

    Questions answered:
      1. Which sectors have the worst win rate? → suppress those sectors
      2. Which trade_modes are underperforming? → suppress or flag
      3. Are even high-composite (>80) signals failing? → raise global bar to 85

    Writes results to LEARNING_CONFIG_PATH for the analyzer to read at startup.
    Safe to call repeatedly — each call overwrites the previous config.

    Returns the adjustments dict (or status dict if insufficient data).
    """
    if supabase_client is None:
        return {"status": "no_client"}

    cutoff = (datetime.now() - timedelta(days=30)).date().isoformat()

    try:
        result = (
            supabase_client.table("recommendations")
            .select("performance_status, composite_score, trade_mode, signal_date, symbol, stocks(sector)")
            .neq("performance_status", "pending")
            .gte("signal_date", cutoff)
            .execute()
        )
        records = result.data or []
    except Exception as exc:
        return {"status": "db_error", "error": str(exc)}

    if len(records) < 1:
        return {
            "status": "insufficient_data",
            "min_required": 1,
            "available": len(records),
        }

    wins = [r for r in records if r.get("performance_status") == "target_hit"]
    losses = [r for r in records if r.get("performance_status") == "stop_loss_hit"]
    total_win_rate = len(wins) / len(records)

    adjustments: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "overall_win_rate": round(total_win_rate, 3),
        "sample_size": len(records),
        "suppressed_sectors": [],
        "suppressed_trade_modes": [],
        "min_composite_score_override": None,
        "sector_win_rates": {},
        "mode_win_rates": {},
    }

    # Helper to parse sector from stocks join
    def get_sector(r):
        stocks_data = r.get("stocks")
        if isinstance(stocks_data, dict):
            return stocks_data.get("sector")
        elif isinstance(stocks_data, list) and len(stocks_data) > 0:
            return stocks_data[0].get("sector")
        return None

    # --- Sector win rate analysis ---
    sector_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
    for r in wins:
        sec = get_sector(r)
        if sec:
            sector_counts[sec]["wins"] += 1
    for r in losses:
        sec = get_sector(r)
        if sec:
            sector_counts[sec]["losses"] += 1

    for sector, counts in sector_counts.items():
        total = counts["wins"] + counts["losses"]
        if total >= 1:
            wr = counts["wins"] / total
            adjustments["sector_win_rates"][sector] = round(wr, 3)
            if wr < 0.35:
                adjustments["suppressed_sectors"].append(sector)

    # --- Trade mode win rate analysis ---
    mode_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0})
    for r in wins:
        mode_counts[r.get("trade_mode", "unknown")]["wins"] += 1
    for r in losses:
        mode_counts[r.get("trade_mode", "unknown")]["losses"] += 1

    for mode, counts in mode_counts.items():
        total = counts["wins"] + counts["losses"]
        if total >= 1:
            wr = counts["wins"] / total
            adjustments["mode_win_rates"][mode] = round(wr, 3)
            if wr < 0.35:
                adjustments["suppressed_trade_modes"].append(mode)

    # Auto-floats threshold base score based on overall 30-day win rate (floats base score between 70 and 85)
    if total_win_rate < 0.35:
        adjustments["min_composite_score_override"] = 85
        adjustments["systemic_warning"] = (
            f"Overall 30d win rate is extremely low ({total_win_rate * 100:.1f}%). "
            "Threshold raised to 85."
        )
    elif total_win_rate < 0.50:
        adjustments["min_composite_score_override"] = 80
        adjustments["systemic_warning"] = (
            f"Overall 30d win rate is cautionary ({total_win_rate * 100:.1f}%). "
            "Threshold raised to 80."
        )
    elif total_win_rate < 0.65:
        adjustments["min_composite_score_override"] = 75
        adjustments["systemic_warning"] = (
            f"Overall 30d win rate is normal ({total_win_rate * 100:.1f}%). "
            "Threshold set to 75."
        )
    else:
        adjustments["min_composite_score_override"] = 70
        adjustments["systemic_warning"] = (
            f"Overall 30d win rate is excellent ({total_win_rate * 100:.1f}%). "
            "Threshold lowered to 70."
        )

    # Write to config
    _ensure_config_dir()
    try:
        with open(LEARNING_CONFIG_PATH, "w") as f:
            json.dump(adjustments, f, indent=2)
    except Exception as exc:
        adjustments["write_error"] = str(exc)

    return adjustments


def load_learned_adjustments() -> dict[str, Any]:
    """Load learned adjustments at scan start.

    Returns {} if:
      - File doesn't exist yet (first run)
      - File is older than 7 days (stale)
      - JSON is malformed

    This means the system silently falls back to defaults rather than
    crashing on a missing or corrupted config file.
    """
    try:
        with open(LEARNING_CONFIG_PATH) as f:
            config = json.load(f)

        generated_str = config.get("generated_at", "2000-01-01T00:00:00")
        generated = datetime.fromisoformat(generated_str)
        if (datetime.now() - generated).days > 7:
            return {}  # Stale — use defaults

        return config

    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {}
