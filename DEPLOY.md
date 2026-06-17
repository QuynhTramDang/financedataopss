# Deploy lên GreenNode AgentBase (Claw-a-thon)

Hướng dẫn deploy agent **Impact-Aware Finance DataOps Twin** lên AgentBase Runtime.

## Đã chuẩn bị sẵn trong repo

| File | Vai trò |
|------|---------|
| `Dockerfile` | Build image: Streamlit (8501 nội bộ) + nginx (8080 public) |
| `deploy/nginx.conf` | Reverse proxy: `GET /health` → health Streamlit; còn lại → UI (kèm WebSocket) |
| `deploy/start.sh` | Khởi động Streamlit rồi nginx trong cùng container |
| `.dockerignore` | Loại `.env`, `.greennode.json`, venv, skill… khỏi image |
| `.env.example` | Mẫu config; có sẵn block `MAAS_*` cho model GreenNode |

**Runtime Contract đã đạt:** container listen `8080`, có `GET /health` → 200.
**Auto-inject:** AgentBase tự bơm `GREENNODE_CLIENT_ID/SECRET/AGENT_IDENTITY/ENDPOINT_URL` — KHÔNG set thủ công trong `.env`.

## Trước khi deploy — còn phải làm

1. **Đổi LLM sang MaaS.** Trên AgentBase không có Claude. Trong `model_router/models.yaml`,
   trỏ `provider:` của các route sang `maas` (xem ghi chú cuối file đó), rồi điền
   `MAAS_BASE_URL` / `MAAS_API_KEY` / `MAAS_MODEL` trong `.env`.
2. **Build xong workflow LangGraph** (hiện mới Step 0 scaffold) để agent chạy có ý nghĩa.
3. **Docker Desktop đang chạy** (bộ skill cần để build & push).
4. **IAM credential**: `GREENNODE_CLIENT_ID` / `GREENNODE_CLIENT_SECRET` (env hoặc `.greennode.json`)
   — lấy từ portal/email BTC.

## Test image tại local (tùy chọn, nên làm trước khi deploy)

```powershell
docker build -t financedataops:test .
docker run --rm -p 8080:8080 --env-file .env financedataops:test
# Mở http://localhost:8080  (UI)
# Health: curl http://localhost:8080/health   → 200
```

## Deploy bằng bộ skill AgentBase

Bộ skill nằm ngang hàng tại `..\greennode-agentbase-skills`. Trong Claude Code, prompt:

> "Dùng skill agentbase-deploy để deploy agent trong folder này lên AgentBase"

Skill sẽ hỏi lần lượt: registry (chọn **AgentBase CR** — khuyến nghị), env file (`.env`),
runtime name, flavor, network mode (**PUBLIC**) → tự `docker build` + push + tạo runtime →
chờ `ACTIVE` → trả endpoint public. Mỗi bước skill dừng chờ bạn xác nhận (`yes`/`ok`).

Sau khi ACTIVE: copy endpoint, test `<endpoint>/health` = 200, rồi push source lên GitHub để submit.
