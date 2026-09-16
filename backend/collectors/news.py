"""Coletor de notícias via Google News RSS + feeds brasileiros."""

import asyncio
import logging
import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

BRAZILIAN_NEWS_FEEDS = [
    {"url": "https://g1.globo.com/rss/g1/", "label": "G1"},
    {"url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "label": "Folha de S.Paulo"},
    {"url": "https://www.uol.com.br/feed/", "label": "UOL"},
    {"url": "https://oglobo.globo.com/rss/oglobo/", "label": "O Globo"},
    {"url": "https://www.estadao.com.br/rss/politica.xml", "label": "Estadão"},
    {"url": "https://www.cnnbrasil.com.br/feed/", "label": "CNN Brasil"},
]

DEFAULT_MAX_ITEMS = 25
REQUEST_TIMEOUT = 20.0


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def _query_tokens(query: str) -> list[str]:
    """Extrai palavras significativas (3+ chars) para matching flexível."""
    return [t for t in re.findall(r"\w{3,}", query.lower()) if t not in {"para", "com", "que", "dos", "das", "uma", "por"}]


def _matches_query(text: str, query: str) -> bool:
    """Match por frase completa OU por pelo menos 2 tokens da busca."""
    lower = text.lower()
    q = query.lower().strip()
    if q in lower:
        return True
    tokens = _query_tokens(query)
    if not tokens:
        return q in lower
    hits = sum(1 for t in tokens if t in lower)
    return hits >= min(2, len(tokens))


def _entries_to_items(entries: list, source_label: str, query: str, max_items: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in entries:
        title = entry.get("title", "")
        summary = _strip_html(entry.get("summary", entry.get("description", "")))
        combined = f"{title}. {summary}".strip()

        if not _matches_query(combined, query):
            continue

        link = entry.get("link", "")
        items.append(
            {
                "source": "news",
                "text": combined[:500],
                "author": source_label,
                "created_at": entry.get("published", entry.get("updated", "")),
                "source_url": link,
                "source_label": source_label,
            }
        )
        if len(items) >= max_items:
            break
    return items


def _fetch_google_news_sync(query: str, max_items: int) -> list[dict[str, Any]]:
    url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
    try:
        parsed = feedparser.parse(url)
        items = _entries_to_items(parsed.entries, "Google Notícias", query, max_items)
        logger.info("Google News RSS: %d resultados para '%s'", len(items), query)
        return items
    except Exception as exc:
        logger.warning("Google News RSS: erro — %s", exc)
        return []


def _parse_static_feed(feed: dict, query: str, max_items: int) -> list[dict[str, Any]]:
    try:
        parsed = feedparser.parse(feed["url"])
        return _entries_to_items(parsed.entries, feed["label"], query, max_items)
    except Exception as exc:
        logger.warning("RSS %s: erro — %s", feed["label"], exc)
        return []


async def collect_news(query: str, max_items: int = DEFAULT_MAX_ITEMS) -> list[dict[str, Any]]:
    """Busca via Google News RSS + filtra feeds estáticos brasileiros."""
    google_task = asyncio.to_thread(_fetch_google_news_sync, query, max_items)
    static_tasks = [
        asyncio.to_thread(_parse_static_feed, feed, query, 5)
        for feed in BRAZILIAN_NEWS_FEEDS
    ]

    results = await asyncio.gather(google_task, *static_tasks, return_exceptions=True)

    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for result in results:
        if isinstance(result, Exception):
            logger.error("RSS: erro — %s", result)
            continue
        for item in result:
            url = item.get("source_url", item.get("text", "")[:50])
            if url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(item)

    logger.info("Notícias: %d menções coletadas para '%s'", len(items), query)
    return items[:max_items * 2]
