import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from app.services import market_data, technicals
from app.services.analyzer import _target_for_mode, _stop_for_mode
from app.scan_modes import get_config

symbols = ["PTCIL.NS", "NEWGEN.NS", "IFCI.NS", "NUVAMA.NS", "RRKABEL.NS"]

for sym in symbols:
    print(f"=== {sym} ===")
    try:
        profile = market_data.fetch_stock_profile(sym)
        history = market_data.fetch_price_history(sym, "3mo")
        price = history["Close"].iloc[-1]
        
        # Calculate personality rule
        personality = technicals.get_stock_personality(profile, history)
        rules = personality["rules"]
        atr_sl_multiplier = rules.get("atr_sl_multiplier", 2.0)
        
        atr_levels = technicals.get_atr_levels(history, price, sl_multiplier=atr_sl_multiplier)
        
        target_price = _target_for_mode(price, "swing", atr_levels)
        stop_loss = _stop_for_mode(price, "swing", atr_levels)
        
        print(f"Price: {price}")
        print(f"ATR Levels: {atr_levels}")
        print(f"Target: {target_price}")
        print(f"Stop Loss: {stop_loss}")
        if target_price and stop_loss and stop_loss < price:
            rr = (target_price - price) / (price - stop_loss)
            print(f"R:R relative to price: {rr:.4f}")
        else:
            print("Cannot compute R:R relative to price")
            
    except Exception as e:
        print(f"Error: {e}")
