# ─────────────────────────────────────────────────────────────
# Impact-Aware Finance DataOps Twin — image deploy lên GreenNode AgentBase
#
# Kiến trúc trong container:
#   nginx (port 8080, platform route vào đây)
#     ├── GET /health  → FastAPI /health (port 8000)
#     ├── /api/        → FastAPI uvicorn (port 8000)
#     └── /            → Next.js production server (port 3000)
#   uvicorn api.server:app (127.0.0.1:8000) — control-plane API
#   next start (127.0.0.1:3000) — Next.js UI
#
# AgentBase Runtime Contract (HARD): listen 8080 + GET /health → 200.
# Platform tự inject GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY/ENDPOINT_URL.
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Cài Node.js 20 LTS + nginx + curl
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg nginx \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Next.js build ──
# Copy package files trước để tận dụng layer cache
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci --prefer-offline

# Copy toàn bộ web source rồi build
COPY web/ ./web/
# NEXT_PUBLIC_API_BASE="" → browser gọi /api/... (relative) → nginx proxy sang FastAPI
RUN cd web && NEXT_PUBLIC_API_BASE="" npm run build

# ── Python source ──
COPY . .

# ── nginx + start script ──
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
COPY deploy/start.sh /app/deploy/start.sh
RUN chmod +x /app/deploy/start.sh

EXPOSE 8080

CMD ["/app/deploy/start.sh"]
