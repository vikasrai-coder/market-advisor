import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.supabase_store import get_client
from datetime import date

def main():
    client = get_client()
    if not client:
        print("Supabase client not available")
        return
        
    today_str = date.today().isoformat()
    print(f"Querying recommendations and signals for {today_str}...")
    
    recs = client.table("recommendations").select("*").eq("signal_date", today_str).execute()
    signals = client.table("trading_signals").select("*").eq("signal_date", today_str).execute()
    
    print(f"\nSupabase Recommendations ({len(recs.data)}):")
    for r in recs.data:
        print(f"Symbol: {r['symbol']}, Mode: {r['trade_mode']}, Score: {r['composite_score']}, Target: {r['target_price']}, Stop: {r['stop_loss']}")
        
    print(f"\nSupabase Signals ({len(signals.data)}):")
    for s in signals.data:
        print(f"Symbol: {s['symbol']}, Type: {s['signal_type']}, Mode: {s['trade_mode']}, Target: {s['target_price']}, Stop: {s['stop_loss']}")

if __name__ == "__main__":
    main()
