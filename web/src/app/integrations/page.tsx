"use client";
import { api } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function IntegrationsPage() {
  const { data, loading, error } = useFetch(() => api.integrations(), []);
  const { data: health } = useFetch(() => api.mcpHealth(), []);
  return (
    <>
      <PageHead crumb="Govern / Integrations" title="Integrations"
        sub="MCP-backed systems and connector health. Tools exposed to agents stay allow-listed and governed by the same tiers." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={5} />}

      {health && (
        <Panel title="Live MCP connection" sub={health.mcp_live ? "RealMCPTransport active — agent calls hit your real systems" : "FakeTransport (offline) — set *_MCP_ENABLED in .env to go live"} flush>
          <table>
            <thead><tr><th>MCP server</th><th>Enabled</th><th>Connection</th><th>Tools (live)</th><th>Detail</th></tr></thead>
            <tbody>
              {health.servers.map((s) => (
                <tr key={s.name}>
                  <td><strong>{s.name}</strong></td>
                  <td><Badge t={s.enabled ? "ok" : "neu"}>{s.enabled ? "on" : "off"}</Badge></td>
                  <td><Badge t={s.connected ? "ok" : s.enabled ? "bad" : "neu"}>{s.connected ? "connected" : s.enabled ? "error" : "—"}</Badge></td>
                  <td className="mono">{(s.tools || []).join(", ") || "—"}</td>
                  <td className="cellsub">{s.detail || (s.connected ? "live" : "")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {data && (
        <div className="grid" style={{ marginTop: 16 }}>
          <Panel title="Connector health" sub="MCP servers & external systems" flush>
            <table>
              <thead><tr><th>Connector</th><th>Type</th><th>Status</th><th>Auth</th><th>Scopes</th><th>Calls</th><th>Error rate</th></tr></thead>
              <tbody>
                {data.map((i) => (
                  <tr key={i.name}>
                    <td><strong>{i.name}</strong>{i.note && <div className="cellsub" style={{ color: "var(--bad)" }}>{i.note}</div>}</td>
                    <td><Badge t="neu">{i.type}</Badge></td><td><Badge>{i.status}</Badge></td>
                    <td>{i.auth}</td><td>{i.scopes}</td><td>{i.calls}</td><td>{i.error_rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
          <Panel title="MCP boundary" sub="Agents never call MCP servers directly">
            <div className="flow">
              {[["Planner", "requests capability"], ["Tool registry", "maps canonical tool"], ["Policy gate", "checks tier + approval"], ["MCP gateway", "allow-listed tool only"], ["External", "Airflow · GitLab · Teams"]]
                .map(([t, s], i, arr) => (
                  <div key={t} style={{ display: "contents" }}>
                    <div className="fnode"><b>{t}</b><span>{s}</span></div>
                    {i < arr.length - 1 && <div className="farr">→</div>}
                  </div>
                ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
