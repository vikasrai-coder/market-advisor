import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services import analyzer
from app.services.supabase_store import get_client
from datetime import date

def run_test():
    print("Running full swing analysis...")
    res = analyzer.run_full_analysis(mode="swing")
    
    print("\n--- RESULTS ---")
    print(f"Status: {res.get('status')}")
    print(f"Stocks analyzed: {res.get('stocks_analyzed')}")
    
    recs = res.get("top_recommendations", [])
    signals = res.get("signals", [])
    
    print(f"Recommendations count: {len(recs)}")
    print(f"Signals count: {len(signals)}")
    
    print("\n--- RECOMMENDATIONS ---")
    for r in recs:
        entry = r.get("ideal_entry_price") or r.get("price_at_signal") or r.get("vwap")
        # Wait, let's find price from stocks profile or rec
        price = r.get("ideal_entry_price") or r.get("vwap")
        target = r.get("target_price")
        stop = r.get("stop_loss")
        print(f"Symbol: {r['symbol']}, Entry: {entry}, Target: {target}, Stop: {stop}")
        if target and stop and entry:
            try:
                rr = (target - entry) / (entry - stop)
                print(f"  R:R: {rr:.4f}")
            except ZeroDivisionError:
                print("  R:R: division by zero")
        
    print("\n--- SIGNALS ---")
    for s in signals:
        print(f"Symbol: {s['symbol']}, Type: {s['signal_type']}, Target: {s.get('target_price')}, Stop: {s.get('stop_loss')}")
        
    # Check for duplicates in signals
    seen = set()
    duplicates = []
    for s in signals:
        key = (s.get("symbol"), s.get("signal_date"), s.get("signal_type"))
        if key in seen:
            duplicates.append(key)
        seen.add(key)
        
    if duplicates:
        print(f"\nWARNING: Found duplicate signals: {duplicates}")
    else:
        print("\nSUCCESS: No duplicate signals found.")

if __name__ == "__main__":
    run_test()
