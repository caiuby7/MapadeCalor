# Mapa de Calor — Monitoramento de Sentimentos YouTube

MVP full stack para coletar comentários públicos do YouTube, analisar sentimento e geolocalização via LLM, e visualizar os dados em um mapa de calor interativo centrado no Brasil.

## Arquitetura

```
├── backend/
│   ├── main.py          # Servidor FastAPI e rotas
│   ├── collector.py     # Integração YouTube Data API v3
│   ├── analyzer.py      # NLP / Sentimento + Geocoding via OpenAI
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html       # Dashboard com mapa Leaflet + leaflet-heat
```

## Pré-requisitos

- Python 3.11+
- Chave da **YouTube Data API v3** ([Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com))
- Chave da **OpenAI API** ([platform.openai.com](https://platform.openai.com/api-keys))

> Sem a chave OpenAI, o sistema usa um fallback heurístico básico (menos preciso).

## Configuração

1. Clone o repositório e entre na pasta do backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

2. Copie o arquivo de ambiente e preencha as chaves:

```bash
cp .env.example .env
```

Edite `.env`:

```env
YOUTUBE_API_KEY=sua_chave_youtube
OPENAI_API_KEY=sua_chave_openai
OPENAI_MODEL=gpt-4o-mini
```

## Execução

Inicie o servidor FastAPI (que também serve o frontend):

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra no navegador: **http://localhost:8000**

## API

### `GET /api/health`

Verifica status e se as chaves estão configuradas.

### `GET /api/heatmap-data?query={termo}`

Coleta comentários do YouTube, analisa sentimento e retorna pontos para o mapa.

**Parâmetros:**

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `query` | string | obrigatório | Palavra-chave de busca |
| `max_videos` | int | 5 | Máximo de vídeos (1–10) |
| `max_comments` | int | 20 | Comentários por vídeo (1–50) |

**Resposta:**

```json
[
  {
    "lat": -23.5505,
    "lng": -46.6333,
    "intensity": 0.8,
    "sentiment": "positivo",
    "sentiment_score": 0.75,
    "location": "São Paulo, SP",
    "text": "Comentário...",
    "author": "Usuário",
    "video_title": "Título do vídeo"
  }
]
```

## Frontend

O dashboard oferece:

- Campo de busca com botão **Atualizar Mapa** e estado de carregamento
- Três modos de visualização:
  - **Densidade Geral** — volume total de comentários (gradiente azul)
  - **Calor Positivo** — peso para sentimento favorável (gradiente verde)
  - **Calor Negativo** — peso para sentimento crítico (gradiente vermelho)
- Mapa centrado no Brasil com tiles OpenStreetMap e camada `L.heatLayer`

## Como funciona a análise

1. O `collector.py` busca os vídeos mais recentes com a palavra-chave e extrai comentários via `commentThreads.list`.
2. O `analyzer.py` envia cada comentário à OpenAI com instruções para retornar JSON estruturado (sentimento + localização).
3. Um dicionário de 27 capitais brasileiras garante coordenadas válidas quando a inferência falha.
4. O frontend renderiza os pontos no mapa com gradientes configuráveis.

## Limitações do MVP

- Comentários do YouTube raramente contêm localização explícita — a geolocalização é inferida por contexto.
- A YouTube API tem cotas diárias; ajuste `max_videos` e `max_comments` conforme necessário.
- Vídeos com comentários desabilitados são ignorados silenciosamente.

## Licença

MIT
