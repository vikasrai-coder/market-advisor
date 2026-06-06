import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.institutional_scorer import run_institutional_scan, score_stock
import yfinance as yf

def main():
    print("Testing institutional scan logic...")
    try:
        # Run bulk scan (this fetches watchlist and runs parallel analysis)
        scan_results = run_institutional_scan()
        results = scan_results.get("results", [])
        alerts = scan_results.get("alerts", [])
        summary = scan_results.get("summary", {})
        
        print(f"\n--- Scan Summary ---")
        print(f"Scanned count: {summary.get('scanned')}")
        print(f"Total results: {summary.get('total_results')}")
        print(f"High-alpha alerts count: {summary.get('high_alpha_alerts')}")
        print(f"Market environment: {summary.get('market_environment')}")
        
        print(f"\n--- Top 3 Scored Stocks ---")
        for i, res in enumerate(results[:3]):
            print(f"\n{i+1}. {res.get('symbol')} ({res.get('name')})")
            print(f"   Alpha Score: {res.get('alpha_score')}")
            print(f"   Confidence:  {res.get('confidence_score')}%")
            print(f"   Verdict:     {res.get('verdict')}")
            print(f"   Price:       ₹{res.get('price')}")
            print(f"   Entry:       ₹{res.get('entry')}")
            print(f"   Stop Loss:   ₹{res.get('stop_loss')}")
            print(f"   Target 1:    ₹{res.get('target_1')}")
            print(f"   Target 2:    ₹{res.get('target_2')}")
            print(f"   R:R Ratio:   {res.get('risk_reward')}:1")
            print(f"   Reasoning:   {res.get('reasoning')}")
            print(f"   Pillar Scores: {res.get('pillar_scores')}")
            
        print(f"\n--- High Alpha Alerts ---")
        for alert in alerts:
            print(f"Alert: {alert.get('symbol')} - Alpha: {alert.get('alpha_score')}, Conf: {alert.get('confidence_score')}")
            
    except Exception as e:
        print(f"Error executing scan: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
