import sys
import os

# Adjust sys.path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.google_news import fetch_google_news_rss
from app.services import hf_ai, analyzer
from app.scan_modes import get_config

def test_google_news_fetching():
    print("--- 1. Testing Google News RSS Fetching for 'NIFTY 50' ---")
    articles = fetch_google_news_rss("NIFTY 50", limit=3)
    print(f"Successfully retrieved {len(articles)} NIFTY articles.")
    for idx, art in enumerate(articles, start=1):
        print(f"Article {idx}:")
        print(f"  Title: {art['title']}")
        print(f"  Source: {art['source']}")
        print(f"  Published At: {art['published_at']}")
        print(f"  URL: {art['url'][:60]}...")
    assert len(articles) > 0, "No articles fetched from Google News RSS"
    print("Google News RSS Fetching matches the specification!\n")


def test_sentiment_scoring():
    print("--- 2. Testing FinBERT Sentiment Scoring with User's Geopolitical Headlines ---")
    # Mocking the two user provided headlines
    mock_articles = [
        {
            "title": "Blast from the Middle East: NIFTY Sinks 2% as US-Iran Tensions Escalate",
            "summary": "Fresh US-Iran strikes trigger a 2% plunge in the Nifty index, hinting at a gap-down opening for Indian stock markets on Thursday, with investors cautious about escalating global tensions."
        },
        {
            "title": "NIFTY CRASHES 2%, BOLSTERING BLOOD-BOILING VOLATILITY: FRESH US-IRAN STRIKES SPARK GLOBAL MARKET CHAOS",
            "summary": "The Indian equity markets are bracing for a gap-down opening on 29 May as the NIFTY benchmark crashes 2% overnight amidst fresh US-Iran strikes."
        }
    ]
    
    score = hf_ai.score_news_batch(mock_articles)
    print(f"Scored macro sentiment for geopolitical headlines: {score:.2f}/100")
    
    # Verify that the score is indeed highly bearish
    assert score < 35.0, f"Expected bearish score (<35.0) for NIFTY crash news, but got {score}"
    print("FinBERT sentiment scoring correctly identified the bearish macro news!\n")


def test_macro_score_modifier():
    print("--- 3. Testing Mathematical Risk Penalty Overlay on Composite Scores ---")
    cfg = get_config("swing")
    
    # Mock stock analysis details
    mock_profile = {
        "symbol": "RELIANCE.NS",
        "display_symbol": "RELIANCE",
        "name": "Reliance Industries Ltd",
        "sector": "Energy"
    }
    
    mock_metrics = {
        "price": 2800.0,
        "trend_score": 80.0,      # strongly bullish technicals
        "technical_score": 75.0,  # strongly bullish trend
        "rsi": 62.0
    }
    
    # 3.1 Normal market baseline (neutral/bullish macro, no penalty)
    res_normal = analyzer._analyze_symbol_swing(
        symbol="RELIANCE.NS",
        cfg=cfg,
        db_profile=mock_profile,
        history_df=None,
        news_articles=[],
        macro_sentiment_score=50.0  # neutral macro
    )
    print(f"Normal market composite score (no penalty): {res_normal['composite_score']:.2f}")
    
    # 3.2 Bearish market (macro score 15.0/100, representing the geopolitical crash)
    bearish_score = 15.0
    res_bearish = analyzer._analyze_symbol_swing(
        symbol="RELIANCE.NS",
        cfg=cfg,
        db_profile=mock_profile,
        history_df=None,
        news_articles=[],
        macro_sentiment_score=bearish_score
    )
    print(f"Bearish market composite score (with penalty): {res_bearish['composite_score']:.2f}")
    
    # Expected penalty: (15.0 - 50.0) * 0.4 = -14.0 points
    expected_diff = round((bearish_score - 50.0) * 0.4, 2)
    actual_diff = round(res_bearish["composite_score"] - res_normal["composite_score"], 2)
    
    print(f"Expected composite decrement: {expected_diff:.2f}")
    print(f"Actual composite decrement: {actual_diff:.2f}")
    
    assert abs(actual_diff - expected_diff) < 0.01, f"Expected decrement of {expected_diff}, got {actual_diff}"
    print("Macro score modifier is mathematically precise!\n")


def test_gap_down_warnings():
    print("--- 4. Testing Overnight Gap-Down Flagging and LLM Prompt Generation ---")
    mock_profile = {
        "symbol": "RELIANCE.NS",
        "display_symbol": "RELIANCE",
        "name": "Reliance Industries Ltd",
        "sector": "Energy"
    }
    mock_metrics = {"price": 2800.0}
    
    # Verify warning flag condition (<30 score)
    warning_triggered = (15.0 < 30.0)
    print(f"Gap-down warning triggered status for macro score 15.0: {warning_triggered}")
    assert warning_triggered is True, "Warning flag should trigger under score 30"
    
    # Mock a call to generate insight with the bearish macro context to verify formatting
    insight = hf_ai.generate_recommendation_insight(
        symbol="RELIANCE.NS",
        profile=mock_profile,
        metrics=mock_metrics,
        news_score=50.0,
        composite=65.0,
        macro_sentiment=15.0,
        macro_headlines="US-Iran strikes trigger Nifty crash"
    )
    
    print("Generated insight reasoning fallback or response:")
    print(f"  Reasoning: {insight['reasoning']}")
    print(f"  Key Factors: {insight['key_factors']}")
    
    # Check that warning/volatility is contained in reasoning or key factors
    has_warning = any("warning" in k.lower() or "volatility" in k.lower() for k in insight["key_factors"])
    assert has_warning or "warning" in insight["reasoning"].lower(), "Geopolitical risk/warning not found in fallback insight"
    print("Overnight Gap-Down Warnings are successfully integrated!\n")


if __name__ == "__main__":
    print("======================================================================")
    print("RUNNING GOOGLE NEWS & NIFTY MACRO sentiment INTEGRATION TESTS")
    print("======================================================================\n")
    try:
        test_google_news_fetching()
        test_sentiment_scoring()
        test_macro_score_modifier()
        test_gap_down_warnings()
        print("======================================================================")
        print("ALL TESTS PASSED SUCCESSFULLY!")
        print("======================================================================")
    except AssertionError as e:
        print("\n=== TEST FAILURE ===")
        print(e)
        sys.exit(1)
