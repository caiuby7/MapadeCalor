"""Coletor Bluesky via endpoint público da AT Protocol API."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BSKY_SEARCH_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
DEFAULT_LIMIT = 50
REQUEST_TIMEOUT = 20.0


async def collect_bluesky(query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """
    Busca posts públicos sem autenticação.
    Retorna lista no schema unificado: source, text, author, created_at.
    """
    params = {
        "q": query,
        "limit": limit,
        "lang": "pt",
        "sort": "latest",
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(BSKY_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException:
        logger.warning("Bluesky: timeout ao buscar '%s'", query)
        return []
    except httpx.HTTPStatusError as exc:
        logger.warning("Bluesky: HTTP %d — %s", exc.response.status_code, exc.response.text[:200])
        return []
    except httpx.RequestError as exc:
        logger.warning("Bluesky: erro de rede — %s", exc)
        return []
    except Exception as exc:
        logger.error("Bluesky: erro inesperado — %s", exc)
        return []

    items: list[dict[str, Any]] = []

    for post in data.get("posts", []):
        record = post.get("record", {})
        text = record.get("text", "").strip()
        if not text:
            continue

        author_info = post.get("author", {})
        handle = author_info.get("handle", "")
        display_name = author_info.get("displayName") or handle

        uri = post.get("uri", "")
        post_id = uri.rsplit("/", 1)[-1] if uri else ""
        source_url = (
            f"https://bsky.app/profile/{handle}/post/{post_id}"
            if handle and post_id
            else ""
        )

        items.append(
            {
                "source": "bluesky",
                "text": text,
                "author": display_name,
                "created_at": record.get("createdAt", ""),
                "source_url": source_url,
            }
        )

    logger.info("Bluesky: %d menções coletadas para '%s'", len(items), query)
    return items
