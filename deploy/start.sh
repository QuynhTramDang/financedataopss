#!/bin/sh
# Khởi động Streamlit (nội bộ 8501) rồi nginx (public 8080) trong cùng container.
# Nếu một trong hai chết, container thoát để AgentBase đánh dấu unhealthy và restart.
set -e

# Streamlit chạy nền, chỉ bind localhost (chỉ nginx mới được truy cập trực tiếp).
streamlit run app/main.py \
    --server.port=8501 \
    --server.address=127.0.0.1 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    &
STREAMLIT_PID=$!

# Nếu Streamlit thoát thì kéo cả container xuống (tránh nginx báo healthy giả).
trap "kill $STREAMLIT_PID 2>/dev/null || true" EXIT

# nginx chạy foreground → giữ container sống.
exec nginx -g 'daemon off;'
