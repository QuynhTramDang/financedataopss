# ─────────────────────────────────────────────────────────────
# Impact-Aware Finance DataOps Twin — image deploy lên GreenNode AgentBase
#
# Kiến trúc trong container:
#   nginx (port 8080, platform route vào đây)
#     ├── GET /health  → proxy /_stcore/health của Streamlit (health thật)
#     └── mọi path khác → proxy (kèm WebSocket) sang Streamlit (port nội bộ 8501)
#   streamlit (127.0.0.1:8501) — UI hiện có ở app/main.py
#
# AgentBase Runtime Contract (HARD): listen 8080 + GET /health → 200. Cả hai đạt qua nginx.
# Platform tự inject GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY/ENDPOINT_URL — KHÔNG set thủ công.
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# nginx cho reverse proxy + curl để debug health
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài Python deps trước (tận dụng layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source agent
COPY . .

# Cấu hình nginx + script khởi động
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
COPY deploy/start.sh /app/deploy/start.sh
RUN chmod +x /app/deploy/start.sh

EXPOSE 8080

CMD ["/app/deploy/start.sh"]
