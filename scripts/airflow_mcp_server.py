"""MCP server tối thiểu cho Airflow (SDK `mcp`, stdio) — wrap Airflow REST API.

Đây là MCP server THẬT (nói giao thức MCP), chạy LOCAL, gọi Airflow REST bằng token của bạn.
Dùng khi không có uvx/npx để chạy server cộng đồng. Tool đặt tên KHỚP registry.mcp_tool:
  - get_dag_run_status (read)   ← airflow_dag_status
  - trigger_dag_run    (write)  ← airflow_trigger_dag

Env: AIRFLOW_API_URL (mặc định http://localhost:8080/api/v1), AIRFLOW_USERNAME, AIRFLOW_PASSWORD.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE = os.getenv("AIRFLOW_API_URL", "http://localhost:8080/api/v1")
_AUTH = base64.b64encode(
    f"{os.getenv('AIRFLOW_USERNAME', 'admin')}:{os.getenv('AIRFLOW_PASSWORD', 'admin')}".encode()
).decode()

mcp = FastMCP("airflow")


def _req(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": f"Basic {_AUTH}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


@mcp.tool()
def get_dag_run_status(dag_id: str, run_date: str = "") -> dict:
    """Trạng thái DAG run mới nhất + state các task của một DAG."""
    runs = _req(f"/dags/{dag_id}/dagRuns?order_by=-execution_date&limit=1")
    items = runs.get("dag_runs", [])
    if not items:
        return {"dag_id": dag_id, "state": "no_runs", "tasks": []}
    run = items[0]
    tis = _req(f"/dags/{dag_id}/dagRuns/{run['dag_run_id']}/taskInstances")
    tasks = [{"task_id": t["task_id"], "state": t["state"]} for t in tis.get("task_instances", [])]
    return {"dag_id": dag_id, "run_id": run["dag_run_id"], "state": run["state"], "tasks": tasks}


@mcp.tool()
def trigger_dag_run(dag_id: str, run_date: str = "") -> dict:
    """Trigger một DAG run (backfill). Trả dag_run_id + state."""
    body = {"conf": {"backfill_date": run_date}} if run_date else {}
    run = _req(f"/dags/{dag_id}/dagRuns", method="POST", body=body)
    return {"dag_id": dag_id, "run_id": run.get("dag_run_id"), "state": run.get("state")}


if __name__ == "__main__":
    mcp.run()
