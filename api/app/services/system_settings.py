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
_IN_MEMORY_SETTINGS: dict[str, Any] = {}


def get_settings() -> dict[str, Any]:
    """Get the current system settings. Returns 'low' as default usage_mode."""
    global _IN_MEMORY_SETTINGS
    with _lock:
        if _IN_MEMORY_SETTINGS:
            return _IN_MEMORY_SETTINGS

        # Try /tmp settings file first (Vercel runtime environment)
        tmp_file = "/tmp/system_settings_cache.json"
        if os.path.exists(tmp_file):
            try:
                with open(tmp_file, "r") as f:
                    data = json.load(f)
                    if "usage_mode" not in data:
                        data["usage_mode"] = "low"
                    _IN_MEMORY_SETTINGS = data
                    return data
            except Exception:
                pass

        # Try original settings file path next
        try:
            with open(_SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "usage_mode" not in data:
                    data["usage_mode"] = "low"
                _IN_MEMORY_SETTINGS = data
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {"usage_mode": "low"}


def save_settings(usage_mode: str) -> dict[str, Any]:
    """Save system settings, specifically the usage mode ('low' | 'high')."""
    if usage_mode not in ("low", "high"):
        raise ValueError("Invalid usage_mode. Must be 'low' or 'high'.")
        
    global _IN_MEMORY_SETTINGS
    with _lock:
        data = {"usage_mode": usage_mode}
        _IN_MEMORY_SETTINGS = data
        
        # 1. Try writing to original settings file
        try:
            with open(_SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            return {"success": True, "settings": data}
        except Exception as main_exc:
            # 2. Try writing to /tmp folder in read-only environment
            try:
                tmp_file = "/tmp/system_settings_cache.json"
                with open(tmp_file, "w") as f:
                    json.dump(data, f, indent=2)
                return {"success": True, "settings": data, "warning": "Saved to temporary storage"}
            except Exception as tmp_exc:
                # 3. Fallback to in-memory only if everything is read-only
                return {
                    "success": True, 
                    "settings": data, 
                    "warning": f"Saved in-memory only (Disk write failed: {main_exc} | {tmp_exc})"
                }
