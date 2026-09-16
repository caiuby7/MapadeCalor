"""Análise de sentimento e geolocalização via Groq / Hugging Face."""

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
    "detected_city_uf": "Brasil",
    "detected_location": "Brasil",
    "lat": -14.235,
    "lng": -51.9253,
}

SYSTEM_PROMPT = """Você analisa textos brasileiros de redes sociais e notícias.
Retorne APENAS JSON válido (sem markdown) com:
- sentiment_score: float de -1.0 (muito negativo) a 1.0 (muito positivo)
- sentiment_label: "positivo", "neutro" ou "negativo"
- detected_city_uf: cidade e UF inferidos (ex: "São Paulo, SP"). Use "Brasil" se não houver indício.
- lat: latitude float da cidade
- lng: longitude float da cidade

Considere gírias, ironia e contexto político brasileiro."""


class AnalyzerError(Exception):
    pass


def _normalize_location_key(location: str) -> str:
    return re.sub(r"\s+", " ", location.strip().lower())


def resolve_coordinates(
    location: str | None, lat: float | None, lng: float | None
) -> dict[str, Any]:
    if lat is not None and lng is not None and -35 <= lat <= 6 and -75 <= lng <= -30:
        city_uf = location or DEFAULT_LOCATION["detected_city_uf"]
        return {"detected_city_uf": city_uf, "detected_location": city_uf, "lat": lat, "lng": lng}

    if location:
        key = _normalize_location_key(location)
        if key in BRAZILIAN_CAPITALS:
            coords = BRAZILIAN_CAPITALS[key]
            return {
                "detected_city_uf": location,
                "detected_location": location,
                "lat": coords["lat"],
                "lng": coords["lng"],
            }
        for capital_key, coords in BRAZILIAN_CAPITALS.items():
            city = capital_key.split(",")[0]
            if city in key or key.split(",")[0] in capital_key:
                return {
                    "detected_city_uf": location,
                    "detected_location": location,
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                }

    return DEFAULT_LOCATION.copy()


def _parse_llm_response(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)
    score = max(-1.0, min(1.0, float(data.get("sentiment_score", 0))))

    label = str(data.get("sentiment_label", "neutro")).lower()
    if label not in ("positivo", "neutro", "negativo"):
        label = "positivo" if score > 0.15 else "negativo" if score < -0.15 else "neutro"

    city_uf = data.get("detected_city_uf") or data.get("detected_location")
    try:
        lat_f = float(data["lat"]) if data.get("lat") is not None else None
        lng_f = float(data["lng"]) if data.get("lng") is not None else None
    except (TypeError, ValueError):
        lat_f, lng_f = None, None

    coords = resolve_coordinates(city_uf, lat_f, lng_f)
    return {"sentiment_score": score, "sentiment_label": label, **coords}


async def _analyze_groq(text: str, author: str, location_hint: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise AnalyzerError("GROQ_API_KEY não configurada")

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    user_content = f"Autor: {author}\nLocalização conhecida: {location_hint or 'desconhecida'}\nTexto: {text}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.2,
                "max_tokens": 200,
            },
        )
        if resp.status_code != 200:
            raise AnalyzerError(f"Groq HTTP {resp.status_code}: {resp.text[:200]}")

        raw = resp.json()["choices"][0]["message"]["content"]
        return _parse_llm_response(raw)


async def _analyze_huggingface(text: str, author: str, location_hint: str) -> dict[str, Any]:
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise AnalyzerError("HUGGINGFACE_API_KEY não configurada")

    model = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    user_content = f"{SYSTEM_PROMPT}\n\nAutor: {author}\nLocal: {location_hint or 'desconhecida'}\nTexto: {text}"

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "inputs": user_content,
                "parameters": {"max_new_tokens": 200, "temperature": 0.2, "return_full_text": False},
            },
        )
        if resp.status_code != 200:
            raise AnalyzerError(f"HuggingFace HTTP {resp.status_code}: {resp.text[:200]}")

        result = resp.json()
        if isinstance(result, list):
            raw = result[0].get("generated_text", "")
        else:
            raw = result.get("generated_text", str(result))

        return _parse_llm_response(raw)


def _rule_based_fallback(text: str, location_hint: str = "") -> dict[str, Any]:
    lower = text.lower()
    positive = {"amo", "top", "incrível", "melhor", "parabéns", "genial", "excelente", "adorei", "apoio"}
    negative = {"ódio", "pior", "horrível", "lixo", "vergonha", "ridículo", "mentiroso", "fraco", "condeno"}

    pos = sum(1 for w in positive if w in lower)
    neg = sum(1 for w in negative if w in lower)

    if pos > neg:
        score, label = 0.6, "positivo"
    elif neg > pos:
        score, label = -0.6, "negativo"
    else:
        score, label = 0.0, "neutro"

    location = location_hint or None
    if not location:
        for capital_key in BRAZILIAN_CAPITALS:
            city = capital_key.split(",")[0]
            if city in lower:
                location = capital_key.title()
                break

    coords = resolve_coordinates(location, None, None)
    return {"sentiment_score": score, "sentiment_label": label, **coords}


async def analyze_item(item: dict[str, Any]) -> dict[str, Any]:
    """Analisa um item coletado e retorna ponto para o mapa."""
    text = item.get("text", "").strip()
    if not text:
        return {}

    author = item.get("author", "")
    location_hint = item.get("author_location_raw", "")

    analysis = None
    if os.getenv("GROQ_API_KEY"):
        try:
            analysis = await _analyze_groq(text, author, location_hint)
        except Exception as exc:
            logger.warning("Groq falhou, tentando HuggingFace: %s", exc)

    if analysis is None and os.getenv("HUGGINGFACE_API_KEY"):
        try:
            analysis = await _analyze_huggingface(text, author, location_hint)
        except Exception as exc:
            logger.warning("HuggingFace falhou, usando fallback: %s", exc)

    if analysis is None:
        analysis = _rule_based_fallback(text, location_hint)

    return {
        "lat": analysis["lat"],
        "lng": analysis["lng"],
        "intensity": abs(analysis["sentiment_score"]) if analysis["sentiment_score"] != 0 else 0.3,
        "sentiment": analysis["sentiment_label"],
        "sentiment_score": analysis["sentiment_score"],
        "location": analysis.get("detected_city_uf", "Brasil"),
        "text": text[:300],
        "author": author,
        "source": item.get("source", "unknown"),
        "source_label": item.get("source_label", item.get("source", "")),
        "source_url": item.get("source_url", ""),
        "context_title": item.get("context_title", ""),
    }


async def analyze_items(items: list[dict[str, Any]], concurrency: int = 5) -> list[dict[str, Any]]:
    """Analisa múltiplos itens com limite de concorrência."""
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any]] = []

    async def _process(item: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await analyze_item(item)

    tasks = [_process(item) for item in items]
    processed = await asyncio.gather(*tasks)

    for point in processed:
        if point:
            results.append(point)

    return results


def build_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Gera resumo com percentuais de sentimento e contagem por fonte."""
    total = len(points)
    if total == 0:
        return {
            "total": 0,
            "sentiment_percentages": {"positivo": 0, "neutro": 0, "negativo": 0},
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
        by_source[src][sentiment] = by_source[src].get(sentiment, 0) + 1

    percentages = {k: round(v / total * 100, 1) for k, v in counts.items()}

    for src_data in by_source.values():
        src_total = src_data["count"]
        if src_total > 0:
            src_data["percentages"] = {
                "positivo": round(src_data["positivo"] / src_total * 100, 1),
                "neutro": round(src_data["neutro"] / src_total * 100, 1),
                "negativo": round(src_data["negativo"] / src_total * 100, 1),
            }

    return {
        "total": total,
        "sentiment_percentages": percentages,
        "by_source": by_source,
    }
