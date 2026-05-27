# Market Advisor

AI **Indian stock** (NSE) buy recommendation platform that automatically produces **10 daily buy picks** using Yahoo Finance data, trend analysis, technical indicators, news sentiment, and Hugging Face LLM reasoning. Buy/sell signals are generated **today for tomorrow's** NSE/BSE session.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 16, Tailwind |
| API | Python FastAPI |
| AI | Hugging Face Inference API (FinBERT + Zephyr) |
| Database | Supabase (Postgres) |
| Market data | Yahoo Finance via `yfinance` (NSE `.NS` symbols, INR) |

## Features

- Scores **90+ NSE stocks** across large, mid, and small cap (e.g. `RELIANCE.NS`, `INDIGO.NS`, `CDSL.NS`) on trend, RSI/MACD/SMA, and news sentiment
- Top 10 picks are diversified: ~4 large, ~3 mid, ~3 small cap (best scores per segment)
- Ranks top **10 BUY** recommendations with AI-written reasoning
- **Buy/sell signals** with planned trade date = next market day
- Stores stocks, metrics, news, recommendations, and signals in Supabase
- Daily cron at 6:00 PM (API scheduler) or manual "Run daily analysis"

## Algo trading platform roadmap

See [`ALGO_TRADING_PLATFORM_ROADMAP.md`](./ALGO_TRADING_PLATFORM_ROADMAP.md) for the staged product and technical architecture to evolve this alert/recommendation app into a full no-code strategy, backtesting, paper trading, live execution, and marketplace platform.

## Quick start

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. In SQL Editor, run `supabase/migrations/001_initial.sql`.
3. Copy **Project URL**, **anon key**, and **service role key**.

### 2. Hugging Face

1. Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) with **Inference** access.
2. Optional: accept the license for `HuggingFaceH4/zephyr-7b-beta` on the model page.

### 3. Environment

```bash
cp .env.example api/.env
cp .env.example web/.env.local
```

Edit both files with your keys:

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
HF_TOKEN=hf_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4. API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 5. Web

```bash
cd web
npm install
npm run dev
```

### Production (Vercel)

| App | URL |
|-----|-----|
| Web | https://web-seven-smoky-94.vercel.app |
| API | https://market-advisor-api.vercel.app |

Redeploy: `bash scripts/deploy-vercel.sh` (uses `bunx vercel`)

In **Supabase → Authentication → URL Configuration**, set Site URL and Redirect URLs to your Vercel web URL (e.g. `https://web-seven-smoky-94.vercel.app/**`).

### Local

Open [http://localhost:3000](http://localhost:3000) — you will be redirected to **login**.

**Default admin** (create once with `python scripts/seed_admin_user.py` using `api/.venv/bin/python`):

- Email: `admin@market.in`
- Password: set via `ADMIN_PASSWORD` in `api/.env`

Then click **Run daily analysis**.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service status |
| POST | `/api/analysis/run` | Run full analysis (10 buys + signals) |
| GET | `/api/recommendations` | Latest top 10 buys |
| GET | `/api/signals` | Buy/sell signals |
| GET | `/api/stocks/{symbol}` | Stock profile, metrics, news |

## How scoring works

**Composite score** = 40% trend + 35% technical + 25% news sentiment

- **Trend**: price vs SMA20/SMA50, RSI zone, MACD crossover
- **Technical**: momentum and daily change
- **News**: FinBERT (`ProsusAI/finbert`) on recent headlines
- **AI insight**: Hugging Face chat model summarizes each top pick

## Disclaimer

This tool is for **education and research only**. It is not financial advice. Past patterns do not guarantee future returns. Always do your own due diligence.
