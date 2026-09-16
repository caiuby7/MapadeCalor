"""Coletor Reddit via API REST gratuita (OAuth client_credentials)."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BRAZILIAN_SUBREDDITS = ["brasil", "conversas", "desabafos", "Brasilivre"]
DEFAULT_LIMIT = 15
REQUEST_TIMEOUT = 20.0


async def _get_token(client: httpx.AsyncClient) -> str | None:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("Reddit: REDDIT_CLIENT_ID/SECRET não configurados — retornando lista vazia")
        return None

    user_agent = os.getenv("REDDIT_USER_AGENT", "MapaDeCalor/1.0")

    try:
        resp = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": user_agent},
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.error("Reddit: falha ao obter token — %s", exc)
        return None


def _matches(text: str, query: str) -> bool:
    return query.lower() in text.lower()


async def collect_reddit(query: str, limit_per_sub: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Busca posts e comentários em subreddits brasileiros."""
    items: list[dict[str, Any]] = []
    user_agent = os.getenv("REDDIT_USER_AGENT", "MapaDeCalor/1.0")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            token = await _get_token(client)
            if not token:
                return []

            headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent}

            for sub in BRAZILIAN_SUBREDDITS:
                try:
                    post_resp = await client.get(
                        f"https://oauth.reddit.com/r/{sub}/search",
                        params={
                            "q": query,
                            "restrict_sr": "on",
                            "sort": "new",
                            "limit": limit_per_sub,
                            "t": "week",
                        },
                        headers=headers,
                    )
                    if post_resp.status_code == 200:
                        for child in post_resp.json().get("data", {}).get("children", []):
                            post = child.get("data", {})
                            title = post.get("title", "")
                            body = post.get("selftext", "")
                            combined = f"{title}. {body}".strip()
                            if not combined or not _matches(combined, query):
                                continue

                            permalink = post.get("permalink", "")
                            items.append(
                                {
                                    "source": "reddit",
                                    "text": combined[:500],
                                    "author": post.get("author", ""),
                                    "created_at": str(post.get("created_utc", "")),
                                    "source_url": f"https://www.reddit.com{permalink}",
                                    "source_label": f"Reddit r/{sub}",
                                }
                            )

                    comment_resp = await client.get(
                        "https://oauth.reddit.com/search",
                        params={
                            "q": query,
                            "restrict_sr": "on",
                            "sort": "new",
                            "limit": limit_per_sub,
                            "type": "comment",
                            "subreddit": sub,
                        },
                        headers=headers,
                    )
                    if comment_resp.status_code == 200:
                        for child in comment_resp.json().get("data", {}).get("children", []):
                            comment = child.get("data", {})
                            body = comment.get("body", "").strip()
                            if not body or not _matches(body, query):
                                continue

                            permalink = comment.get("permalink", "")
                            items.append(
                                {
                                    "source": "reddit",
                                    "text": body[:500],
                                    "author": comment.get("author", ""),
                                    "created_at": str(comment.get("created_utc", "")),
                                    "source_url": f"https://www.reddit.com{permalink}",
                                    "source_label": f"Reddit r/{sub}",
                                }
                            )

                except httpx.RequestError as exc:
                    logger.warning("Reddit r/%s: erro de rede — %s", sub, exc)

    except Exception as exc:
        logger.error("Reddit: erro inesperado — %s", exc)
        return []

    logger.info("Reddit: %d menções coletadas para '%s'", len(items), query)
    return items
