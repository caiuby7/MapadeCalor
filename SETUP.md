# Guia de Configuração — APIs Gratuitas

Siga os passos abaixo para ativar **todas** as fontes e análise de sentimento via LLM.

## 1. Arquivo `.env`

```bash
cd backend
cp .env.example .env
```

Edite `backend/.env` com suas chaves.

---

## 2. Groq — Análise de Sentimento (recomendado, gratuito)

1. Acesse [console.groq.com](https://console.groq.com)
2. Crie uma conta (gratuita)
3. Vá em **API Keys** → **Create API Key**
4. Cole no `.env`:

```env
GROQ_API_KEY=gsk_sua_chave_aqui
GROQ_MODEL=llama-3.1-8b-instant
```

Sem esta chave, o sistema usa análise heurística básica (menos precisa).

---

## 3. YouTube Data API v3 (gratuito, cota diária)

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto (ou use existente)
3. Ative **YouTube Data API v3**: [link direto](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
4. Em **Credenciais** → **Criar credenciais** → **Chave de API**
5. Cole no `.env`:

```env
YOUTUBE_API_KEY=AIza...
```

**Sem chave:** o sistema tenta fallback via Invidious (pode falhar em algumas redes).

---

## 4. Reddit API (gratuito)

1. Acesse [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (logado)
2. Clique **create another app...**
3. Tipo: **script**
4. Nome: `MapaDeCalor`, redirect: `http://localhost`
5. Copie **client id** (abaixo do nome) e **secret**
6. Cole no `.env`:

```env
REDDIT_CLIENT_ID=seu_client_id
REDDIT_CLIENT_SECRET=seu_secret
REDDIT_USER_AGENT=MapaDeCalor/1.0 by /u/seu_usuario_reddit
```

**Sem chave:** tenta API JSON pública (limitada).

---

## 5. Bluesky — sem chave

Funciona automaticamente via API pública. Nenhuma configuração necessária.

---

## 6. Notícias RSS — sem chave

Funciona automaticamente (Google News + G1, Folha, UOL, etc.).

---

## 7. Executar

```bash
cd backend
source .venv/bin/activate   # ou: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra **http://localhost:8000**

Verifique status: **http://localhost:8000/api/health**

---

## Resumo rápido

| O que | Precisa de chave? | Link |
|-------|-------------------|------|
| Notícias | Não | — |
| Bluesky | Não | — |
| Sentimento LLM | Sim (Groq) | [console.groq.com](https://console.groq.com) |
| YouTube | Sim | [Google Cloud](https://console.cloud.google.com/apis/library/youtube.googleapis.com) |
| Reddit | Sim | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) |
