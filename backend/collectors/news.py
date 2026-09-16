"""Coletor de notícias via feeds RSS públicos (sem API key)."""

import asyncio
import logging
import re
from html import unescape
from typing import Any

import feedparser

logger = logging.getLogger(__name__)

BRAZILIAN_NEWS_FEEDS = [
    {"url": "https://g1.globo.com/rss/g1/", "label": "G1"},
    {"url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "label": "Folha de S.Paulo"},
    {"url": "https://www.uol.com.br/feed/", "label": "UOL"},
    {"url": "https://rss.uol.com.br/feed/noticias/politica.xml", "label": "UOL Política"},
    {"url": "https://oglobo.globo.com/rss/oglobo/", "label": "O Globo"},
    {"url": "https://www.estadao.com.br/rss/politica.xml", "label": "Estadão"},
    {"url": "https://www.cnnbrasil.com.br/feed/", "label": "CNN Brasil"},
]

DEFAULT_MAX_PER_FEED = 10


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def _parse_feed(feed: dict, query: str, max_items: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_lower = query.lower()

    try:
        parsed = feedparser.parse(feed["url"])
    except Exception as exc:
        logger.warning("RSS %s: erro — %s", feed["label"], exc)
        return []

    for entry in parsed.entries:
        title = entry.get("title", "")
        summary = _strip_html(entry.get("summary", entry.get("description", "")))
        combined = f"{title}. {summary}".strip()

        if query_lower not in combined.lower():
            continue

        link = entry.get("link", feed["url"])
        items.append(
            {
                "source": "news",
                "text": combined[:500],
                "author": feed["label"],
                "created_at": entry.get("published", entry.get("updated", "")),
                "source_url": link,
                "source_label": feed["label"],
            }
        )

        if len(items) >= max_items:
            break

    return items


async def collect_news(query: str, max_per_feed: int = DEFAULT_MAX_PER_FEED) -> list[dict[str, Any]]:
    """Lê feeds RSS em paralelo e filtra por palavra-chave."""
    tasks = [
        asyncio.to_thread(_parse_feed, feed, query, max_per_feed)
        for feed in BRAZILIAN_NEWS_FEEDS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    items: list[dict[str, Any]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("RSS: erro — %s", result)
            continue
        items.extend(result)

    logger.info("Notícias RSS: %d menções coletadas para '%s'", len(items), query)
    return items
