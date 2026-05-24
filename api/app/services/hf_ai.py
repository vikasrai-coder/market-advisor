import json
import logging
import os
import re
from typing import Any

import httpx
from huggingface_hub import InferenceClient

from app.config import settings

logger = logging.getLogger(__name__)

HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"


def _get_hf_tokens() -> list[str]:
    """Extract primary token from settings and look up any indexed fallback tokens in environment."""
    tokens = []
    
    # 1. Parse from settings.hf_token (allow comma, space, or semicolon separated lists)
    if settings.hf_token:
        for t in re.split(r'[,\s;]+', settings.hf_token):
            if t.strip():
                tokens.append(t.strip())
                
    # 2. Dynamic check for environment fallbacks: HF_TOKEN_2, HF_TOKEN_3, etc.
    idx = 2
    while True:
        token_env = os.getenv(f"HF_TOKEN_{idx}")
        if not token_env:
            break
        token_clean = token_env.strip()
        if token_clean and token_clean not in tokens:
            tokens.append(token_clean)
        idx += 1
        
    return tokens


def _client() -> InferenceClient | None:
    tokens = _get_hf_tokens()
    if not tokens:
        return None
    return InferenceClient(token=tokens[0])


def _chat(prompt: str, max_tokens: int = 400, temperature: float = 0.3) -> str | None:
    """Chat via Hugging Face router (OpenAI-compatible) with fallback tokens."""
    tokens = _get_hf_tokens()
    if not tokens:
        logger.error("No Hugging Face token found for chat completion.")
        return None
        
    for token in tokens:
        try:
            response = httpx.post(
                HF_ROUTER_URL,
                headers={"Authorization": f"Bearer {token}"},
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
        except Exception as exc:
            logger.warning(
                f"Hugging Face Chat completion failed with token: {token[:12]}... "
                f"Exception: {exc}. Trying fallback..."
            )
            continue
            
    logger.error("All Hugging Face fallback tokens exhausted in chat completion.")
    return None


def generate_advisor_response(prompt: str) -> str | None:
    """Public wrapper to chat via Hugging Face AI router."""
    return _chat(prompt, max_tokens=650, temperature=0.4)


def analyze_news_sentiment(text: str) -> tuple[str, float]:
    """FinBERT sentiment for financial news with fallback tokens."""
    tokens = _get_hf_tokens()
    if not tokens or not text.strip():
        return "neutral", 0.5

    snippet = text[:512]
    for token in tokens:
        try:
            client = InferenceClient(token=token)
            result = client.text_classification(snippet, model=settings.hf_sentiment_model)
            if isinstance(result, list) and result:
                label = result[0].get("label", "neutral").lower()
                score = float(result[0].get("score", 0.5))
                if "pos" in label:
                    return "positive", score
                if "neg" in label:
                    return "negative", score
                return "neutral", score
        except Exception as exc:
            logger.warning(
                f"Hugging Face Sentiment classification failed with token: {token[:12]}... "
                f"Exception: {exc}. Trying fallback..."
            )
            continue
            
    logger.error("All Hugging Face fallback tokens exhausted in sentiment classification.")
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
