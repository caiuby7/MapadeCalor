# Mapa de Calor — Monitoramento de Menções na Web

MVP que coleta menções de **todas as APIs gratuitas de busca**, classifica sentimento via LLM e visualiza em mapa de calor geográfico.

## Fontes integradas (plano gratuito)

| Fonte | Coletor | Chave necessária? | Custo |
|-------|---------|-------------------|-------|
| **YouTube** | `collectors/youtube.py` | Sim (`YOUTUBE_API_KEY`) | Gratuito (cota diária) |
| **Bluesky** | `collectors/bluesky.py` | Não | Gratuito |
| **Reddit** | `collectors/reddit.py` | Sim (`CLIENT_ID` + `SECRET`) | Gratuito |
| **Notícias RSS** | `collectors/news.py` | Não | Gratuito |

> Fontes sem chave ou com chave ausente retornam lista vazia **sem abortar** as demais.

## Estrutura

```
backend/
├── main.py
├── collectors/
│   ├── __init__.py      # asyncio.gather — todas as fontes em paralelo
│   ├── youtube.py
│   ├── bluesky.py
│   ├── reddit.py
│   └── news.py
├── analyzer.py          # Groq / OpenAI + fallback capitais BR
└── frontend/index.html
```

## Schema unificado

```json
{
  "source": "bluesky",
  "text": "Texto da menção",
  "author": "Nome",
  "created_at": "2026-01-01T12:00:00Z",
  "source_url": "https://...",
  "source_label": "Bluesky"
}
```

## Configuração

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Chaves

| Variável | Onde obter |
|----------|-----------|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| `REDDIT_CLIENT_ID/SECRET` | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |

**Funciona imediatamente sem chave:** Bluesky + Notícias RSS (fallback heurístico de sentimento).

## Execução

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra **http://localhost:8000**

## API

### `GET /api/heatmap-data?query={termo}&sources=youtube,bluesky,reddit,news`

### `GET /api/sources` — lista fontes gratuitas disponíveis

### `GET /api/health` — status de cada API

## Frontend

- Checkboxes para ativar/desativar cada fonte no mapa
- Percentuais de sentimento (positivo / neutro / negativo)
- Breakdown por fonte com link para o site de origem
- Mapa Leaflet: Densidade, Calor Positivo, Calor Negativo

## Licença

MIT
