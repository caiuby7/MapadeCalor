"""Coleta de posts e comentários do Reddit via API REST."""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BRAZILIAN_SUBREDDITS = ["brasil", "conversas", "Brasilivre", "desabafos"]
DEFAULT_LIMIT_PER_SUB = 10


async def _get_reddit_token(client: httpx.AsyncClient) -> str | None:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    user_agent = os.getenv("REDDIT_USER_AGENT", "MapaDeCalor/1.0")

    try:
        resp = await client.post(
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": user_agent},
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception as exc:
        logger.error("Reddit: falha no token — %s", exc)

    return None


def _matches_query(text: str, query: str) -> bool:
    return query.lower() in text.lower()


async def collect_reddit(
    query: str,
    subreddits: list[str] | None = None,
    limit_per_sub: int = DEFAULT_LIMIT_PER_SUB,
) -> list[dict[str, Any]]:
    """Busca posts e comentários recentes nos subreddits brasileiros."""
    items: list[dict[str, Any]] = []
    subs = subreddits or BRAZILIAN_SUBREDDITS
    user_agent = os.getenv("REDDIT_USER_AGENT", "MapaDeCalor/1.0")

    async with httpx.AsyncClient(timeout=20) as client:
        token = await _get_reddit_token(client)
        if not token:
            logger.warning("Reddit: REDDIT_CLIENT_ID/SECRET não configurados")
            return []

        headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent}

        for sub in subs:
            try:
                resp = await client.get(
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
                if resp.status_code != 200:
                    logger.warning("Reddit r/%s: HTTP %d", sub, resp.status_code)
                    continue

                for child in resp.json().get("data", {}).get("children", []):
                    post = child.get("data", {})
                    title = post.get("title", "")
                    selftext = post.get("selftext", "")
                    combined = f"{title}. {selftext}".strip()

                    if not _matches_query(combined, query):
                        continue

                    permalink = post.get("permalink", "")
                    items.append(
                        {
                            "source": "reddit",
                            "source_label": f"Reddit r/{sub}",
                            "source_url": f"https://www.reddit.com{permalink}",
                            "text": combined[:500],
                            "author": post.get("author", ""),
                            "author_location_raw": "",
                            "published_at": str(post.get("created_utc", "")),
                            "context_title": title,
                        }
                    )

                # Comentários do subreddit via search global restrito
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
                        if not body or not _matches_query(body, query):
                            continue

                        permalink = comment.get("permalink", "")
                        items.append(
                            {
                                "source": "reddit",
                                "source_label": f"Reddit r/{sub}",
                                "source_url": f"https://www.reddit.com{permalink}",
                                "text": body[:500],
                                "author": comment.get("author", ""),
                                "author_location_raw": "",
                                "published_at": str(comment.get("created_utc", "")),
                                "context_title": f"Comentário em r/{sub}",
                            }
                        )

            except Exception as exc:
                logger.error("Reddit r/%s: %s", sub, exc)

    logger.info("Reddit: %d menções para '%s'", len(items), query)
    return items
