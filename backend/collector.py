"""Orquestrador de coleta multi-fonte em paralelo."""

import asyncio
import logging
from typing import Any

from sources.bluesky import collect_bluesky
from sources.news import collect_news
from sources.reddit import collect_reddit
from sources.youtube import collect_youtube

logger = logging.getLogger(__name__)

# Formato padronizado de cada item coletado:
# {
#   "source": "youtube|bluesky|reddit|news",
#   "source_label": "YouTube",
#   "source_url": "https://...",
#   "text": "...",
#   "author": "...",
#   "author_location_raw": "...",
#   "published_at": "...",
#   "context_title": "...",
# }

AVAILABLE_SOURCES = ("youtube", "bluesky", "reddit", "news")

_SOURCE_COLLECTORS = {
    "youtube": collect_youtube,
    "bluesky": collect_bluesky,
    "reddit": collect_reddit,
    "news": collect_news,
}


async def _safe_collect(name: str, coro) -> list[dict[str, Any]]:
    """Executa um coletor isolando falhas para não derrubar as demais fontes."""
    try:
        result = await coro
        return result
    except Exception as exc:
        logger.error("Coletor %s falhou: %s", name, exc)
        return []


async def collect_all(
    query: str,
    sources: list[str] | None = None,
    max_videos: int = 5,
    max_comments: int = 15,
) -> list[dict[str, Any]]:
    """
    Coleta menções de múltiplas fontes em paralelo via asyncio.gather.
    Retorna lista unificada no formato padronizado.
    """
    active = sources or list(AVAILABLE_SOURCES)
    active = [s for s in active if s in _SOURCE_COLLECTORS]

    if not active:
        logger.warning("Nenhuma fonte válida selecionada")
        return []

    tasks = []
    for source in active:
        if source == "youtube":
            tasks.append(_safe_collect(source, collect_youtube(query, max_videos, max_comments)))
        else:
            tasks.append(_safe_collect(source, _SOURCE_COLLECTORS[source](query)))

    results = await asyncio.gather(*tasks)

    all_items: list[dict[str, Any]] = []
    for source, items in zip(active, results):
        logger.info("Fonte %s: %d itens", source, len(items))
        all_items.extend(items)

    logger.info("Total coletado: %d menções de %d fontes para '%s'", len(all_items), len(active), query)
    return all_items


def collect_all_sync(
    query: str,
    sources: list[str] | None = None,
    max_videos: int = 5,
    max_comments: int = 15,
) -> list[dict[str, Any]]:
    """Wrapper síncrono para uso em contextos sem event loop."""
    return asyncio.run(collect_all(query, sources, max_videos, max_comments))
