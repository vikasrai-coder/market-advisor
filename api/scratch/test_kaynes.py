import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.market_data import fetch_stock_profile, fetch_price_history
from app.symbols import normalize_symbol

symbol = "KAYNES.NS"
try:
    print("Normalizing symbol...")
    sym = normalize_symbol(symbol)
    print(f"Normalized: {sym}")
    
    print("Fetching stock profile...")
    profile = fetch_stock_profile(sym)
    print("Profile keys:", list(profile.keys()))
    print("Name:", profile.get("name"))
    print("Sector:", profile.get("sector"))
    
    print("Fetching price history...")
    history = fetch_price_history(sym, "5d")
    print("History empty?", history.empty)
    if not history.empty:
        print("Last close price:", history["Close"].iloc[-1])
except Exception as e:
    print("ERROR OCCURRED:", e)
    import traceback
    traceback.print_exc()
