import requests
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from config.settings import MAX_ARTICLES

_FEEDS = [
    "https://news.google.com/rss/search?q=silver+market+price&hl=en-US&gl=US&ceid=US:en",
    "https://feeds.reuters.com/reuters/companyNews",
    "https://www.kitco.com/rss/latestNews.rss",
]


def _parse_feed(url: str) -> list[dict]:
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.content, "xml")
    articles = []
    for item in soup.find_all("item"):
        title_tag = item.find("title")
        description = item.find("description")
        pub_date = item.find("pubDate")

        raw_desc = description.get_text() if description else ""
        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(strip=True)

        link_tag = item.find("link")
        guid_tag = item.find("guid")
        url_val = link_tag.get_text(strip=True) if link_tag else ""
        if not url_val and guid_tag:
            url_val = guid_tag.get_text(strip=True)

        date_str = pub_date.get_text(strip=True) if pub_date else ""
        try:
            parsed_dt = parsedate_to_datetime(date_str) if date_str else None
        except Exception:
            parsed_dt = None

        articles.append({
            "title": title_tag.get_text(strip=True) if title_tag else "",
            "date": date_str,
            "_dt": parsed_dt,
            "description": clean_desc,
            "url": url_val,
        })
    return articles


def fetch_articles() -> list[dict]:
    all_articles: list[dict] = []
    for feed_url in _FEEDS:
        all_articles.extend(_parse_feed(feed_url))

    # Deduplicate by normalised title, preserving first occurrence
    seen: set[str] = set()
    unique: list[dict] = []
    for article in all_articles:
        key = article["title"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(article)

    # Sort by recency; articles without a parseable date sort last
    unique.sort(key=lambda a: a["_dt"].timestamp() if a["_dt"] else 0, reverse=True)

    # Strip internal sort key before returning
    for a in unique:
        del a["_dt"]

    return unique[:MAX_ARTICLES]
