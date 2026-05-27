"""System Settings — Manages system settings cache such as usage modes.

Provides dynamic toggle between "low" usage (efficient Vercel runtime) 
and "high" usage (full LLM insight + news sentiment capabilities).
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "system_settings_cache.json")
_lock = threading.Lock()


def get_settings() -> dict[str, Any]:
    """Get the current system settings. Returns 'low' as default usage_mode."""
    with _lock:
        try:
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "usage_mode" not in data:
                    data["usage_mode"] = "low"
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"usage_mode": "low"}


def save_settings(usage_mode: str) -> dict[str, Any]:
    """Save system settings, specifically the usage mode ('low' | 'high')."""
    if usage_mode not in ("low", "high"):
        raise ValueError("Invalid usage_mode. Must be 'low' or 'high'.")
        
    with _lock:
        data = {"usage_mode": usage_mode}
        try:
            with open(_SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            return {"success": True, "settings": data}
        except Exception as exc:
            raise RuntimeError(f"Failed to save system settings: {exc}")
