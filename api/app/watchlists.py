"""NSE watchlists by market cap segment (Yahoo Finance .NS symbols)."""

# Large cap — Nifty 50 / blue chips
LARGE_CAP = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "HCLTECH.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS",
    "NESTLEIND.NS", "NTPC.NS", "TECHM.NS", "M&M.NS", "TATASTEEL.NS",
    "BAJAJFINSV.NS", "ADANIPORTS.NS", "EICHERMOT.NS", "HDFCLIFE.NS", "POWERGRID.NS",
]

# Mid cap — Nifty Midcap / next 150 style
MID_CAP = [
    "INDIGO.NS", "PERSISTENT.NS", "COFORGE.NS", "MUTHOOTFIN.NS", "VOLTAS.NS",
    "POLYCAB.NS", "GODREJPROP.NS", "MARICO.NS", "DIXON.NS", "TATAELXSI.NS",
    "LUPIN.NS", "APLAPOLLO.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS", "CHOLAFIN.NS",
    "HINDPETRO.NS", "BPCL.NS", "GAIL.NS", "IRFC.NS", "REC.NS",
    "PFC.NS", "NHPC.NS", "SJVN.NS", "HAL.NS", "BEL.NS",
    "DMART.NS", "IRCTC.NS", "SRF.NS", "MPHASIS.NS", "AUROPHARMA.NS",
]

# Small cap — Nifty Smallcap 250 / emerging names
SMALL_CAP = [
    "CDSL.NS", "CAMS.NS", "KALYANKJIL.NS", "ASTRAL.NS", "DEEPAKNTR.NS",
    "CROMPTON.NS", "METROPOLIS.NS", "AAVAS.NS", "LATENTVIEW.NS", "NEWGEN.NS",
    "TANLA.NS", "KEI.NS", "CYIENT.NS", "KAYNES.NS", "RADICO.NS",
    "ROUTE.NS", "JKCEMENT.NS", "STARHEALTH.NS", "RVNL.NS", "IRCON.NS",
    "NBCC.NS", "BEML.NS", "CENTURYPLY.NS", "TIMKEN.NS", "HAPPSTMNDS.NS",
    "SUZLON.NS", "NH.NS", "CARTRADE.NS", "CRAFTSMAN.NS", "ZENTEC.NS",
]

import json
import os

CACHE_FILE = os.path.join(os.path.dirname(__file__), "watchlists_cache.json")

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as _f:
            _cache = json.load(_f)
            if _cache.get("large"):
                LARGE_CAP = _cache["large"]
            if _cache.get("mid"):
                MID_CAP = _cache["mid"]
            if _cache.get("small"):
                SMALL_CAP = _cache["small"]
    except Exception:
        pass

WATCHLIST_BY_SEGMENT: dict[str, list[str]] = {
    "large": LARGE_CAP,
    "mid": MID_CAP,
    "small": SMALL_CAP,
}

DEFAULT_WATCHLIST: list[str] = LARGE_CAP + MID_CAP + SMALL_CAP

_SYMBOL_SEGMENT: dict[str, str] = {}
for segment, symbols in WATCHLIST_BY_SEGMENT.items():
    for symbol in symbols:
        _SYMBOL_SEGMENT[symbol] = segment


def get_cap_segment(symbol: str) -> str:
    return _SYMBOL_SEGMENT.get(symbol.upper(), "unknown")


def watchlist_summary() -> dict[str, int]:
    return {segment: len(symbols) for segment, symbols in WATCHLIST_BY_SEGMENT.items()}
