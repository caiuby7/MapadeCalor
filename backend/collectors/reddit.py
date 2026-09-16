"""Coletor Reddit — OAuth API ou fallback JSON público gratuito."""

import logging
import os
from typing import Any

import httpx

from config import is_valid_key

logger = logging.getLogger(__name__)

BRAZILIAN_SUBREDDITS = ["brasil", "conversas", "desabafos", "Brasilivre", "filmes"]
DEFAULT_LIMIT = 20
REQUEST_TIMEOUT = 20.0
USER_AGENT = os.getenv("REDDIT_USER_AGENT", "MapaDeCalor/1.0 (educational project)")


def _matches(text: str, query: str) -> bool:
    return query.lower() in text.lower()


async def _get_oauth_token(client: httpx.AsyncClient) -> str | None:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not is_valid_key(client_id) or not is_valid_key(client_secret):
        return None

    try:
        resp = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("Reddit OAuth: %s", exc)
        return None


def _parse_reddit_children(children: list, query: str, sub_label: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data", {})
        kind = child.get("kind")

        if kind == "t3":  # post
            title = data.get("title", "")
            body = data.get("selftext", "")
            text = f"{title}. {body}".strip()
        elif kind == "t1":  # comment
            text = data.get("body", "").strip()
        else:
            continue

        if not text or not _matches(text, query):
            continue

        permalink = data.get("permalink", "")
        items.append(
            {
                "source": "reddit",
                "text": text[:500],
                "author": data.get("author", ""),
                "created_at": str(data.get("created_utc", "")),
                "source_url": f"https://www.reddit.com{permalink}" if permalink else "",
                "source_label": sub_label,
            }
        )
    return items


async def _collect_public_json(client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
    """Fallback gratuito sem OAuth — reddit.com/search.json."""
    items: list[dict[str, Any]] = []
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "limit": DEFAULT_LIMIT, "type": "link,comment"},
            headers=headers,
        )
        if resp.status_code == 200:
            children = resp.json().get("data", {}).get("children", [])
            items.extend(_parse_reddit_children(children, query, "Reddit"))
            logger.info("Reddit público: %d resultados", len(items))
    except Exception as exc:
        logger.warning("Reddit público: %s", exc)

    for sub in BRAZILIAN_SUBREDDITS[:3]:
        try:
            resp = await client.get(
                f"https://www.reddit.com/r/{sub}/search.json",
                params={"q": query, "restrict_sr": "on", "sort": "new", "limit": 10},
                headers=headers,
            )
            if resp.status_code == 200:
                children = resp.json().get("data", {}).get("children", [])
                items.extend(_parse_reddit_children(children, query, f"Reddit r/{sub}"))
        except Exception:
            pass

    return items


async def _collect_oauth(client: httpx.AsyncClient, query: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}

    for sub in BRAZILIAN_SUBREDDITS:
        try:
            resp = await client.get(
                f"https://oauth.reddit.com/r/{sub}/search",
                params={"q": query, "restrict_sr": "on", "sort": "new", "limit": 15, "t": "month"},
                headers=headers,
            )
            if resp.status_code == 200:
                children = resp.json().get("data", {}).get("children", [])
                items.extend(_parse_reddit_children(children, query, f"Reddit r/{sub}"))
        except Exception as exc:
            logger.warning("Reddit r/%s: %s", sub, exc)

    return items


async def collect_reddit(query: str) -> list[dict[str, Any]]:
    """Busca posts/comentários via OAuth ou API JSON pública gratuita."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            token = await _get_oauth_token(client)
            if token:
                items = await _collect_oauth(client, query, token)
            else:
                items = await _collect_public_json(client, query)
    except Exception as exc:
        logger.error("Reddit: erro — %s", exc)
        return []

    logger.info("Reddit: %d menções para '%s'", len(items), query)
    return items
