import sys
import json
import time
import urllib.request
import urllib.parse

def create_jobs(api_key: str, cron_secret: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Job 1: Intraday Crossover and Reversal Check
    intraday_job = {
        "job": {
            "title": "Market Advisor - Intraday & Reversals",
            "url": "https://market-advisor-api.vercel.app/api/cron/intraday",
            "enabled": True,
            "saveResponses": True,
            "extendedData": {
                "headers": {
                    "Authorization": f"Bearer {cron_secret}"
                }
            },
            "schedule": {
                "timezone": "Asia/Kolkata", # Sets timezone directly to Indian Standard Time (IST)
                "expiresAt": 0,
                "hours": [9, 10, 11, 12, 13, 14, 15, 16], # 9:00 AM to 4:00 PM IST
                "mdays": [-1],
                "minutes": [0, 15, 30, 45], # Automatically triggers every 15 minutes!
                "months": [-1],
                "wdays": [1, 2, 3, 4, 5] # Weekdays only (Monday to Friday)
            }
        }
    }

    # Job 2: Daily Swing Trade scans
    daily_job = {
        "job": {
            "title": "Market Advisor - Daily Swing Scans",
            "url": "https://market-advisor-api.vercel.app/api/cron/daily",
            "enabled": True,
            "saveResponses": True,
            "extendedData": {
                "headers": {
                    "Authorization": f"Bearer {cron_secret}"
                }
            },
            "schedule": {
                "timezone": "Asia/Kolkata",
                "expiresAt": 0,
                "hours": [18], # 6:00 PM IST
                "mdays": [-1],
                "minutes": [0],
                "months": [-1],
                "wdays": [1, 2, 3, 4, 5] # Weekdays only
            }
        }
    }

    url = "https://api.cron-job.org/jobs"

    # Create Job 1
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(intraday_job).encode("utf-8"), 
            headers=headers, 
            method="PUT"
        )
        with urllib.request.urlopen(req) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            print(f"✔ Successfully created Intraday Cron Job! (Job ID: {res_data.get('jobId')})")
    except Exception as exc:
        print(f"❌ Failed to create Intraday Cron Job: {exc}")

    # Sleep to avoid hitting the rate limit of max 1 request/sec for PUT /jobs
    print("Waiting 2 seconds to avoid rate limits...")
    time.sleep(2)

    # Create Job 2
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(daily_job).encode("utf-8"), 
            headers=headers, 
            method="PUT"
        )
        with urllib.request.urlopen(req) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            print(f"✔ Successfully created Daily Swing Cron Job! (Job ID: {res_data.get('jobId')})")
    except Exception as exc:
        print(f"❌ Failed to create Daily Swing Cron Job: {exc}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python setup-cron-jobs.py <CRON_JOB_ORG_API_KEY> <VERCEL_CRON_SECRET>")
        sys.exit(1)
    create_jobs(sys.argv[1], sys.argv[2])
