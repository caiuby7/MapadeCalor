#!/usr/bin/env bash
# Configuração rápida do Mapa de Calor
set -e

cd "$(dirname "$0")"
echo "=== Mapa de Calor — Setup ==="

if [ ! -d ".venv" ]; then
  echo "→ Criando ambiente virtual..."
  python3 -m venv .venv
fi

echo "→ Instalando dependências..."
.venv/bin/pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "→ Criando .env a partir do exemplo..."
  cp .env.example .env
  echo ""
  echo "⚠️  Edite backend/.env com suas chaves:"
  echo "   GROQ_API_KEY      → https://console.groq.com (sentimento)"
  echo "   YOUTUBE_API_KEY   → https://console.cloud.google.com (YouTube)"
  echo "   REDDIT_CLIENT_ID  → https://www.reddit.com/prefs/apps"
  echo ""
  echo "   Notícias e Bluesky funcionam SEM chave."
  echo "   Veja SETUP.md para passo a passo completo."
else
  echo "→ .env já existe"
fi

echo ""
echo "→ Verificando chaves configuradas..."
.venv/bin/python3 -c "
from dotenv import load_dotenv
load_dotenv()
from config import get_config_status
cfg = get_config_status()
checks = {
    'GROQ_API_KEY (sentimento)': cfg['groq'],
    'YOUTUBE_API_KEY': cfg['youtube'],
    'REDDIT_CLIENT_ID+SECRET': cfg['reddit'],
}
for name, ok in checks.items():
    print(f'  {\"✓\" if ok else \"✗\"} {name}')
print('  ✓ Notícias RSS (sem chave)')
print('  ✓ Bluesky (sem chave)')
"

echo ""
echo "Para iniciar: source .venv/bin/activate && uvicorn main:app --reload --port 8000"
