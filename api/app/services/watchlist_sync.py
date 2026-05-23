"""Service to dynamically download and synchronize the NSE Nifty 500 stock index sheets."""

import csv
import io
import json
import logging
import os
import urllib.request
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "watchlists_cache.json")

# Official NSE index URLs
URLS = {
    "large_50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "large_next50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "mid_100": "https://archives.nseindia.com/content/indices/ind_niftymidcap100list.csv",
    "small_250": "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
}


def sync_nse_watchlists() -> dict[str, Any]:
    """Scrape the official NSE index sheets, categorize them by cap, and update the cache file.

    Returns:
        Summary count of successfully synchronized symbols per segment.
    """
    logger.info("Starting official NSE watchlist synchronization...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    synced_data = {
        "large": [],
        "mid": [],
        "small": [],
    }

    # Helper to download and parse symbols
    def download_index_symbols(url: str) -> list[str]:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode("utf-8")
                # Parse CSV rows
                reader = csv.reader(io.StringIO(content))
                rows = list(reader)
                if not rows:
                    return []
                
                header = [c.strip().lower() for c in rows[0]]
                symbol_idx = -1
                for idx, col in enumerate(header):
                    if "symbol" in col:
                        symbol_idx = idx
                        break
                
                if symbol_idx == -1:
                    return []

                symbols = []
                for row in rows[1:]:
                    if len(row) > symbol_idx:
                        sym = row[symbol_idx].strip()
                        if sym:
                            symbols.append(f"{sym}.NS")
                return symbols
        except Exception as exc:
            logger.error(f"Error fetching from {url}: {exc}")
            return []

    # 1. Fetch Large Cap (Nifty 50 + Nifty Next 50)
    n50 = download_index_symbols(URLS["large_50"])
    n_next50 = download_index_symbols(URLS["large_next50"])
    large_list = list(set(n50 + n_next50))
    if large_list:
        synced_data["large"] = sorted(large_list)
        logger.info(f"Synchronized {len(large_list)} Large Cap symbols.")

    # 2. Fetch Mid Cap (Nifty Midcap 100)
    mid_list = download_index_symbols(URLS["mid_100"])
    if mid_list:
        synced_data["mid"] = sorted(mid_list)
        logger.info(f"Synchronized {len(mid_list)} Mid Cap symbols.")

    # 3. Fetch Small Cap (Nifty Smallcap 250)
    small_list = download_index_symbols(URLS["small_250"])
    if small_list:
        synced_data["small"] = sorted(small_list)
        logger.info(f"Synchronized {len(small_list)} Small Cap symbols.")

    # Check if we got valid lists
    success = len(synced_data["large"]) > 0 or len(synced_data["mid"]) > 0 or len(synced_data["small"]) > 0

    if success:
        # If any of the fetches failed, keep the defaults from the cache if available
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    old_data = json.load(f)
                for segment in ["large", "mid", "small"]:
                    if not synced_data[segment] and segment in old_data:
                        synced_data[segment] = old_data[segment]
            except Exception:
                pass

        # Save to local cache file
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump({
                    "updated_at": datetime.utcnow().isoformat(),
                    **synced_data
                }, f, indent=2)
            logger.info("Watchlist cache file updated successfully.")
        except Exception as exc:
            logger.error(f"Failed to write to watchlist cache file: {exc}")
    else:
        logger.warning("No lists successfully synchronized. Watchlist remains unchanged.")

    return {
        "success": success,
        "large_count": len(synced_data["large"]),
        "mid_count": len(synced_data["mid"]),
        "small_count": len(synced_data["small"]),
        "updated_at": datetime.utcnow().isoformat(),
    }
