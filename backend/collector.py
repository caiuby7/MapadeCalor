"""Coleta de vídeos e comentários públicos com a YouTube Data API v3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubeCollectorError(RuntimeError):
    """Erro legível ocorrido durante a coleta."""


@dataclass(frozen=True)
class YouTubeComment:
    text: str
    video_id: str
    video_title: str
    author: str | None = None


class YouTubeCollector:
    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise YouTubeCollectorError(
                "YOUTUBE_API_KEY não configurada. Copie backend/.env.example para "
                "backend/.env e informe uma chave válida."
            )
        self._youtube = build(
            "youtube", "v3", developerKey=api_key, cache_discovery=False
        )

    def collect(
        self, query: str, max_videos: int = 5, max_comments: int = 100
    ) -> list[YouTubeComment]:
        """Pesquisa vídeos recentes e coleta comentários até o limite global."""
        if not query.strip():
            raise YouTubeCollectorError("O termo de busca não pode estar vazio.")

        try:
            search_response = (
                self._youtube.search()
                .list(
                    part="snippet",
                    q=query.strip(),
                    type="video",
                    order="date",
                    maxResults=min(max(max_videos, 1), 50),
                    relevanceLanguage="pt",
                    regionCode="BR",
                    safeSearch="moderate",
                )
                .execute()
            )

            comments: list[YouTubeComment] = []
            for item in search_response.get("items", []):
                if len(comments) >= max_comments:
                    break
                video_id = item["id"]["videoId"]
                title = item.get("snippet", {}).get("title", "Vídeo sem título")
                comments.extend(
                    self._comments_for_video(
                        video_id, title, max_comments - len(comments)
                    )
                )
            return comments
        except HttpError as exc:
            reason = _http_error_reason(exc)
            raise YouTubeCollectorError(f"Falha na YouTube Data API: {reason}") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise YouTubeCollectorError(
                "A YouTube Data API retornou dados em formato inesperado."
            ) from exc

    def _comments_for_video(
        self, video_id: str, title: str, limit: int
    ) -> list[YouTubeComment]:
        result: list[YouTubeComment] = []
        page_token: str | None = None

        while len(result) < limit:
            try:
                response = (
                    self._youtube.commentThreads()
                    .list(
                        part="snippet",
                        videoId=video_id,
                        order="time",
                        textFormat="plainText",
                        maxResults=min(100, limit - len(result)),
                        pageToken=page_token,
                    )
                    .execute()
                )
            except HttpError as exc:
                # Comentários desativados em um vídeo não devem cancelar toda a busca.
                if getattr(exc.resp, "status", None) in {403, 404}:
                    break
                raise

            for item in response.get("items", []):
                snippet = (
                    item.get("snippet", {})
                    .get("topLevelComment", {})
                    .get("snippet", {})
                )
                text = str(snippet.get("textOriginal", "")).strip()
                if text:
                    result.append(
                        YouTubeComment(
                            text=text,
                            video_id=video_id,
                            video_title=title,
                            author=snippet.get("authorDisplayName"),
                        )
                    )
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return result


def _http_error_reason(exc: HttpError) -> str:
    try:
        payload: Any = exc.error_details
        if payload:
            return str(payload[0].get("reason") or payload[0].get("message"))
    except (AttributeError, IndexError, TypeError):
        pass
    status = getattr(exc.resp, "status", "desconhecido")
    return f"HTTP {status}"
