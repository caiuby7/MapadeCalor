"""Análise de sentimento e inferência geográfica via LLM."""

import json
import logging
import os
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# Capitais brasileiras — fallback quando a LLM não retorna coordenadas válidas
BRAZILIAN_CAPITALS: dict[str, dict[str, Any]] = {
    "rio branco, ac": {"lat": -9.9747, "lng": -67.8243},
    "maceió, al": {"lat": -9.6658, "lng": -35.735},
    "macapá, ap": {"lat": 0.0349, "lng": -51.0694},
    "manaus, am": {"lat": -3.119, "lng": -60.0217},
    "salvador, ba": {"lat": -12.9714, "lng": -38.5014},
    "fortaleza, ce": {"lat": -3.7172, "lng": -38.5433},
    "brasília, df": {"lat": -15.7942, "lng": -47.8822},
    "vitória, es": {"lat": -20.3155, "lng": -40.3128},
    "goiânia, go": {"lat": -16.6869, "lng": -49.2648},
    "são luís, ma": {"lat": -2.5387, "lng": -44.2825},
    "cuiabá, mt": {"lat": -15.6014, "lng": -56.0979},
    "campo grande, ms": {"lat": -20.4697, "lng": -54.6201},
    "belo horizonte, mg": {"lat": -19.9167, "lng": -43.9345},
    "belém, pa": {"lat": -1.4558, "lng": -48.5044},
    "joão pessoa, pb": {"lat": -7.1195, "lng": -34.845},
    "curitiba, pr": {"lat": -25.4284, "lng": -49.2733},
    "recife, pe": {"lat": -8.0476, "lng": -34.877},
    "teresina, pi": {"lat": -5.0892, "lng": -42.8019},
    "rio de janeiro, rj": {"lat": -22.9068, "lng": -43.1729},
    "natal, rn": {"lat": -5.7945, "lng": -35.211},
    "porto alegre, rs": {"lat": -30.0346, "lng": -51.2177},
    "porto velho, ro": {"lat": -8.7612, "lng": -63.9004},
    "boa vista, rr": {"lat": 2.8235, "lng": -60.6758},
    "florianópolis, sc": {"lat": -27.5954, "lng": -48.548},
    "são paulo, sp": {"lat": -23.5505, "lng": -46.6333},
    "aracaju, se": {"lat": -10.9472, "lng": -37.0731},
    "palmas, to": {"lat": -10.184, "lng": -48.3336},
}

DEFAULT_LOCATION = {
    "detected_location": "Brasil",
    "lat": -14.235,
    "lng": -51.9253,
}

SYSTEM_PROMPT = """Você é um analisador de sentimentos e geolocalização para comentários brasileiros do YouTube.
Analise o comentário e retorne APENAS um JSON válido (sem markdown) com os campos:
- sentiment_score: float entre -1.0 (muito negativo) e 1.0 (muito positivo)
- sentiment_label: "positivo", "neutro" ou "negativo"
- detected_location: cidade e estado brasileiro inferidos do texto (ex: "São Paulo, SP"). Use "Brasil" se não houver indício.
- lat: latitude da cidade inferida (float)
- lng: longitude da cidade inferida (float)

Considere gírias, ironia e contexto político brasileiro. Infira localização por menções a cidades, estados, times, sotaques ou expressões regionais."""


class AnalyzerError(Exception):
    """Erro na análise de sentimento."""


def _normalize_location_key(location: str) -> str:
    return re.sub(r"\s+", " ", location.strip().lower())


def resolve_coordinates(location: str | None, lat: float | None, lng: float | None) -> dict[str, Any]:
    """Garante coordenadas válidas usando o dicionário de capitais como fallback."""
    if lat is not None and lng is not None and -35 <= lat <= 6 and -75 <= lng <= -30:
        return {
            "detected_location": location or DEFAULT_LOCATION["detected_location"],
            "lat": lat,
            "lng": lng,
        }

    if location:
        key = _normalize_location_key(location)
        if key in BRAZILIAN_CAPITALS:
            coords = BRAZILIAN_CAPITALS[key]
            return {"detected_location": location, "lat": coords["lat"], "lng": coords["lng"]}

        for capital_key, coords in BRAZILIAN_CAPITALS.items():
            city = capital_key.split(",")[0]
            if city in key or key.split(",")[0] in capital_key:
                return {
                    "detected_location": location,
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                }

    return DEFAULT_LOCATION.copy()


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AnalyzerError(
            "OPENAI_API_KEY não configurada. Defina a variável no arquivo .env"
        )
    return OpenAI(api_key=api_key)


def _parse_llm_response(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AnalyzerError(f"Resposta da LLM não é JSON válido: {raw[:200]}") from exc

    score = float(data.get("sentiment_score", 0))
    score = max(-1.0, min(1.0, score))

    label = str(data.get("sentiment_label", "neutro")).lower()
    if label not in ("positivo", "neutro", "negativo"):
        label = "positivo" if score > 0.15 else "negativo" if score < -0.15 else "neutro"

    location = data.get("detected_location")
    lat = data.get("lat")
    lng = data.get("lng")

    try:
        lat_f = float(lat) if lat is not None else None
        lng_f = float(lng) if lng is not None else None
    except (TypeError, ValueError):
        lat_f, lng_f = None, None

    coords = resolve_coordinates(location, lat_f, lng_f)

    return {
        "sentiment_score": score,
        "sentiment_label": label,
        **coords,
    }


def analyze_comment(text: str, author: str = "") -> dict[str, Any]:
    """Envia um comentário à LLM e retorna análise estruturada."""
    client = _get_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    user_content = f"Autor: {author}\nComentário: {text}"

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        raw = response.choices[0].message.content or ""
    except Exception as exc:
        logger.exception("Falha na chamada OpenAI")
        raise AnalyzerError(f"Erro na análise via LLM: {exc}") from exc

    return _parse_llm_response(raw)


def _rule_based_fallback(text: str) -> dict[str, Any]:
    """Fallback heurístico quando a API OpenAI não está disponível."""
    lower = text.lower()
    positive_words = {"amo", "top", "incrível", "melhor", "parabéns", "genial", "excelente", "adorei"}
    negative_words = {"ódio", "pior", "horrível", "lixo", "vergonha", "ridículo", "mentiroso", "fraco"}

    pos = sum(1 for w in positive_words if w in lower)
    neg = sum(1 for w in negative_words if w in lower)

    if pos > neg:
        score, label = 0.6, "positivo"
    elif neg > pos:
        score, label = -0.6, "negativo"
    else:
        score, label = 0.0, "neutro"

    location = None
    for capital_key in BRAZILIAN_CAPITALS:
        city = capital_key.split(",")[0]
        if city in lower:
            location = capital_key.title()
            break

    coords = resolve_coordinates(location, None, None)
    return {"sentiment_score": score, "sentiment_label": label, **coords}


def analyze_comments(comments: list[dict[str, Any]], use_fallback: bool = False) -> list[dict[str, Any]]:
    """Analisa uma lista de comentários e retorna pontos para o mapa de calor."""
    results: list[dict[str, Any]] = []

    for comment in comments:
        text = comment.get("text", "").strip()
        if not text:
            continue

        author = comment.get("author", "")

        try:
            if use_fallback:
                analysis = _rule_based_fallback(text)
            else:
                analysis = analyze_comment(text, author)
        except AnalyzerError:
            logger.warning("Usando fallback heurístico para comentário")
            analysis = _rule_based_fallback(text)

        results.append(
            {
                "lat": analysis["lat"],
                "lng": analysis["lng"],
                "intensity": abs(analysis["sentiment_score"]) if analysis["sentiment_score"] != 0 else 0.3,
                "sentiment": analysis["sentiment_label"],
                "sentiment_score": analysis["sentiment_score"],
                "location": analysis.get("detected_location", "Brasil"),
                "text": text[:300],
                "author": author,
                "video_title": comment.get("video_title", ""),
            }
        )

    return results
