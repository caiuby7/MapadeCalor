"""Coleta de comentários do YouTube via Data API v3."""

import asyncio
import logging
import os
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

DEFAULT_MAX_VIDEOS = 5
DEFAULT_MAX_COMMENTS_PER_VIDEO = 15


def _build_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return None
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _collect_sync(query: str, max_videos: int, max_comments: int) -> list[dict[str, Any]]:
    youtube = _build_client()
    if not youtube:
        logger.warning("YouTube: YOUTUBE_API_KEY não configurada")
        return []

    items: list[dict[str, Any]] = []

    try:
        search = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                order="date",
                maxResults=max_videos,
                relevanceLanguage="pt",
                regionCode="BR",
            )
            .execute()
        )
    except HttpError as exc:
        logger.error("YouTube: erro na busca — %s", exc.reason)
        return []

    for video in search.get("items", []):
        video_id = video["id"]["videoId"]
        video_title = video["snippet"].get("title", "")

        try:
            threads = (
                youtube.commentThreads()
                .list(
                    part="snippet",
                    videoId=video_id,
                    order="time",
                    maxResults=max_comments,
                    textFormat="plainText",
                )
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status != 403:
                logger.warning("YouTube: erro nos comentários de %s — %s", video_id, exc.reason)
            continue

        for thread in threads.get("items", []):
            snippet = thread["snippet"]["topLevelComment"]["snippet"]
            text = snippet.get("textDisplay", "").strip()
            if not text:
                continue

            items.append(
                {
                    "source": "youtube",
                    "source_label": "YouTube",
                    "source_url": f"https://www.youtube.com/watch?v={video_id}",
                    "text": text,
                    "author": snippet.get("authorDisplayName", ""),
                    "author_location_raw": "",
                    "published_at": snippet.get("publishedAt", ""),
                    "context_title": video_title,
                }
            )

    logger.info("YouTube: %d menções para '%s'", len(items), query)
    return items


async def collect_youtube(
    query: str,
    max_videos: int = DEFAULT_MAX_VIDEOS,
    max_comments: int = DEFAULT_MAX_COMMENTS_PER_VIDEO,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_collect_sync, query, max_videos, max_comments)
