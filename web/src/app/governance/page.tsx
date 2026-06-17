"use client";
import { api } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function GovernancePage() {
  const { data, loading, error } = useFetch(() => api.governance(), []);
  return (
    <>
      <PageHead crumb="Govern / Governance" title="Governance"
        sub="What agents may read, draft, retry, notify or block. Every tool call and approval is auditable." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={5} />}
      {data && (
        <div className="grid main-side">
          <div className="grid">
            <Panel title="Permission tiers" sub="Execution policy — L1 / L2 / L3 (from tool_policy)" flush>
              <table>
                <thead><tr><th>Tier</th><th>Default decision</th><th>Examples</th></tr></thead>
                <tbody>
                  {data.tiers.map((t) => (
                    <tr key={t.tier}><td><strong>{t.tier}</strong></td>
                      <td><Badge t={t.decision === "Blocked" ? "bad" : t.decision === "Allowed" ? "ok" : t.decision.includes("Auto") ? "ok" : "warn"}>{t.decision}</Badge></td>
                      <td>{t.examples}</td></tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <Panel title="Live tool checks" sub="governance.tool_policy.check_tool() — real backend" flush>
              <table>
                <thead><tr><th>Tool</th><th>Decision</th><th>Tier</th><th>Approval</th></tr></thead>
                <tbody>
                  {data.tool_checks.map((t) => (
                    <tr key={t.tool}><td className="mono">{t.tool}</td>
                      <td><Badge t={t.decision === "allowed" ? "ok" : "bad"}>{t.decision}</Badge></td>
                      <td>{t.tier || "—"}</td><td>{t.requires_approval ? "required" : "—"}</td></tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </div>
          <Panel title="Audit posture" sub="Current hard controls">
            <div className="kv">
              {data.audit_posture.map((p) => (
                <div key={p.k}><span className="k">{p.k}</span><span className="v">{p.v}</span></div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
