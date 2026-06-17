"""M1 — RealMCPTransport wiring (offline bits; không cần `mcp` SDK / Docker)."""

import pytest

from orchestration.mcp_transport import (
    RealMCPTransport,
    build_servers_from_env,
    maybe_enable_real_mcp,
)


def test_no_env_means_no_servers_and_fake_stays(monkeypatch):
    for k in ("AIRFLOW_MCP_ENABLED", "GITLAB_MCP_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    assert build_servers_from_env() == {}
    assert maybe_enable_real_mcp() is False   # không env → giữ FakeTransport (offline)


def test_airflow_env_builds_server_spec(monkeypatch):
    monkeypatch.setenv("AIRFLOW_MCP_ENABLED", "1")
    monkeypatch.setenv("AIRFLOW_BASE_URL", "http://localhost:8080/api/v1")
    servers = build_servers_from_env()
    assert "airflow" in servers
    spec = servers["airflow"]
    assert spec.command  # uvx mặc định
    assert "mcp-server-apache-airflow" in " ".join(spec.args)
    assert spec.env["AIRFLOW_API_URL"] == "http://localhost:8080/api/v1"


def test_real_transport_unknown_server_raises():
    with pytest.raises(RuntimeError):
        # chưa cấu hình server → fail-loud (raise trước khi cần tới mcp SDK)
        RealMCPTransport({}).call("airflow", "get_dag_run_status", {})
