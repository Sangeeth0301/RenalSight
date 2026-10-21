#!/usr/bin/env bash
# Runs once when the Codespace is created: installs everything the app needs.
set -e
cd "$(dirname "$0")/.."
python -m pip install --upgrade pip
pip install -r backend/requirements.txt -r mcp_server/requirements.txt
(cd frontend/web && npm ci)
if [ ! -f backend/.env ]; then
  printf 'SECRET_KEY=%s\nLLM_CHAIN=groq,gemini,openai,xai,ollama,rules\nOLLAMA_ENABLED=false\nBUDDY_MESSAGES_PER_MINUTE=30\n' "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" > backend/.env
  echo "Created backend/.env. AI keys: add GROQ_API_KEY / GEMINI_API_KEY as Codespaces secrets (or in this file). The app works without them."
fi
