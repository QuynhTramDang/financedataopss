"""RealMCPTransport — MCP client THẬT (SDK `mcp`, stdio) nối tới MCP server official chạy local.

Chỉ kích hoạt khi đã cài `mcp` + khai báo server qua env (build_servers_from_env). Test/CI vẫn dùng
FakeTransport (không import `mcp`, không cần Docker/server). Import `mcp` được làm LAZY trong call.

Mô hình an toàn: server (vd mcp-server-apache-airflow) chạy LOCAL như subprocess do client spawn,
gọi Airflow REST bằng token của bạn — data/token ở lại máy, không ra bên thứ 3.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class MCPServerSpec:
    """Cách spawn một MCP server (stdio): lệnh + args + env."""
    name: str
    command: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)


def _normalize(result: Any) -> dict[str, Any]:
    """Chuẩn hoá kết quả call_tool của MCP về dict (parse JSON text nếu có)."""
    for content in getattr(result, "content", []) or []:
        text = getattr(content, "text", None)
        if text:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return {"text": text}
    return {"raw": str(result)}


class RealMCPTransport:
    """Mỗi call mở 1 stdio session tới server tương ứng, gọi tool, đóng (M1: đơn giản, an toàn)."""

    def __init__(self, servers: dict[str, MCPServerSpec]):
        self._servers = servers

    def call(self, server: str, tool: str, args: dict, timeout: float = 30.0) -> dict:
        spec = self._servers.get(server)
        if spec is None:
            raise RuntimeError(f"Chưa cấu hình MCP server '{server}'.")
        return asyncio.run(self._call_async(spec, tool, args, timeout))

    async def _call_async(self, spec: MCPServerSpec, tool: str, args: dict, timeout: float) -> dict:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=spec.command, args=spec.args, env={**os.environ, **spec.env},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await asyncio.wait_for(session.call_tool(tool, args), timeout)
                return _normalize(result)

    async def list_tools(self, server: str) -> list[str]:
        """Liệt kê tool server expose — để map tên tool (registry mcp_tool) cho khớp server thật."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        spec = self._servers[server]
        params = StdioServerParameters(
            command=spec.command, args=spec.args, env={**os.environ, **spec.env})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]


def build_servers_from_env() -> dict[str, MCPServerSpec]:
    """Đọc cấu hình MCP server từ env (chỉ server được khai báo). {} nếu chưa cấu hình."""
    servers: dict[str, MCPServerSpec] = {}
    if os.getenv("AIRFLOW_MCP_ENABLED") == "1":
        servers["airflow"] = MCPServerSpec(
            name="airflow",
            command=os.getenv("AIRFLOW_MCP_CMD", "uvx"),
            args=os.getenv("AIRFLOW_MCP_ARGS", "mcp-server-apache-airflow").split(),
            env={
                "AIRFLOW_API_URL": os.getenv("AIRFLOW_BASE_URL", ""),
                "AIRFLOW_USERNAME": os.getenv("AIRFLOW_USERNAME", ""),
                "AIRFLOW_PASSWORD": os.getenv("AIRFLOW_PASSWORD", ""),
            },
        )
    if os.getenv("GITLAB_MCP_ENABLED") == "1":
        servers["gitlab"] = MCPServerSpec(
            name="gitlab",
            command=os.getenv("GITLAB_MCP_CMD", "python"),
            args=os.getenv("GITLAB_MCP_ARGS", "scripts/gitlab_mcp_server.py").split(),
            env={
                "GITLAB_TOKEN": os.getenv("GITLAB_TOKEN", ""),
                "GITLAB_PROJECT_ID": os.getenv("GITLAB_PROJECT_ID", ""),
                "GITLAB_API_URL": os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4"),
                # tương thích server cộng đồng (đọc PERSONAL_ACCESS_TOKEN)
                "GITLAB_PERSONAL_ACCESS_TOKEN": os.getenv("GITLAB_TOKEN", ""),
            },
        )
    return servers


def maybe_enable_real_mcp() -> bool:
    """Nếu env có khai báo server → thay gateway bằng RealMCPTransport. Trả True nếu đã bật."""
    from .mcp_gateway import MCPGateway, default_allowlist, set_gateway

    servers = build_servers_from_env()
    if not servers:
        return False
    set_gateway(MCPGateway(default_allowlist(), RealMCPTransport(servers)))
    return True
