import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from app.services.supabase_store import get_client
from app.services.redis_cache import invalidate_all_caches

def main():
    print("Flushing stale cache...")
    client = get_client()
    if client:
        today_str = date.today().isoformat()
        print(f"Deleting recommendations and signals before {today_str} from Supabase...")
        res_rec = client.table("recommendations").delete().lt("signal_date", today_str).execute()
        res_sig = client.table("trading_signals").delete().lt("signal_date", today_str).execute()
        print("Supabase deletion complete.")
    else:
        print("Supabase client not available.")

    print("Flushing Redis cache...")
    invalidate_all_caches()
    print("Redis cache invalidation complete.")

if __name__ == "__main__":
    main()
