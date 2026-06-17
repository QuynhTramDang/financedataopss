"""Discovery helper: liệt kê tool mà MCP server thật expose → map cho khớp registry.mcp_tool.

Dùng (sau khi `docker compose up` Airflow + set env trong .env):
    python scripts/mcp_list_tools.py airflow

Tên tool server có thể KHÁC với registry (vd 'trigger_dag_run' vs 'trigger_dag') — chạy script này
rồi chỉnh `mcp_tool` trong orchestration/registry.py cho khớp.
"""

import asyncio
import sys

from orchestration.mcp_transport import RealMCPTransport, build_servers_from_env


def main() -> None:
    server = sys.argv[1] if len(sys.argv) > 1 else "airflow"
    servers = build_servers_from_env()
    if server not in servers:
        print(f"Server '{server}' chưa cấu hình env (xem .env.example). Có: {list(servers)}")
        return
    tools = asyncio.run(RealMCPTransport(servers).list_tools(server))
    print(f"MCP server '{server}' expose {len(tools)} tool:")
    for t in tools:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
