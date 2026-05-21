import json
import re
from typing import Any

import httpx
from huggingface_hub import InferenceClient

from app.config import settings

HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"


def _client() -> InferenceClient | None:
    if not settings.hf_token:
        return None
    return InferenceClient(token=settings.hf_token)


def _chat(prompt: str, max_tokens: int = 400, temperature: float = 0.3) -> str | None:
    """Chat via Hugging Face router (OpenAI-compatible)."""
    if not settings.hf_token:
        return None
    try:
        response = httpx.post(
            HF_ROUTER_URL,
            headers={"Authorization": f"Bearer {settings.hf_token}"},
            json={
                "model": settings.hf_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=90.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def analyze_news_sentiment(text: str) -> tuple[str, float]:
    """FinBERT sentiment for financial news."""
    client = _client()
    if not client or not text.strip():
        return "neutral", 0.5

    snippet = text[:512]
    try:
        result = client.text_classification(snippet, model=settings.hf_sentiment_model)
        if isinstance(result, list) and result:
            label = result[0].get("label", "neutral").lower()
            score = float(result[0].get("score", 0.5))
            if "pos" in label:
                return "positive", score
            if "neg" in label:
                return "negative", score
            return "neutral", score
    except Exception:
        pass
    return "neutral", 0.5


def score_news_batch(articles: list[dict[str, Any]]) -> float:
    if not articles:
        return 50.0
    scores: list[float] = []
    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}"
        label, conf = analyze_news_sentiment(text)
        if label == "positive":
            scores.append(50 + conf * 50)
        elif label == "negative":
            scores.append(50 - conf * 50)
        else:
            scores.append(50.0)
    return sum(scores) / len(scores) if scores else 50.0


def generate_recommendation_insight(
    symbol: str,
    profile: dict[str, Any],
    metrics: dict[str, Any],
    news_score: float,
    composite: float,
) -> dict[str, Any]:
    """LLM reasoning via Hugging Face router + FinBERT sentiment."""
    display = profile.get("display_symbol") or symbol.replace(".NS", "")
    currency = profile.get("currency") or "INR"
    fallback = {
        "reasoning": (
            f"{display} (NSE) scores {composite:.0f}/100: trend {metrics.get('trend_score', 50):.0f}, "
            f"technicals {metrics.get('technical_score', 50):.0f}, news {news_score:.0f}. "
            f"RSI {metrics.get('rsi')}, price vs SMA20/SMA50 supports "
            f"{'bullish' if (metrics.get('trend_score') or 0) >= 55 else 'mixed'} bias."
        ),
        "confidence": min(0.95, composite / 100),
        "key_factors": [
            "Price trend vs moving averages",
            "RSI and MACD momentum",
            "Recent news sentiment",
            f"Sector: {profile.get('sector') or 'N/A'}",
        ],
    }
    if not settings.hf_token:
        return fallback

    prompt = f"""You are an experienced Indian equity analyst (NSE). Analyze {display} ({symbol}) for a BUY recommendation.

Company: {profile.get('name')} | Exchange: {profile.get('exchange', 'NSE')} | Sector: {profile.get('sector')} | P/E: {profile.get('pe_ratio')}
Price: {currency} {metrics.get('price')} | Change: {metrics.get('change_pct')}% | RSI: {metrics.get('rsi')}
Trend score: {metrics.get('trend_score')}/100 | Technical: {metrics.get('technical_score')}/100
News sentiment score: {news_score}/100 | Composite: {composite}/100

Reply ONLY with valid JSON:
{{"reasoning": "2-3 sentences", "confidence": 0.0-1.0, "key_factors": ["factor1", "factor2", "factor3"]}}"""

    content = _chat(prompt, max_tokens=400, temperature=0.3)
    if content:
        parsed = _extract_json(content)
        if parsed:
            return parsed
    return fallback


def generate_sell_rationale(symbol: str, metrics: dict[str, Any]) -> str:
    display = symbol.replace(".NS", "").replace(".BO", "")
    base = (
        f"Sell signal for {display}: weakening trend (score {metrics.get('trend_score', 0):.0f}), "
        f"RSI {metrics.get('rsi')}, MACD below signal."
    )
    if not settings.hf_token:
        return base

    prompt = (
        f"In one sentence, explain why to reduce {display} ({symbol}) NSE position: "
        f"trend={metrics.get('trend_score')}, rsi={metrics.get('rsi')}, "
        f"change={metrics.get('change_pct')}%."
    )
    content = _chat(prompt, max_tokens=120, temperature=0.2)
    return content.strip() if content else base


def _extract_json(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
