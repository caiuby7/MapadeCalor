"""Análise de sentimento e inferência geográfica com LLM e fallback local."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator


BRAZIL_CAPITALS: dict[str, tuple[str, float, float]] = {
    "aracaju": ("Aracaju, SE", -10.9472, -37.0731),
    "belem": ("Belém, PA", -1.4558, -48.4902),
    "belo horizonte": ("Belo Horizonte, MG", -19.9167, -43.9345),
    "boa vista": ("Boa Vista, RR", 2.8235, -60.6758),
    "brasilia": ("Brasília, DF", -15.7939, -47.8828),
    "campo grande": ("Campo Grande, MS", -20.4697, -54.6201),
    "cuiaba": ("Cuiabá, MT", -15.6014, -56.0979),
    "curitiba": ("Curitiba, PR", -25.4284, -49.2733),
    "florianopolis": ("Florianópolis, SC", -27.5949, -48.5482),
    "fortaleza": ("Fortaleza, CE", -3.7319, -38.5267),
    "goiania": ("Goiânia, GO", -16.6869, -49.2648),
    "joao pessoa": ("João Pessoa, PB", -7.1195, -34.8450),
    "macapa": ("Macapá, AP", 0.0349, -51.0694),
    "maceio": ("Maceió, AL", -9.6498, -35.7089),
    "manaus": ("Manaus, AM", -3.1190, -60.0217),
    "natal": ("Natal, RN", -5.7945, -35.2110),
    "palmas": ("Palmas, TO", -10.2491, -48.3243),
    "porto alegre": ("Porto Alegre, RS", -30.0346, -51.2177),
    "porto velho": ("Porto Velho, RO", -8.7608, -63.8999),
    "recife": ("Recife, PE", -8.0476, -34.8770),
    "rio branco": ("Rio Branco, AC", -9.9754, -67.8249),
    "rio de janeiro": ("Rio de Janeiro, RJ", -22.9068, -43.1729),
    "salvador": ("Salvador, BA", -12.9777, -38.5016),
    "sao luis": ("São Luís, MA", -2.5307, -44.3068),
    "sao paulo": ("São Paulo, SP", -23.5505, -46.6333),
    "teresina": ("Teresina, PI", -5.0919, -42.8034),
    "vitoria": ("Vitória, ES", -20.3155, -40.3128),
}

DEFAULT_LOCATION = BRAZIL_CAPITALS["brasilia"]

POSITIVE_WORDS = {
    "adorei",
    "apoio",
    "bom",
    "excelente",
    "feliz",
    "gostei",
    "incrivel",
    "melhor",
    "otimo",
    "parabens",
}
NEGATIVE_WORDS = {
    "absurdo",
    "enganacao",
    "horrivel",
    "mentira",
    "odio",
    "pessimo",
    "ridiculo",
    "ruim",
    "triste",
    "vergonha",
}


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: Literal["positivo", "neutro", "negativo"]
    detected_location: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @field_validator("detected_location")
    @classmethod
    def location_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("localização vazia")
        return value.strip()


class SentimentAnalyzer:
    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.client = (
            AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key else None
        )

    async def analyze(self, text: str) -> AnalysisResult:
        """Usa a LLM quando disponível e sempre mantém um fallback determinístico."""
        fallback = local_analysis(text)
        if not self.client:
            return fallback

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Analise um comentário público em português do Brasil. "
                            "Retorne somente JSON com sentiment_score (-1 a 1), "
                            "sentiment_label (positivo, neutro ou negativo), "
                            "detected_location (Cidade, UF), lat e lng. Só infira uma "
                            "localização quando houver evidência textual; sem evidência, "
                            "use Brasília, DF (-15.7939, -47.8828). Não invente endereço "
                            "preciso nem use dados pessoais."
                        ),
                    },
                    {"role": "user", "content": text[:4000]},
                ],
            )
            content = response.choices[0].message.content or "{}"
            result = AnalysisResult.model_validate(json.loads(content))
            if not _inside_brazil(result.lat, result.lng):
                result.detected_location, result.lat, result.lng = DEFAULT_LOCATION
            result.sentiment_label = _label_for_score(result.sentiment_score)
            return result
        except Exception:
            # Indisponibilidade, rate limit ou JSON inválido não interrompem o lote.
            return fallback


def local_analysis(text: str) -> AnalysisResult:
    normalized = _normalize(text)
    tokens = set(re.findall(r"[a-z]+", normalized))
    positive = len(tokens & POSITIVE_WORDS)
    negative = len(tokens & NEGATIVE_WORDS)
    total = positive + negative
    score = (positive - negative) / total if total else 0.0

    location, lat, lng = DEFAULT_LOCATION
    for key, capital in BRAZIL_CAPITALS.items():
        if re.search(rf"\b{re.escape(key)}\b", normalized):
            location, lat, lng = capital
            break

    return AnalysisResult(
        sentiment_score=round(score, 3),
        sentiment_label=_label_for_score(score),
        detected_location=location,
        lat=lat,
        lng=lng,
    )


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )


def _label_for_score(score: float) -> Literal["positivo", "neutro", "negativo"]:
    if score > 0.15:
        return "positivo"
    if score < -0.15:
        return "negativo"
    return "neutro"


def _inside_brazil(lat: float, lng: float) -> bool:
    return -34.0 <= lat <= 5.5 and -74.0 <= lng <= -32.0
