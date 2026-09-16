"""Coleta de posts do Bluesky via AT Protocol (API pública)."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BSKY_PUBLIC_API = os.getenv("BLUESKY_API_URL", "https://public.api.bsky.app")
DEFAULT_LIMIT = 25


async def _get_auth_headers() -> dict[str, str]:
    """Autentica opcionalmente para endpoints que exigem sessão."""
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        return {}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BSKY_PUBLIC_API}/xrpc/com.atproto.server.createSession",
                json={"identifier": handle, "password": password},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"Authorization": f"Bearer {data['accessJwt']}"}
    except Exception as exc:
        logger.warning("Bluesky: falha na autenticação — %s", exc)

    return {}


async def collect_bluesky(query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Busca posts via app.bsky.feed.searchPosts (endpoint público)."""
    items: list[dict[str, Any]] = []
    headers = await _get_auth_headers()

    params = {"q": query, "limit": limit, "lang": "pt"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.searchPosts",
                params=params,
                headers=headers,
            )
            if resp.status_code != 200:
                logger.error("Bluesky: HTTP %d — %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
    except Exception as exc:
        logger.error("Bluesky: erro na requisição — %s", exc)
        return []

    for post in data.get("posts", []):
        record = post.get("record", {})
        text = record.get("text", "").strip()
        if not text:
            continue

        author = post.get("author", {})
        handle = author.get("handle", "")
        display_name = author.get("displayName", handle)

        # Bluesky não expõe localização diretamente; usamos descrição do perfil se houver
        author_location = ""

        uri = post.get("uri", "")
        post_id = uri.split("/")[-1] if uri else ""
        profile_handle = handle.replace(".bsky.social", "")
        source_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if post_id else f"https://bsky.app/profile/{handle}"

        items.append(
            {
                "source": "bluesky",
                "source_label": "Bluesky",
                "source_url": source_url,
                "text": text,
                "author": display_name,
                "author_location_raw": author_location,
                "published_at": record.get("createdAt", ""),
                "context_title": f"@{handle}",
            }
        )

    logger.info("Bluesky: %d menções para '%s'", len(items), query)
    return items
