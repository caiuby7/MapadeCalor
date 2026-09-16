"""Coleta de comentários públicos via YouTube Data API v3."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class YouTubeCollectorError(Exception):
    """Erro na integração com a YouTube Data API."""


def _get_youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def search_recent_videos(api_key: str, query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Pesquisa os vídeos mais recentes que correspondem à palavra-chave."""
    youtube = _get_youtube_client(api_key)
    try:
        response = (
            youtube.search()
            .list(
                q=query,
                part="id,snippet",
                type="video",
                order="date",
                maxResults=max_results,
                relevanceLanguage="pt",
                regionCode="BR",
            )
            .execute()
        )
    except HttpError as exc:
        raise YouTubeCollectorError(f"Falha na busca de vídeos: {exc}") from exc

    videos: list[dict[str, Any]] = []
    for item in response.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        snippet = item.get("snippet", {})
        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt"),
            }
        )
    return videos


def fetch_comment_threads(
    api_key: str,
    video_id: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Extrai os comentários mais recentes de um vídeo via commentThreads.list."""
    youtube = _get_youtube_client(api_key)
    try:
        response = (
            youtube.commentThreads()
            .list(
                part="snippet",
                videoId=video_id,
                maxResults=max_results,
                order="time",
                textFormat="plainText",
            )
            .execute()
        )
    except HttpError as exc:
        # Comentários desabilitados ou vídeo privado — não interrompe a coleta.
        logger.warning("Não foi possível listar comentários de %s: %s", video_id, exc)
        return []

    comments: list[dict[str, Any]] = []
    for item in response.get("items", []):
        top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = (top.get("textDisplay") or top.get("textOriginal") or "").strip()
        if not text:
            continue
        comments.append(
            {
                "comment_id": item.get("id"),
                "video_id": video_id,
                "author": top.get("authorDisplayName", "Anônimo"),
                "text": text,
                "published_at": top.get("publishedAt"),
                "like_count": top.get("likeCount", 0),
            }
        )
    return comments


def collect_comments(
    query: str,
    api_key: str | None = None,
    max_videos: int | None = None,
    max_comments_per_video: int | None = None,
) -> list[dict[str, Any]]:
    """
    Pipeline completo: busca vídeos pela palavra-chave e agrega comentários recentes.
    """
    api_key = api_key or os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key or api_key.startswith("sua_chave"):
        raise YouTubeCollectorError(
            "YOUTUBE_API_KEY não configurada. Defina a chave no arquivo .env "
            "ou ative DEMO_MODE=true para usar dados simulados."
        )

    max_videos = max_videos or int(os.getenv("MAX_VIDEOS", "5"))
    max_comments_per_video = max_comments_per_video or int(
        os.getenv("MAX_COMMENTS_PER_VIDEO", "20")
    )

    videos = search_recent_videos(api_key, query, max_results=max_videos)
    if not videos:
        logger.info("Nenhum vídeo encontrado para query=%s", query)
        return []

    all_comments: list[dict[str, Any]] = []
    for video in videos:
        threads = fetch_comment_threads(
            api_key,
            video["video_id"],
            max_results=max_comments_per_video,
        )
        for comment in threads:
            comment["video_title"] = video["title"]
            comment["channel"] = video["channel"]
            all_comments.append(comment)

    logger.info(
        "Coletados %s comentários de %s vídeos para query=%s",
        len(all_comments),
        len(videos),
        query,
    )
    return all_comments


def generate_demo_comments(query: str) -> list[dict[str, Any]]:
    """Comentários simulados com pistas geográficas brasileiras para modo demo."""
    now = datetime.now(timezone.utc).isoformat()
    samples = [
        (
            "Aqui em São Paulo a galera tá fervendo com isso, apoiamos demais!",
            "São Paulo",
        ),
        (
            "Em BH o povo tá indignado, que vergonha...",
            "Belo Horizonte",
        ),
        (
            "Do Rio de Janeiro: discurso forte, mas ainda tenho dúvidas.",
            "Rio de Janeiro",
        ),
        (
            "Curitiba aqui — parece marketing puro, não compro essa ideia.",
            "Curitiba",
        ),
        (
            "Salvador torcendo! Finalmente alguém fala a nossa língua.",
            "Salvador",
        ),
        (
            "Manaus tá acompanhando. Neutro por enquanto, vamos ver os fatos.",
            "Manaus",
        ),
        (
            "Porto Alegre rejeita esse tipo de postura. Absurdo total.",
            "Porto Alegre",
        ),
        (
            "Recife apoia! Mudança necessária e urgente.",
            "Recife",
        ),
        (
            "Brasília: político demais pra mim, sem opinião formada.",
            "Brasília",
        ),
        (
            "Fortaleza animada com o movimento, energia positiva demais.",
            "Fortaleza",
        ),
        (
            "Goiânia preocupada com o rumo disso. Não gosto nada.",
            "Goiânia",
        ),
        (
            "Belém acompanha de perto. Interessante, mas cautela.",
            "Belém",
        ),
        (
            "Florianópolis vibra! Conteúdo excelente sobre " + query,
            "Florianópolis",
        ),
        (
            "Vitória critica: só polêmica, zero proposta concreta.",
            "Vitória",
        ),
        (
            "Natal torce! Orgulho de ver esse debate no Nordeste.",
            "Natal",
        ),
        (
            "Cuiabá: mais um show midiático, cansativo.",
            "Cuiabá",
        ),
        (
            "João Pessoa apoiando firme. Boa análise!",
            "João Pessoa",
        ),
        (
            "Maceió em silêncio — não sei o que pensar ainda.",
            "Maceió",
        ),
        (
            "Teresina rejeita. Conteúdo tóxico e manipulador.",
            "Teresina",
        ),
        (
            "Campo Grande gosta da ousadia. Merece atenção.",
            "Campo Grande",
        ),
        (
            "Aracaju: péssimo exemplo pra juventude.",
            "Aracaju",
        ),
        (
            "Palmas curtiu a live. Bem colocadas as ideias.",
            "Palmas",
        ),
        (
            "Boa Vista acompanha. Parece ok, nada demais.",
            "Boa Vista",
        ),
        (
            "Macapá torcendo! Força total pro time.",
            "Macapá",
        ),
        (
            "Rio Branco: decepcionante. Esperava mais conteúdo.",
            "Rio Branco",
        ),
        (
            "São Luís apoia a causa. Mensagem clara e forte.",
            "São Luís",
        ),
        (
            "Porto Velho: discurso agressivo demais, não curto.",
            "Porto Velho",
        ),
        (
            "Aqui no Brasil a opinião tá dividida sobre " + query,
            "Brasília",
        ),
    ]

    comments: list[dict[str, Any]] = []
    for idx, (text, city) in enumerate(samples):
        comments.append(
            {
                "comment_id": f"demo-{idx}",
                "video_id": "demo-video",
                "author": f"Usuário {city}",
                "text": text,
                "published_at": now,
                "like_count": idx % 7,
                "video_title": f"Discussão sobre {query}",
                "channel": "Canal Demo",
                "_hint_city": city,
            }
        )
    return comments
