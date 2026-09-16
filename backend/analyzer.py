"""Classificação de sentimento e inferência de coordenadas via Groq / OpenAI."""

import asyncio
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

BRAZILIAN_CAPITALS: dict[str, dict[str, float]] = {
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

DEFAULT_LOCATION = {"detected_city_uf": "Brasil", "lat": -14.235, "lng": -51.9253}

SYSTEM_PROMPT = """Você analisa textos brasileiros de redes sociais.
Retorne APENAS JSON válido (sem markdown) com:
- sentiment_score: float de -1.0 (muito negativo) a 1.0 (muito positivo)
- sentiment_label: "positivo", "neutro" ou "negativo"
- detected_city_uf: cidade e UF inferidos (ex: "Curitiba, PR"). Use "Brasil" se não houver indício.
- lat: latitude float
- lng: longitude float

Considere gírias, ironia e contexto político brasileiro."""


def resolve_coordinates(
    city_uf: str | None, lat: float | None, lng: float | None
) -> dict[str, Any]:
    """Fallback em capitais brasileiras quando coordenadas são inválidas."""
    if lat is not None and lng is not None and -35 <= lat <= 6 and -75 <= lng <= -30:
        return {"detected_city_uf": city_uf or "Brasil", "lat": lat, "lng": lng}

    if city_uf:
        key = re.sub(r"\s+", " ", city_uf.strip().lower())
        if key in BRAZILIAN_CAPITALS:
            c = BRAZILIAN_CAPITALS[key]
            return {"detected_city_uf": city_uf, "lat": c["lat"], "lng": c["lng"]}
        for capital_key, coords in BRAZILIAN_CAPITALS.items():
            city = capital_key.split(",")[0]
            if city in key:
                return {"detected_city_uf": city_uf, "lat": coords["lat"], "lng": coords["lng"]}

    return DEFAULT_LOCATION.copy()


def _parse_llm_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)
    score = max(-1.0, min(1.0, float(data.get("sentiment_score", 0))))

    label = str(data.get("sentiment_label", "neutro")).lower()
    if label not in ("positivo", "neutro", "negativo"):
        label = "positivo" if score > 0.15 else "negativo" if score < -0.15 else "neutro"

    city_uf = data.get("detected_city_uf", "Brasil")
    try:
        lat = float(data["lat"]) if data.get("lat") is not None else None
        lng = float(data["lng"]) if data.get("lng") is not None else None
    except (TypeError, ValueError):
        lat, lng = None, None

    coords = resolve_coordinates(city_uf, lat, lng)
    return {"sentiment_score": score, "sentiment_label": label, **coords}


async def _call_groq(text: str, author: str) -> dict[str, Any]:
    from groq import AsyncGroq

    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Autor: {author}\nTexto: {text}"},
        ],
        temperature=0.2,
        max_tokens=200,
    )
    return _parse_llm_json(response.choices[0].message.content or "")


async def _call_openai(text: str, author: str) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Autor: {author}\nTexto: {text}"},
        ],
        temperature=0.2,
        max_tokens=200,
    )
    return _parse_llm_json(response.choices[0].message.content or "")


def _rule_based_fallback(text: str) -> dict[str, Any]:
    lower = text.lower()
    pos_words = {"amo", "top", "incrível", "melhor", "parabéns", "excelente", "adorei"}
    neg_words = {"ódio", "pior", "horrível", "lixo", "vergonha", "ridículo", "mentiroso"}

    pos = sum(1 for w in pos_words if w in lower)
    neg = sum(1 for w in neg_words if w in lower)

    if pos > neg:
        score, label = 0.6, "positivo"
    elif neg > pos:
        score, label = -0.6, "negativo"
    else:
        score, label = 0.0, "neutro"

    city_uf = None
    for capital_key in BRAZILIAN_CAPITALS:
        if capital_key.split(",")[0] in lower:
            city_uf = capital_key.title()
            break

    coords = resolve_coordinates(city_uf, None, None)
    return {"sentiment_score": score, "sentiment_label": label, **coords}


async def analyze_text(text: str, author: str = "") -> dict[str, Any]:
    """Classifica sentimento e infere localização de um texto."""
    if os.getenv("GROQ_API_KEY"):
        try:
            return await _call_groq(text, author)
        except Exception as exc:
            logger.warning("Groq falhou: %s", exc)

    if os.getenv("OPENAI_API_KEY"):
        try:
            return await _call_openai(text, author)
        except Exception as exc:
            logger.warning("OpenAI falhou: %s", exc)

    return _rule_based_fallback(text)


async def analyze_items(items: list[dict[str, Any]], concurrency: int = 8, max_items: int = 40) -> list[dict[str, Any]]:
    """Processa lista de menções e retorna pontos para o mapa de calor."""
    semaphore = asyncio.Semaphore(concurrency)
    points: list[dict[str, Any]] = []

    async def _process(item: dict[str, Any]) -> dict[str, Any] | None:
        text = item.get("text", "").strip()
        if not text:
            return None

        async with semaphore:
            analysis = await analyze_text(text, item.get("author", ""))

        source = item.get("source", "unknown")
        default_labels = {
            "youtube": "YouTube",
            "bluesky": "Bluesky",
            "reddit": "Reddit",
            "news": "Notícias",
        }

        return {
            "lat": analysis["lat"],
            "lng": analysis["lng"],
            "intensity": abs(analysis["sentiment_score"]) if analysis["sentiment_score"] else 0.3,
            "sentiment": analysis["sentiment_label"],
            "sentiment_score": analysis["sentiment_score"],
            "detected_city_uf": analysis["detected_city_uf"],
            "text": text[:300],
            "author": item.get("author", ""),
            "source": source,
            "source_label": item.get("source_label") or default_labels.get(source, source),
            "source_url": item.get("source_url", ""),
            "created_at": item.get("created_at", ""),
        }

    results = await asyncio.gather(*[_process(i) for i in items[:max_items]])
    points.extend(r for r in results if r)
    return points


def build_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Calcula percentuais de sentimento e breakdown por fonte."""
    total = len(points)
    if total == 0:
        return {
            "total": 0,
            "sentiment_percentages": {"positivo": 0.0, "neutro": 0.0, "negativo": 0.0},
            "by_source": {},
        }

    counts = {"positivo": 0, "neutro": 0, "negativo": 0}
    by_source: dict[str, dict[str, Any]] = {}

    for p in points:
        sentiment = p.get("sentiment", "neutro")
        counts[sentiment] = counts.get(sentiment, 0) + 1

        src = p.get("source", "unknown")
        if src not in by_source:
            by_source[src] = {
                "count": 0,
                "label": p.get("source_label", src),
                "positivo": 0,
                "neutro": 0,
                "negativo": 0,
            }
        by_source[src]["count"] += 1
        by_source[src][sentiment] += 1

    percentages = {k: round(v / total * 100, 1) for k, v in counts.items()}

    for data in by_source.values():
        n = data["count"]
        data["percentages"] = {
            "positivo": round(data["positivo"] / n * 100, 1),
            "neutro": round(data["neutro"] / n * 100, 1),
            "negativo": round(data["negativo"] / n * 100, 1),
        }

    return {"total": total, "sentiment_percentages": percentages, "by_source": by_source}
