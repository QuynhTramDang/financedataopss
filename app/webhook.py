"""Webhook nhận Airflow on_failure_callback → mở investigation tự động (M3).

Tuỳ chọn (cần FastAPI): pip install fastapi uvicorn — rồi `uvicorn app.webhook:app`.
Core là monitoring.triggers.handle_airflow_failure (test được không cần FastAPI).
"""

from __future__ import annotations

from monitoring.triggers import handle_airflow_failure


def create_app():
    from fastapi import FastAPI, Request

    api = FastAPI(title="Finance DataOps Twin — Airflow webhook")

    @api.post("/airflow/failure")
    async def airflow_failure(req: Request):
        body = await req.json()
        run_date = (body.get("logical_date") or body.get("run_date")
                    or body.get("data_interval_start") or "")
        return handle_airflow_failure(body["dag_id"], str(run_date)[:10], body.get("task_id"))

    return api


try:  # chỉ dựng app khi FastAPI có sẵn; thiếu → app=None (uvicorn sẽ báo cài fastapi)
    app = create_app()
except Exception:  # noqa: BLE001
    app = None
