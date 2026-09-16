"""Coletor YouTube — Data API v3 ou fallback Invidious (gratuito, sem chave)."""

import asyncio
import logging
import os
from typing import Any

import httpx
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import is_valid_key

logger = logging.getLogger(__name__)

DEFAULT_MAX_VIDEOS = 5
DEFAULT_MAX_COMMENTS = 15
REQUEST_TIMEOUT = 20.0

INVIDIOUS_INSTANCES = [
    "https://yewtu.be",
    "https://invidious.nerdvpn.de",
    "https://inv.nadeko.net",
]


def _build_google_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not is_valid_key(api_key):
        return None
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _collect_google_sync(query: str, max_videos: int, max_comments: int) -> list[dict[str, Any]]:
    youtube = _build_google_client()
    if not youtube:
        return []

    items: list[dict[str, Any]] = []

    try:
        search = (
            youtube.search()
            .list(part="snippet", q=query, type="video", order="relevance",
                  maxResults=max_videos, relevanceLanguage="pt", regionCode="BR")
            .execute()
        )
    except HttpError as exc:
        logger.error("YouTube API: %s", exc.reason)
        return []

    for video in search.get("items", []):
        video_id = video["id"]["videoId"]
        try:
            threads = (
                youtube.commentThreads()
                .list(part="snippet", videoId=video_id, order="relevance",
                      maxResults=max_comments, textFormat="plainText")
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status != 403:
                logger.warning("YouTube comentários %s: %s", video_id, exc.reason)
            continue

        for thread in threads.get("items", []):
            snippet = thread["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "").strip()
            if text:
                items.append({
                    "source": "youtube", "text": text,
                    "author": snippet.get("authorDisplayName", ""),
                    "created_at": snippet.get("publishedAt", ""),
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "source_label": "YouTube",
                })

    return items


async def _collect_invidious(query: str, max_videos: int, max_comments: int) -> list[dict[str, Any]]:
    """Fallback gratuito via Invidious quando não há YOUTUBE_API_KEY."""
    items: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for base in INVIDIOUS_INSTANCES:
            try:
                resp = await client.get(f"{base}/api/v1/search", params={"q": query, "type": "video"})
                if resp.status_code != 200:
                    continue

                videos = resp.json()[:max_videos]
                for video in videos:
                    video_id = video.get("videoId", "")
                    title = video.get("title", "")

                    # Inclui o título do vídeo como menção
                    if title:
                        items.append({
                            "source": "youtube", "text": title,
                            "author": video.get("author", ""),
                            "created_at": "",
                            "source_url": f"https://www.youtube.com/watch?v={video_id}",
                            "source_label": "YouTube",
                        })

                    # Busca comentários do vídeo
                    if video_id:
                        try:
                            c_resp = await client.get(f"{base}/api/v1/comments/{video_id}")
                            if c_resp.status_code == 200:
                                comments = c_resp.json().get("comments", [])[:max_comments]
                                for c in comments:
                                    text = c.get("comment", "").strip() or c.get("content", "").strip()
                                    if text:
                                        items.append({
                                            "source": "youtube", "text": text,
                                            "author": c.get("author", ""),
                                            "created_at": "",
                                            "source_url": f"https://www.youtube.com/watch?v={video_id}",
                                            "source_label": "YouTube",
                                        })
                        except Exception:
                            pass

                if items:
                    logger.info("YouTube Invidious (%s): %d menções", base, len(items))
                    return items

            except Exception as exc:
                logger.debug("Invidious %s: %s", base, exc)

    return items


async def collect_youtube(
    query: str,
    max_videos: int = DEFAULT_MAX_VIDEOS,
    max_comments: int = DEFAULT_MAX_COMMENTS,
) -> list[dict[str, Any]]:
    if is_valid_key(os.getenv("YOUTUBE_API_KEY")):
        items = await asyncio.to_thread(_collect_google_sync, query, max_videos, max_comments)
        if items:
            logger.info("YouTube API: %d menções para '%s'", len(items), query)
            return items

    logger.info("YouTube: usando fallback Invidious (sem API key)")
    items = await _collect_invidious(query, max_videos, max_comments)
    logger.info("YouTube: %d menções para '%s'", len(items), query)
    return items
