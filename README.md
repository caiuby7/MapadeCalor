# Mapa de Calor — Monitoramento de Menções na Web

MVP full stack para coletar menções do **YouTube** e **Bluesky**, classificar sentimento via LLM (Groq/OpenAI) e visualizar em mapa de calor geográfico.

## Estrutura

```
├── backend/
│   ├── main.py
│   ├── collectors/
│   │   ├── __init__.py      # Orquestrador async (asyncio.gather)
│   │   ├── bluesky.py       # AT Protocol API pública
│   │   └── youtube.py       # YouTube Data API v3
│   ├── analyzer.py          # Sentimento + geolocalização (Groq/OpenAI)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html           # Leaflet + leaflet-heat
```

## Schema unificado de coleta

```json
{
  "source": "bluesky",
  "text": "Texto da menção",
  "author": "Nome do autor",
  "created_at": "2026-01-01T12:00:00.000Z",
  "source_url": "https://..."
}
```

## Configuração

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `YOUTUBE_API_KEY` | Não* | Google Cloud Console — sem chave, YouTube retorna vazio |
| `GROQ_API_KEY` | Não* | [console.groq.com](https://console.groq.com) — recomendado |
| `OPENAI_API_KEY` | Não* | Alternativa à Groq |

\* Pelo menos uma chave LLM é recomendada; sem ela, usa fallback heurístico.

## Execução

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra **http://localhost:8000**

## API

### `GET /api/heatmap-data?query={termo}&sources=youtube,bluesky`

```json
{
  "points": [{
    "lat": -25.4284, "lng": -49.2733,
    "sentiment": "positivo", "sentiment_score": 0.65,
    "detected_city_uf": "Curitiba, PR",
    "source": "bluesky", "source_label": "Bluesky",
    "source_url": "https://bsky.app/...", "text": "..."
  }],
  "summary": {
    "total": 42,
    "sentiment_percentages": { "positivo": 45.0, "neutro": 30.0, "negativo": 25.0 },
    "by_source": { "bluesky": { "count": 20, "percentages": { ... } } }
  }
}
```

## Frontend

- Filtros por fonte (YouTube / Bluesky)
- Barra de percentuais de sentimento
- Breakdown por fonte com % positivo/neutro/negativo
- Feed lateral com badge da fonte e link
- Mapa com modos: Densidade, Calor Positivo, Calor Negativo

## Licença

MIT
