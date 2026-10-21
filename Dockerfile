# RenalSight as one service: FastAPI (API under /api) + the built React website.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/web/package*.json ./
RUN npm ci
COPY frontend/web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend backend
COPY ml ml
COPY data/processed data/processed
COPY deploy deploy
COPY --from=web /web/dist frontend/web/dist
ENV FRONTEND_DIST=/app/frontend/web/dist WHATSAPP_ENABLED=0 SCHEDULER_ENABLED=true
EXPOSE 8000
CMD ["bash", "deploy/start.sh"]
