"""Coleta de comentários públicos do YouTube via Data API v3."""

import logging
import os
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

DEFAULT_MAX_VIDEOS = 5
DEFAULT_MAX_COMMENTS_PER_VIDEO = 20


class YouTubeCollectorError(Exception):
    """Erro na coleta de dados do YouTube."""


def _get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise YouTubeCollectorError(
            "YOUTUBE_API_KEY não configurada. Defina a variável no arquivo .env"
        )
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def search_videos(
    query: str,
    max_results: int = DEFAULT_MAX_VIDEOS,
) -> list[dict[str, Any]]:
    """Busca os vídeos mais recentes relacionados à palavra-chave."""
    youtube = _get_youtube_client()

    try:
        response = (
            youtube.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                order="date",
                maxResults=max_results,
                relevanceLanguage="pt",
                regionCode="BR",
            )
            .execute()
        )
    except HttpError as exc:
        logger.exception("Falha ao buscar vídeos no YouTube")
        raise YouTubeCollectorError(f"Erro na busca de vídeos: {exc.reason}") from exc

    videos: list[dict[str, Any]] = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
            }
        )
    return videos


def fetch_comments(
    video_id: str,
    max_results: int = DEFAULT_MAX_COMMENTS_PER_VIDEO,
) -> list[dict[str, Any]]:
    """Extrai comentários de um vídeo via commentThreads.list."""
    youtube = _get_youtube_client()
    comments: list[dict[str, Any]] = []

    try:
        response = (
            youtube.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                order="time",
                maxResults=max_results,
                textFormat="plainText",
            )
            .execute()
        )
    except HttpError as exc:
        if exc.resp.status == 403:
            logger.warning("Comentários desabilitados ou indisponíveis para %s", video_id)
            return []
        logger.exception("Falha ao buscar comentários do vídeo %s", video_id)
        raise YouTubeCollectorError(f"Erro ao buscar comentários: {exc.reason}") from exc

    for item in response.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append(
            {
                "comment_id": item["id"],
                "video_id": video_id,
                "text": snippet.get("textDisplay", ""),
                "author": snippet.get("authorDisplayName", ""),
                "published_at": snippet.get("publishedAt", ""),
                "like_count": snippet.get("likeCount", 0),
            }
        )
    return comments


def collect_comments_for_query(
    query: str,
    max_videos: int = DEFAULT_MAX_VIDEOS,
    max_comments_per_video: int = DEFAULT_MAX_COMMENTS_PER_VIDEO,
) -> list[dict[str, Any]]:
    """Pipeline completo: busca vídeos e agrega comentários."""
    videos = search_videos(query, max_results=max_videos)
    if not videos:
        logger.warning("Nenhum vídeo encontrado para a query: %s", query)
        return []

    all_comments: list[dict[str, Any]] = []
    for video in videos:
        comments = fetch_comments(video["video_id"], max_results=max_comments_per_video)
        for comment in comments:
            comment["video_title"] = video["title"]
            comment["channel_title"] = video["channel_title"]
        all_comments.extend(comments)

    logger.info(
        "Coletados %d comentários de %d vídeos para '%s'",
        len(all_comments),
        len(videos),
        query,
    )
    return all_comments
