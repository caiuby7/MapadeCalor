"""Coleta de menções em feeds RSS de notícias brasileiras."""

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import feedparser

logger = logging.getLogger(__name__)

BRAZILIAN_NEWS_FEEDS = [
    {"url": "https://g1.globo.com/rss/g1/", "label": "G1"},
    {"url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "label": "Folha de S.Paulo"},
    {"url": "https://www.uol.com.br/feed/", "label": "UOL"},
    {"url": "https://rss.uol.com.br/feed/noticias/politica.xml", "label": "UOL Política"},
    {"url": "https://oglobo.globo.com/rss/oglobo/", "label": "O Globo"},
    {"url": "https://www.estadao.com.br/rss/politica.xml", "label": "Estadão"},
]


def _parse_feed(feed_info: dict, query: str, max_items: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_lower = query.lower()

    try:
        parsed = feedparser.parse(feed_info["url"])
    except Exception as exc:
        logger.warning("RSS %s: erro ao ler feed — %s", feed_info["label"], exc)
        return []

    for entry in parsed.entries[:max_items * 3]:
        title = entry.get("title", "")
        summary = entry.get("summary", entry.get("description", ""))
        combined = f"{title}. {summary}"

        if query_lower not in combined.lower():
            continue

        link = entry.get("link", feed_info["url"])
        domain = urlparse(link).netloc or feed_info["label"]

        items.append(
            {
                "source": "news",
                "source_label": feed_info["label"],
                "source_url": link,
                "text": combined[:500],
                "author": feed_info["label"],
                "author_location_raw": "",
                "published_at": entry.get("published", entry.get("updated", "")),
                "context_title": title,
            }
        )

        if len(items) >= max_items:
            break

    return items


async def collect_news(query: str, max_per_feed: int = 8) -> list[dict[str, Any]]:
    """Lê feeds RSS e filtra títulos/resumos que contenham o termo."""
    all_items: list[dict[str, Any]] = []

    tasks = [
        asyncio.to_thread(_parse_feed, feed, query, max_per_feed)
        for feed in BRAZILIAN_NEWS_FEEDS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error("RSS: erro — %s", result)
            continue
        all_items.extend(result)

    logger.info("Notícias RSS: %d menções para '%s'", len(all_items), query)
    return all_items
