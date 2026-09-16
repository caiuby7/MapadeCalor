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

## Configuração rápida

```bash
cd backend
chmod +x setup.sh && ./setup.sh
```

Guia completo passo a passo: **[SETUP.md](SETUP.md)**

### Chaves (todas gratuitas)

| Variável | Para quê | Onde obter |
|----------|----------|-----------|
| `GROQ_API_KEY` | Sentimento via LLM (recomendado) | [console.groq.com](https://console.groq.com) |
| `YOUTUBE_API_KEY` | Comentários do YouTube | [Google Cloud](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| `REDDIT_CLIENT_ID/SECRET` | Posts do Reddit | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |

**Sem chave:** Notícias (Google News) + Bluesky funcionam imediatamente.

No dashboard, clique **"Ver dicas de configuração"** para ver o status de cada API.

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
