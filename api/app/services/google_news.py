import xml.etree.ElementTree as ET
import httpx
import logging
from typing import Any
import urllib.parse
import email.utils

logger = logging.getLogger(__name__)

def fetch_google_news_rss(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Fetch search articles from Google News RSS feed and parse into standardised format.
    
    Args:
        query: Search query string (e.g. "NIFTY 50" or stock name).
        limit: Maximum number of articles to return.
    """
    if not query.strip():
        return []
        
    encoded_query = urllib.parse.quote(query)
    # Search URL targeted for Indian English news (coinciding with NSE focus)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        response = httpx.get(url, timeout=12.0)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        articles: list[dict[str, Any]] = []
        
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date_str = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()
            
            # Extract clean publisher from source tag if present
            source_el = item.find("source")
            source = source_el.text.strip() if (source_el is not None and source_el.text) else "Google News"
            
            # Format title (often Google News appends " - Publisher" to title)
            if f" - {source}" in title:
                title = title.replace(f" - {source}", "").strip()
            
            # Parse publication date to ISO timestamp
            published_at = None
            if pub_date_str:
                try:
                    parsed_time = email.utils.parsedate_to_datetime(pub_date_str)
                    published_at = parsed_time.isoformat()
                except Exception:
                    pass
            
            # Standardise summary by removing HTML tags if present
            import re
            clean_desc = re.sub(r'<[^>]*>', '', description)[:2000]
            
            articles.append({
                "title": title,
                "summary": clean_desc,
                "url": link,
                "source": source,
                "published_at": published_at
            })
            
        return articles
    except Exception as exc:
        logger.error(f"Error fetching/parsing Google News RSS for query '{query}': {exc}", exc_info=True)
        return []
