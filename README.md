# Radar de Sentimentos

MVP full stack para coletar comentários públicos recentes do YouTube, analisar sentimento e localização aproximada e exibir os resultados em um mapa de calor interativo do Brasil.

## Stack

- FastAPI, Pydantic, OpenAI e YouTube Data API v3
- HTML5, Tailwind CSS, Leaflet e `leaflet-heat`
- Fallback local para sentimento e coordenadas das 27 capitais brasileiras

## Estrutura

```text
backend/
├── main.py
├── collector.py
├── analyzer.py
├── requirements.txt
└── .env.example
frontend/
└── index.html
tests/
├── test_analyzer.py
└── test_api.py
```

## Execução rápida

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Para testar sem chaves externas, altere `backend/.env`:

```dotenv
DEMO_MODE=true
```

Inicie a aplicação na raiz do projeto:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse:

- Dashboard: http://localhost:8000
- Documentação OpenAPI: http://localhost:8000/docs
- Saúde/configuração: http://localhost:8000/api/health

## Configuração das APIs

### YouTube

1. Crie ou selecione um projeto no [Google Cloud Console](https://console.cloud.google.com/).
2. Ative a **YouTube Data API v3**.
3. Crie uma chave em **APIs e serviços > Credenciais**.
4. Restrinja a chave à YouTube Data API v3 e informe `YOUTUBE_API_KEY` em `backend/.env`.

A pesquisa de vídeos consome cota da API. Ajuste `MAX_VIDEOS` e `MAX_COMMENTS` para controlar volume e custo.

### LLM

Informe `OPENAI_API_KEY` para usar a OpenAI. `OPENAI_MODEL` seleciona o modelo. Um servidor local compatível com a API OpenAI também pode ser usado:

```dotenv
OPENAI_API_KEY=chave-exigida-pelo-provedor
OPENAI_MODEL=seu-modelo
OPENAI_BASE_URL=http://localhost:11434/v1
```

Sem `OPENAI_API_KEY`, o sistema continua funcionando com análise léxica local e detecção de capitais no texto. Sem chave do YouTube, é necessário habilitar `DEMO_MODE=true`.

## API

```http
GET /api/heatmap-data?query=Pablo%20Marçal
```

Resposta:

```json
[
  {
    "lat": -23.5505,
    "lng": -46.6333,
    "intensity": 0.8,
    "sentiment": "positivo",
    "sentiment_score": 0.8,
    "location": "São Paulo, SP",
    "text": "Comentário público..."
  }
]
```

No frontend, **Densidade geral** atribui peso 1 a cada comentário; os modos positivo e negativo usam a intensidade absoluta apenas da classe correspondente.

## Testes

```bash
python -m unittest discover -s tests -v
```

## Limitações e privacidade

- A localização é uma inferência aproximada a partir do texto, nunca GPS. Sem evidência, o ponto padrão é Brasília.
- Comentários podem conter ironia, gírias e ambiguidades; o score não deve ser tratado como fato.
- O MVP processa dados em memória e a cada requisição. Para produção, adicione fila, cache, persistência, autenticação, rate limiting e política de retenção.
- Use apenas conteúdo público e respeite os Termos de Serviço do YouTube, a LGPD e as políticas do provedor de LLM.
