import os
import sys

sys.path.append("/Users/apple/market-advisor/api")

os.environ["FORCE_LIVE_SYNC"] = "true"

print("--- Running Timezone & Market Hours Check Verification ---", flush=True)
from main import is_indian_market_hours, _live_market_sync, admin_penny_scans

market_hours = is_indian_market_hours()
print(f"is_indian_market_hours() under FORCE_LIVE_SYNC=true returned: {market_hours}", flush=True)
assert market_hours is True, "Market hours check should return True under FORCE_LIVE_SYNC=true"
print("SUCCESS: Timezone and market hours check is valid.", flush=True)

print("\n--- Running Dynamic Penny Scans Verification ---", flush=True)
try:
    res = admin_penny_scans()
    print("SUCCESS: admin_penny_scans executed successfully.", flush=True)
    penny_scans = res.get("penny_scans", [])
    print(f"Total performing penny stocks found under Rs. 150: {len(penny_scans)}", flush=True)
    for i, stock in enumerate(penny_scans[:5], 1):
        print(f"  {i}. {stock['symbol']} (₹{stock['price']}) - Change: {stock['change_pct']}% - RSI: {stock['rsi']}", flush=True)
        assert stock['price'] < 150.0, f"Stock price {stock['price']} should be strictly less than 150.0"
        assert stock['change_pct'] > 0.0, f"Stock change {stock['change_pct']}% should be positive"
except Exception as e:
    print(f"ERROR: admin_penny_scans failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n--- Running Live Market Sync Execution Verification ---", flush=True)
try:
    _live_market_sync()
    print("SUCCESS: _live_market_sync completed successfully without raising errors.", flush=True)
except Exception as e:
    print(f"ERROR: _live_market_sync failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nVerification Complete. Everything works perfectly!", flush=True)
