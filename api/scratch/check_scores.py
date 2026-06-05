import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services import analyzer
from app.scan_modes import get_config
from app.services.analyzer import _analyze_symbol_dispatch
import pandas as pd
import yfinance as yf

def main():
    print("Checking scores for a few symbols...")
    symbols = ["PTCIL.NS", "NEWGEN.NS", "IFCI.NS", "NUVAMA.NS", "RRKABEL.NS"]
    cfg = get_config("swing")
    
    for sym in symbols:
        try:
            profile = analyzer.market_data.fetch_stock_profile(sym)
            history = analyzer.market_data.fetch_price_history(sym, "3mo")
            res = _analyze_symbol_dispatch(sym, cfg, db_profile=profile, history_df=history)
            print(f"\nSymbol: {sym}")
            print(f"  Composite Score: {res.get('composite_score')}")
            for k in ["regime_blocked", "distribution_blocked", "bearish_candle_blocked", "personality_blocked", "rsi_overbought_blocked", "entry_blocked"]:
                if res.get(k):
                    print(f"  BLOCKED BY: {k} (reason: {res.get('reasoning') or 'N/A'})")
            metrics = res.get("metrics", {})
            print(f"  RSI: {metrics.get('rsi')}")
            print(f"  Regime: {metrics.get('regime')}")
            print(f"  ADX: {metrics.get('adx')}")
            print(f"  ATR stop loss: {metrics.get('atr_stop_loss')}")
            print(f"  ATR target price: {metrics.get('atr_target_price')}")
        except Exception as e:
            print(f"Error for {sym}: {e}")

if __name__ == "__main__":
    main()
