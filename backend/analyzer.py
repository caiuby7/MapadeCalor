"""Pipeline de NLP: sentimento + geolocalização aproximada via LLM."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)

# Capitais brasileiras — fallback garantido de coordenadas válidas.
BRAZIL_CAPITALS: dict[str, dict[str, float | str]] = {
    "São Paulo": {"lat": -23.5505, "lng": -46.6333, "state": "SP"},
    "Rio de Janeiro": {"lat": -22.9068, "lng": -43.1729, "state": "RJ"},
    "Belo Horizonte": {"lat": -19.9167, "lng": -43.9345, "state": "MG"},
    "Brasília": {"lat": -15.8267, "lng": -47.9218, "state": "DF"},
    "Salvador": {"lat": -12.9714, "lng": -38.5014, "state": "BA"},
    "Fortaleza": {"lat": -3.7172, "lng": -38.5433, "state": "CE"},
    "Curitiba": {"lat": -25.4284, "lng": -49.2733, "state": "PR"},
    "Recife": {"lat": -8.0476, "lng": -34.8770, "state": "PE"},
    "Porto Alegre": {"lat": -30.0346, "lng": -51.2177, "state": "RS"},
    "Manaus": {"lat": -3.1190, "lng": -60.0217, "state": "AM"},
    "Belém": {"lat": -1.4558, "lng": -48.4902, "state": "PA"},
    "Goiânia": {"lat": -16.6869, "lng": -49.2648, "state": "GO"},
    "Guarulhos": {"lat": -23.4538, "lng": -46.5333, "state": "SP"},
    "Campinas": {"lat": -22.9099, "lng": -47.0626, "state": "SP"},
    "São Luís": {"lat": -2.5307, "lng": -44.2825, "state": "MA"},
    "Maceió": {"lat": -9.6658, "lng": -35.7350, "state": "AL"},
    "Natal": {"lat": -5.7945, "lng": -35.2110, "state": "RN"},
    "Teresina": {"lat": -5.0892, "lng": -42.8019, "state": "PI"},
    "Campo Grande": {"lat": -20.4697, "lng": -54.6201, "state": "MS"},
    "João Pessoa": {"lat": -7.1195, "lng": -34.8450, "state": "PB"},
    "Cuiabá": {"lat": -15.6010, "lng": -56.0979, "state": "MT"},
    "Aracaju": {"lat": -10.9472, "lng": -37.0731, "state": "SE"},
    "Florianópolis": {"lat": -27.5954, "lng": -48.5480, "state": "SC"},
    "Vitória": {"lat": -20.3155, "lng": -40.3128, "state": "ES"},
    "Palmas": {"lat": -10.2491, "lng": -48.3243, "state": "TO"},
    "Boa Vista": {"lat": 2.8235, "lng": -60.6758, "state": "RR"},
    "Macapá": {"lat": 0.0349, "lng": -51.0694, "state": "AP"},
    "Rio Branco": {"lat": -9.9754, "lng": -67.8249, "state": "AC"},
    "Porto Velho": {"lat": -8.7612, "lng": -63.9000, "state": "RO"},
}

DEFAULT_LOCATION = {
    "detected_location": "Brasília, DF",
    "lat": -15.8267,
    "lng": -47.9218,
}

# Siglas de UF → capital correspondente (fallback de geocoding).
UF_TO_CAPITAL: dict[str, str] = {
    "SP": "São Paulo",
    "RJ": "Rio de Janeiro",
    "MG": "Belo Horizonte",
    "DF": "Brasília",
    "BA": "Salvador",
    "CE": "Fortaleza",
    "PR": "Curitiba",
    "PE": "Recife",
    "RS": "Porto Alegre",
    "AM": "Manaus",
    "PA": "Belém",
    "GO": "Goiânia",
    "MA": "São Luís",
    "AL": "Maceió",
    "RN": "Natal",
    "PI": "Teresina",
    "MS": "Campo Grande",
    "PB": "João Pessoa",
    "MT": "Cuiabá",
    "SE": "Aracaju",
    "SC": "Florianópolis",
    "ES": "Vitória",
    "TO": "Palmas",
    "RR": "Boa Vista",
    "AP": "Macapá",
    "AC": "Rio Branco",
    "RO": "Porto Velho",
}

SYSTEM_PROMPT = """Você analisa comentários públicos em português do Brasil.
Retorne APENAS um JSON válido (sem markdown) no formato:
{
  "sentiment_score": <float entre -1.0 e 1.0>,
  "sentiment_label": "positivo" | "neutro" | "negativo",
  "detected_location": "<Cidade, UF>" | null,
  "lat": <float> | null,
  "lng": <float> | null
}

Regras:
- sentiment_score: -1.0 muito negativo, 0 neutro, +1.0 muito positivo.
- sentiment_label deve ser consistente com o score (positivo > 0.2, negativo < -0.2, senão neutro).
- Inferir localização APENAS se o texto mencionar cidade/estado/região brasileira.
- Se não houver pista geográfica clara, use null em detected_location/lat/lng.
- Coordenadas devem ser de cidades brasileiras reais quando presentes.
"""


class AnalyzerError(Exception):
    """Erro no pipeline de análise."""


def _normalize_label(score: float, label: str | None = None) -> str:
    if label in {"positivo", "neutro", "negativo"}:
        return label
    if score > 0.2:
        return "positivo"
    if score < -0.2:
        return "negativo"
    return "neutro"


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return max(-1.0, min(1.0, score))


def resolve_coordinates(
    detected_location: str | None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    """
    Garante coordenadas válidas usando fallback de capitais brasileiras
    quando a inferência de local vier nula ou inválida.
    """
    if lat is not None and lng is not None:
        try:
            return {
                "detected_location": detected_location or "Brasil",
                "lat": float(lat),
                "lng": float(lng),
            }
        except (TypeError, ValueError):
            pass

    if detected_location:
        loc_lower = detected_location.lower()
        for city, meta in BRAZIL_CAPITALS.items():
            if city.lower() in loc_lower:
                return {
                    "detected_location": f"{city}, {meta['state']}",
                    "lat": float(meta["lat"]),
                    "lng": float(meta["lng"]),
                }
        # Tenta casar só o nome da cidade antes da vírgula.
        city_part = detected_location.split(",")[0].strip()
        for city, meta in BRAZIL_CAPITALS.items():
            if city.lower() == city_part.lower():
                return {
                    "detected_location": f"{city}, {meta['state']}",
                    "lat": float(meta["lat"]),
                    "lng": float(meta["lng"]),
                }

    return dict(DEFAULT_LOCATION)


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def _heuristic_sentiment(text: str) -> tuple[float, str]:
    positive = [
        "apoi",
        "ótimo",
        "otimo",
        "excelente",
        "amo",
        "parabéns",
        "parabens",
        "incrível",
        "incrivel",
        "forte",
        "animad",
        "curti",
        "gosto",
        "torc",
        "orgulho",
        "melhor",
        "positivo",
        "energia",
    ]
    negative = [
        "vergonha",
        "indign",
        "péssim",
        "pessimo",
        "ódio",
        "odio",
        "rejeit",
        "absurdo",
        "tóxico",
        "toxico",
        "decepcion",
        "preocup",
        "não gosto",
        "nao gosto",
        "critica",
        "pior",
        "manipul",
        "cansativ",
        "agressiv",
    ]
    lower = text.lower()
    pos = sum(1 for w in positive if w in lower)
    neg = sum(1 for w in negative if w in lower)
    if pos == 0 and neg == 0:
        return 0.0, "neutro"
    raw = (pos - neg) / max(pos + neg, 1)
    score = max(-1.0, min(1.0, raw * 0.85))
    return score, _normalize_label(score)


def _heuristic_location(text: str, hint_city: str | None = None) -> dict[str, Any]:
    if hint_city and hint_city in BRAZIL_CAPITALS:
        meta = BRAZIL_CAPITALS[hint_city]
        return {
            "detected_location": f"{hint_city}, {meta['state']}",
            "lat": float(meta["lat"]),
            "lng": float(meta["lng"]),
        }

    lower = text.lower()
    for city, meta in BRAZIL_CAPITALS.items():
        if city.lower() in lower:
            return {
                "detected_location": f"{city}, {meta['state']}",
                "lat": float(meta["lat"]),
                "lng": float(meta["lng"]),
            }

    # Casamento por sigla de UF (ex.: "em SP", "no RJ").
    for uf, city in UF_TO_CAPITAL.items():
        if re.search(rf"(?<![A-Za-z]){uf}(?![A-Za-z])", text, flags=re.IGNORECASE):
            meta = BRAZIL_CAPITALS[city]
            return {
                "detected_location": f"{city}, {meta['state']}",
                "lat": float(meta["lat"]),
                "lng": float(meta["lng"]),
            }

    return dict(DEFAULT_LOCATION)


def analyze_with_llm(text: str, client: OpenAI | None = None) -> dict[str, Any]:
    """Envia o texto para a LLM e retorna JSON estruturado de sentimento + local."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("sua_chave"):
        raise AnalyzerError(
            "OPENAI_API_KEY não configurada. Defina a chave no .env "
            "ou use DEMO_MODE / fallback heurístico."
        )

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Comentário:\n{text}"},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    data = _extract_json(raw)

    score = _clamp_score(data.get("sentiment_score", 0))
    label = _normalize_label(score, data.get("sentiment_label"))
    coords = resolve_coordinates(
        data.get("detected_location"),
        data.get("lat"),
        data.get("lng"),
    )

    return {
        "sentiment_score": score,
        "sentiment_label": label,
        "detected_location": coords["detected_location"],
        "lat": coords["lat"],
        "lng": coords["lng"],
    }


def analyze_comment(
    text: str,
    *,
    use_llm: bool = True,
    hint_city: str | None = None,
    client: OpenAI | None = None,
) -> dict[str, Any]:
    """
    Analisa um comentário. Tenta LLM; em falha, usa heurística + dicionário de capitais.
    """
    if use_llm:
        try:
            return analyze_with_llm(text, client=client)
        except Exception as exc:  # noqa: BLE001 — fallback intencional
            logger.warning("LLM indisponível, usando heurística: %s", exc)

    score, label = _heuristic_sentiment(text)
    coords = _heuristic_location(text, hint_city=hint_city)
    return {
        "sentiment_score": score,
        "sentiment_label": label,
        "detected_location": coords["detected_location"],
        "lat": coords["lat"],
        "lng": coords["lng"],
    }


def to_heatmap_point(comment: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Converte comentário + análise no formato agregado da API de heatmap."""
    score = float(analysis["sentiment_score"])
    # Intensidade 0..1 para o leaflet-heat (baseada no módulo do sentimento + leve boost).
    intensity = round(min(1.0, abs(score) * 0.7 + 0.3), 3)
    return {
        "lat": analysis["lat"],
        "lng": analysis["lng"],
        "intensity": intensity,
        "sentiment": analysis["sentiment_label"],
        "sentiment_score": score,
        "text": comment.get("text", "")[:280],
        "author": comment.get("author"),
        "location": analysis["detected_location"],
        "video_title": comment.get("video_title"),
    }


def analyze_comments(
    comments: list[dict[str, Any]],
    *,
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    """Processa uma lista de comentários e retorna pontos de heatmap."""
    points: list[dict[str, Any]] = []
    client: OpenAI | None = None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if use_llm and api_key and not api_key.startswith("sua_chave"):
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Não foi possível inicializar cliente OpenAI: %s", exc)
            use_llm = False

    for comment in comments:
        analysis = analyze_comment(
            comment.get("text", ""),
            use_llm=use_llm and client is not None,
            hint_city=comment.get("_hint_city"),
            client=client,
        )
        points.append(to_heatmap_point(comment, analysis))
    return points
