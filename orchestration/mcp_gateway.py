"""MCP integration boundary — MCP client (qua transport) + allow-list + audit + timeout.

Nguyên tắc (ARCHITECTURE_AGENTIC.md): agent KHÔNG gọi MCP server tùy ý. Chỉ tool đã allow-list
mới được gọi; mọi call được audit; governance (tool_policy) quyết tier/approval ở tầng executor.

M0: transport trừu tượng + FakeTransport (offline/test, không cần server). M1 sẽ cắm
RealMCPTransport (SDK `mcp`) nối tới MCP server official chạy local (Airflow/GitLab) — data/token
ở lại máy, server chỉ là cầu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class MCPToolRef:
    """Một tool MCP đã được duyệt: tên (theo registry) → (server, tool thật trên server)."""
    name: str
    server: str
    tool: str
    write: bool = False


class MCPTransport(Protocol):
    def call(self, server: str, tool: str, args: dict, timeout: float) -> dict: ...


class FakeTransport:
    """Transport offline cho test/CI — trả stub đúng schema, KHÔNG nối server thật."""

    def __init__(self, responses: Optional[dict[str, dict]] = None):
        self._responses = responses or {}

    def call(self, server: str, tool: str, args: dict, timeout: float = 10.0) -> dict:
        if tool in self._responses:
            return dict(self._responses[tool])
        return {"_fake": True, "server": server, "tool": tool, "args": args, "status": "ok"}


class MCPGatewayError(RuntimeError):
    pass


class MCPGateway:
    """Cổng MCP: allow-list + audit + timeout, route qua transport. Default-deny."""

    def __init__(self, allowed: dict[str, MCPToolRef], transport: MCPTransport):
        self._allowed = allowed
        self._transport = transport
        self._audit: list[dict[str, Any]] = []

    def is_allowed(self, name: str) -> bool:
        return name in self._allowed

    def call(self, name: str, args: dict, timeout: float = 10.0) -> dict:
        ref = self._allowed.get(name)
        if ref is None:
            raise PermissionError(f"MCP tool '{name}' không nằm trong allow-list (default-deny).")
        entry: dict[str, Any] = {"tool": name, "server": ref.server, "mcp_tool": ref.tool,
                                 "write": ref.write, "args": args}
        try:
            result = self._transport.call(ref.server, ref.tool, args, timeout)
            entry["status"] = "ok"
            return result
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            raise MCPGatewayError(entry["error"]) from exc
        finally:
            self._audit.append(entry)

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit)


def default_allowlist() -> dict[str, MCPToolRef]:
    """Allow-list công khai (cho RealMCPTransport wiring ở M1)."""
    return _default_allowed()


def _default_allowed() -> dict[str, MCPToolRef]:
    """Allow-list = các tool source='mcp' đã đăng ký trong registry (single source of truth)."""
    from .registry import get_registry

    allowed: dict[str, MCPToolRef] = {}
    for r in get_registry().list(source="mcp"):
        allowed[r.name] = MCPToolRef(
            name=r.name, server=r.mcp_server or "", tool=r.mcp_tool or r.name,
            write=("write" in r.tags),
        )
    return allowed


_gateway: Optional[MCPGateway] = None


def get_gateway() -> MCPGateway:
    """Singleton gateway. Default transport = FakeTransport (offline). M1 set_gateway() với transport thật."""
    global _gateway
    if _gateway is None:
        _gateway = MCPGateway(_default_allowed(), FakeTransport())
    return _gateway


def set_gateway(gateway: MCPGateway) -> None:
    global _gateway
    _gateway = gateway
