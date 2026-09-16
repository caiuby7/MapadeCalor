# Mapa de Calor de Sentimentos (YouTube)

MVP full stack para coletar comentários públicos do YouTube, analisar sentimento com geolocalização aproximada no Brasil e visualizar o resultado em um mapa de calor interativo (Leaflet).

## Arquitetura

```
├── backend/
│   ├── main.py             # FastAPI + CORS + GET /api/heatmap-data
│   ├── collector.py        # YouTube Data API v3 (search + commentThreads)
│   ├── analyzer.py         # Sentimento + geocoding (OpenAI/LLM + fallback)
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React (Vite) + Tailwind CDN + Leaflet Heat
│   ├── index.html
│   └── src/
└── README.md
```

| Camada | Stack |
|--------|--------|
| Backend | Python, FastAPI, google-api-python-client, Pydantic, OpenAI SDK |
| Frontend | React, Tailwind CSS (CDN), Leaflet.js, leaflet.heat |
| Mapas | OpenStreetMap, centrado no Brasil (`-14.2350, -51.9253`, zoom 4) |

## Pré-requisitos

- Python 3.10+
- Node.js 18+
- Chaves (opcionais para modo demo):
  - [YouTube Data API v3](https://console.cloud.google.com/apis/credentials)
  - [OpenAI API](https://platform.openai.com/api-keys) (ou endpoint compatível)

## Configuração

```bash
cp backend/.env.example backend/.env
```

Edite `backend/.env`:

| Variável | Descrição |
|----------|-----------|
| `YOUTUBE_API_KEY` | Chave da YouTube Data API v3 |
| `OPENAI_API_KEY` | Chave OpenAI (ou LLM compatível) |
| `OPENAI_BASE_URL` | Base URL (padrão `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Modelo (padrão `gpt-4o-mini`) |
| `DEMO_MODE` | `true` usa comentários simulados se não houver chave YouTube |
| `MAX_VIDEOS` | Vídeos recentes a pesquisar (padrão 5) |
| `MAX_COMMENTS_PER_VIDEO` | Comentários por vídeo (padrão 20) |

Sem chaves válidas e com `DEMO_MODE=true`, a API responde com dados simulados cobrindo capitais brasileiras — ideal para validar o frontend.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # se ainda não copiou
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /api/health` — status e se as chaves estão configuradas
- `GET /api/heatmap-data?query=Pablo%20Marçal` — coleta + análise + pontos do heatmap

Exemplo de ponto retornado:

```json
{
  "lat": -23.5505,
  "lng": -46.6333,
  "intensity": 0.8,
  "sentiment": "positivo",
  "sentiment_score": 0.75,
  "text": "...",
  "location": "São Paulo, SP"
}
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`. O Vite faz proxy de `/api` para `http://127.0.0.1:8000`.

Build de produção:

```bash
cd frontend && npm run build
```

Com o backend rodando, o FastAPI também pode servir `frontend/dist` na raiz `/` se a pasta existir.

## Uso do dashboard

1. Digite a palavra-chave (ex.: `Pablo Marçal`).
2. Clique em **Atualizar Mapa**.
3. Alterne o modo de calor:
   - **Densidade Geral** — volume total
   - **Calor Positivo** — peso maior para sentimento favorável (verde)
   - **Calor Negativo** — peso maior para crítica/rejeição (vermelho)
4. Clique nos marcadores para ler o comentário e a cidade inferida.

## Pipeline de análise

1. **Coleta** (`collector.py`): `search.list` (vídeos recentes) → `commentThreads.list`.
2. **Análise** (`analyzer.py`): LLM retorna JSON com `sentiment_score` (−1..+1), `sentiment_label`, `detected_location`, `lat`, `lng`.
3. **Fallback**: se a LLM falhar ou o local for nulo, usa heurística lexica + dicionário de capitais brasileiras.

## Tratamento de erros de API

- Sem `YOUTUBE_API_KEY` e `DEMO_MODE=false` → HTTP 503 com mensagem clara.
- Comentários desabilitados em um vídeo → vídeo ignorado, coleta segue.
- Sem `OPENAI_API_KEY` → análise heurística + geocoding por dicionário.
- CORS liberado para consumo do frontend local.

## Licença

MVP educacional — use respeitando os termos da YouTube Data API e da OpenAI.
