# Mapa de Calor — Monitoramento de Sentimentos Multi-Fonte

MVP full stack que coleta menções de **YouTube**, **Bluesky**, **Reddit** e **feeds RSS de notícias**, analisa sentimento e geolocalização via LLM gratuita (Groq / Hugging Face) e visualiza em mapa de calor interativo.

## Arquitetura

```
├── backend/
│   ├── main.py              # FastAPI — rotas e CORS
│   ├── collector.py         # Orquestrador async (asyncio.gather)
│   ├── analyzer.py          # Sentimento + geolocalização (Groq/HF)
│   ├── sources/
│   │   ├── youtube.py       # YouTube Data API v3
│   │   ├── bluesky.py       # AT Protocol (searchPosts)
│   │   ├── reddit.py        # Reddit REST API
│   │   └── news.py          # RSS via feedparser
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html           # Leaflet + leaflet-heat + filtros
```

## Fontes de dados

| Fonte | API | Chave necessária? | Plano |
|-------|-----|-------------------|-------|
| YouTube | Data API v3 | Sim (`YOUTUBE_API_KEY`) | Gratuito (cota diária) |
| Bluesky | AT Protocol público | Não (credenciais opcionais) | Gratuito |
| Reddit | OAuth REST | Sim (`CLIENT_ID` + `SECRET`) | Gratuito |
| Notícias RSS | feedparser | Não | Gratuito |

## Formato padronizado de coleta

Cada fonte retorna:

```json
{
  "source": "youtube|bluesky|reddit|news",
  "source_label": "YouTube",
  "source_url": "https://...",
  "text": "...",
  "author": "...",
  "author_location_raw": "...",
  "context_title": "..."
}
```

## Configuração

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas chaves
```

### Chaves necessárias

| Variável | Onde obter |
|----------|-----------|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| `REDDIT_CLIENT_ID/SECRET` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipo "script") |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) (gratuito, Llama 3) |
| `HUGGINGFACE_API_KEY` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `BLUESKY_HANDLE/PASSWORD` | Opcional — busca pública funciona sem |

> Sem chave LLM, o sistema usa fallback heurístico. Fontes sem chave são ignoradas silenciosamente.

## Execução

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra **http://localhost:8000**

## API

### `GET /api/heatmap-data?query={termo}&sources=youtube,bluesky,reddit,news`

Coleta em paralelo, analisa e retorna:

```json
{
  "points": [
    {
      "lat": -23.5505,
      "lng": -46.6333,
      "intensity": 0.8,
      "sentiment": "positivo",
      "sentiment_score": 0.75,
      "source": "youtube",
      "source_label": "YouTube",
      "source_url": "https://youtube.com/...",
      "text": "...",
      "location": "São Paulo, SP"
    }
  ],
  "summary": {
    "total": 50,
    "sentiment_percentages": { "positivo": 40.0, "neutro": 35.0, "negativo": 25.0 },
    "by_source": {
      "youtube": { "count": 10, "label": "YouTube", "percentages": { "positivo": 50, "neutro": 30, "negativo": 20 } }
    }
  }
}
```

### `GET /api/health` — status das chaves configuradas

### `GET /api/sources` — lista de fontes disponíveis

## Frontend

- Filtros por fonte (checkboxes) — ative/desative YouTube, Bluesky, Reddit ou Notícias
- Barra de percentuais de sentimento (positivo / neutro / negativo)
- Breakdown por fonte com contagem e % de sentimento
- Feed lateral com menções, fonte de origem e link
- Três modos de calor: Densidade, Positivo (verde), Negativo (vermelho)

## Licença

MIT
