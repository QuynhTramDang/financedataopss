# Integration qua MCP (M1) — Airflow thật chạy local

MCP THẬT (client–server). Gateway của hệ = **MCP client** (`orchestration/mcp_gateway.py` +
`mcp_transport.py`). Server official chạy **local** → token/data ở lại máy, an toàn cho Finance.
Mặc định (không set env) hệ dùng `FakeTransport` → test/CI không cần Docker/server.

## 1) Chạy Airflow local (Docker)
```bash
docker compose -f docker/airflow/docker-compose.yaml up
# UI/REST: http://localhost:8080  (admin/admin)
```
DAG `revenue_daily` (3 task stg→ods→dtm) sẽ xuất hiện. Để mô phỏng task fail ở ODS:
`Admin → Variables → FAIL_ODS = 1`, rồi trigger DAG.

## 2) Cài SDK + bật MCP
```bash
pip install -r requirements.txt   # gồm `mcp`
# uvx (chạy MCP server): cài `uv` nếu chưa có  — https://docs.astral.sh/uv/
```
Copy `.env.example` → `.env`, bỏ comment khối Airflow MCP:
```
AIRFLOW_MCP_ENABLED=1
AIRFLOW_BASE_URL=http://localhost:8080/api/v1
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_MCP_CMD=uvx
AIRFLOW_MCP_ARGS=mcp-server-apache-airflow
```

## 3) Map tên tool cho khớp server thật
Server cộng đồng có thể đặt tên tool khác (vd `get_dag_runs` thay vì `get_dag_run_status`).
Liệt kê tool server expose:
```bash
python scripts/mcp_list_tools.py airflow
```
Rồi chỉnh `mcp_tool=...` trong `orchestration/registry.py` (tool `airflow_dag_status`) cho khớp.

## 4) Bật trong code
```python
from orchestration.mcp_transport import maybe_enable_real_mcp
maybe_enable_real_mcp()   # có env → thay gateway bằng RealMCPTransport; không → giữ Fake
```
Sau đó executor gọi `airflow_dag_status` sẽ đi qua MCP server thật (audit + allow-list + governance giữ nguyên).

## GitLab MR thật (M2)
Server MCP GitLab tối thiểu tự viết: `scripts/gitlab_mcp_server.py` (không cần npx).
1. Tạo **project test** trên gitlab.com (có nhánh `main`).
2. Tạo **Personal Access Token** scope `api` (Settings → Access Tokens).
3. Trong `.env`:
   ```
   GITLAB_MCP_ENABLED=1
   GITLAB_TOKEN=glpat-...          # CHỈ trong .env, không commit/không dán nơi công khai
   GITLAB_PROJECT_ID=<numeric id>  # Project → Settings → General
   GITLAB_API_URL=https://gitlab.com/api/v4
   GITLAB_MCP_CMD=python
   GITLAB_MCP_ARGS=scripts/gitlab_mcp_server.py
   ```
4. `create_merge_request` sẽ: tạo branch `fix/INV-xxx` off `main` → commit file `proposed/...md` (RCA/patch, KHÔNG đụng code thật) → mở MR. **Chỉ tạo MR (proposal), KHÔNG merge.**

## Inbound trigger (M3) — Airflow fail → tự mở investigation
Entry-point = sự kiện Airflow, không cần người gõ tay. `monitoring.triggers.handle_airflow_failure(dag_id, run_date)`
suy metric từ pipeline_memory (fail-loud nếu DAG lạ), dedup theo (dag_id, run_date).

Webhook (tuỳ chọn): `pip install fastapi uvicorn` → `uvicorn app.webhook:app` (POST `/airflow/failure`).
Trong DAG, thêm `on_failure_callback` POST sự kiện về webhook:
```python
import requests
def _notify(context):
    ti = context["task_instance"]
    requests.post("http://<host>:8000/airflow/failure", json={
        "dag_id": ti.dag_id, "task_id": ti.task_id,
        "logical_date": str(context["logical_date"])[:10]}, timeout=10)
# default_args={"on_failure_callback": _notify}
```

## An toàn (Finance)
- Server chạy **local** (subprocess do client spawn), dùng token của bạn gọi Airflow REST — không ra bên thứ 3.
- Gateway **allow-list default-deny** + **audit log** mọi call; governance (`tool_policy`) quyết tier/approval.
- Read-only trước (M1). Write action (M2: trigger_dag/create_mr) = L2/L3 + **HITL approval** + audit.
- Pin phiên bản server cộng đồng đã verify; không cài server lạ.
