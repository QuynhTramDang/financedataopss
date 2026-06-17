"use client";
import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function InvestigationsPage() {
  const [tab, setTab] = useState(0);
  const [q, setQ] = useState("");
  const [source, setSource] = useState("all");
  const [status, setStatus] = useState("all");
  const [domain, setDomain] = useState("all");
  const router = useRouter();
  const { data, loading, error } = useFetch(() => api.investigations(), []);
  const { data: dags } = useFetch(() => api.dags(), []);

  // pick up ?q= / ?domain= from the global search box / projects page
  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    if (sp.get("q")) setQ(sp.get("q") || "");
    if (sp.get("domain")) setDomain(sp.get("domain") || "all");
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    const term = q.trim().toLowerCase();
    return data.filter((i) =>
      (source === "all" || i.source === source) &&
      (status === "all" || i.status === status) &&
      (domain === "all" || i.domain === domain) &&
      (!term || `${i.id} ${i.title} ${i.metric}`.toLowerCase().includes(term)));
  }, [data, q, source, status, domain]);

  const sources = ["all", "alert", "sweep", "dag_fail", "manual"];
  const statuses = ["all", "running", "needs_approval", "escalated", "resolved"];
  const domains = ["all", "revenue", "cash_flow", "spend", "ar"];

  return (
    <>
      <PageHead crumb="Operate / Investigations" title="Investigations"
        sub="Every triggered run and its root-cause analysis in one place. A run is an investigation; DAG and DQ signals that open one live here too." />
      <div className="tabs">
        {["Queue", "DAG monitor", "DQ sweep"].map((t, i) =>
          <button key={t} className={tab === i ? "active" : ""} onClick={() => setTab(i)}>{t}</button>)}
      </div>

      {tab === 0 && (
        <>
          {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
          {loading && <Loading rows={5} />}
          {data && (
            <Panel title="All investigations" sub="Click a row to open the full trace and evidence" flush
              right={
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {q && <Badge t="acc">“{q}”</Badge>}
                  <select className="filter" value={domain} onChange={(e) => setDomain(e.target.value)}>
                    {domains.map((s) => <option key={s} value={s}>{s === "all" ? "All projects" : s}</option>)}
                  </select>
                  <select className="filter" value={source} onChange={(e) => setSource(e.target.value)}>
                    {sources.map((s) => <option key={s} value={s}>{s === "all" ? "All sources" : s}</option>)}
                  </select>
                  <select className="filter" value={status} onChange={(e) => setStatus(e.target.value)}>
                    {statuses.map((s) => <option key={s} value={s}>{s === "all" ? "All status" : s.replace("_", " ")}</option>)}
                  </select>
                </div>
              }>
              {filtered.length === 0 ? <div className="pb"><div className="note acc">No investigations match this filter.</div></div> : (
                <table>
                  <thead><tr><th>ID</th><th>Title</th><th>Project</th><th>Source</th><th>Status</th><th>Severity</th><th>Confidence</th><th>Cost</th></tr></thead>
                  <tbody>
                    {filtered.map((i) => (
                      <tr key={i.id} className="clk" onClick={() => router.push(`/investigations/${i.id}`)}>
                        <td className="mono">{i.id}</td>
                        <td>{i.title}<div className="cellsub">{i.metric} · {i.date} · {i.started_at}</div></td>
                        <td><Badge t="neu">{i.project || i.domain || "—"}</Badge></td>
                        <td><Badge t="neu">{i.source}</Badge></td>
                        <td><Badge>{i.status}</Badge></td>
                        <td><Badge>{i.severity}</Badge></td>
                        <td>{i.confidence_route || "—"}</td>
                        <td className="mono">{i.cost_usd != null ? `$${i.cost_usd}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          )}
        </>
      )}

      {tab === 1 && (
        <Panel title="DAG monitor" sub="Airflow status with owner & SLA — sub-context of investigations" flush>
          {!dags ? <Loading rows={4} /> : (
            <table>
              <thead><tr><th>DAG</th><th>Project</th><th>Status</th><th>SLA</th><th>Owner</th><th>Alert → incident</th></tr></thead>
              <tbody>
                {dags.map((d) => (
                  <tr key={d.id} className={d.investigation_id ? "clk" : ""}
                    onClick={() => d.investigation_id && router.push(`/investigations/${d.investigation_id}`)}>
                    <td><strong>{d.id}</strong><div className="cellsub">{d.last} · {d.success} success</div></td>
                    <td><Badge t="neu">{d.project || "—"}</Badge></td>
                    <td><Badge>{d.status}</Badge></td><td>{d.sla}</td><td>{d.owner}</td>
                    <td>{d.alert ? <span style={{ color: "var(--accent)", fontWeight: 600 }}>{d.alert} →</span> : "—"}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      )}

      {tab === 2 && (
        <Panel title="Proactive DQ sweep" sub="Anomalies caught before Finance reports them">
          <div className="note acc">
            Sweep scans watched metrics across dates and opens an investigation when an anomaly is found.
            The null-spike on stg_payment (2026-06-08) was caught this way → see the escalated investigation in Queue.
          </div>
        </Panel>
      )}
    </>
  );
}
