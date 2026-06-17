#!/bin/sh
# Khởi động FastAPI (8000) + Next.js (3000) + nginx (8080) trong cùng container.
set -e

# FastAPI backend chạy nền
uvicorn api.server:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

# Next.js production server chạy nền
cd /app/web && node_modules/.bin/next start --hostname 127.0.0.1 --port 3000 &
NEXT_PID=$!
cd /app

# Đợi cả hai sẵn sàng (tối đa 60s)
echo "Waiting for FastAPI and Next.js..."
for i in $(seq 1 30); do
    sleep 2
    FA_OK=0; NX_OK=0
    curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && FA_OK=1 || true
    curl -sf http://127.0.0.1:3000 >/dev/null 2>&1 && NX_OK=1 || true
    if [ "$FA_OK" = "1" ] && [ "$NX_OK" = "1" ]; then
        echo "Both services ready."
        break
    fi
done

# Kéo container xuống nếu một trong hai chết
trap "kill $UVICORN_PID $NEXT_PID 2>/dev/null || true" EXIT

# nginx chạy foreground → giữ container sống
exec nginx -g 'daemon off;'
