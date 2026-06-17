"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, CatalogItem, Project } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";
import { useAsk } from "@/components/Shell";

const LABEL: Record<string, string> = {
  revenue: "Revenue", cash_flow: "Cash Flow", spend: "Cost / Spend", ar: "AR / Collections",
};

export default function ProjectDetail() {
  const { key } = useParams<{ key: string }>();
  const router = useRouter();
  const { open } = useAsk();
  const { data: projects } = useFetch<Project[]>(() => api.projects(), []);
  const { data: catalog, loading, error } = useFetch<CatalogItem[]>(() => api.catalog(), []);
  const [sel, setSel] = useState<string | null>(null);

  const project = projects?.find((p) => p.key === key);
  const metrics = (catalog || []).filter((c) => c.domain === key);
  const current = metrics.find((m) => m.name === sel) || metrics[0] || null;

  return (
    <>
      <PageHead crumb={`Operate / Projects / ${LABEL[key] || key}`} title={LABEL[key] || key}
        sub={project ? `Owner ${project.owner} · primary metric ${project.metric} · ${project.investigations} investigations` : "Project definition — metrics, lineage, contracts."}
        actions={<button className="btn primary" onClick={() => router.push(`/investigations?domain=${key}`)}>View investigations →</button>} />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={5} />}
      {catalog && metrics.length === 0 && <Empty text="No metrics defined for this project yet." />}
      {current && (
        <div className="grid main-side">
          <Panel title="Metrics" sub={`${metrics.length} defined in this project`} flush>
            <div className="list">
              {metrics.map((m) => (
                <div key={m.name} className={`item ${m.status === "attention" ? "medium" : ""}`} onClick={() => setSel(m.name)}>
                  <span className="lead" />
                  <div><div className="t">{m.name}</div><div className="s">{m.kind} · {m.definition.slice(0, 70)}</div></div>
                  <div className="r">{m.investigations ? <Badge t="neu">{m.investigations} inv</Badge> : null}<Badge>{m.status}</Badge></div>
                </div>
              ))}
            </div>
          </Panel>

          <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
            <Panel title={current.name} sub={`${current.kind} · owner ${current.owner}`}
              right={<button className="btn sm" onClick={() => open(`${current.name} tính từ đâu?`)}>Ask</button>}>
              <p style={{ margin: "0 0 12px", lineHeight: 1.55 }}>{current.definition}</p>
              <div className="kv">
                <div><span className="k">Sources</span><span className="v">{current.sources.join(", ")}</span></div>
                <div><span className="k">Investigations</span><span className="v">{current.investigations ?? 0}</span></div>
                <div><span className="k">Status</span><span className="v"><Badge>{current.status}</Badge></span></div>
              </div>
              {(current.investigations ?? 0) > 0 && (
                <button className="btn sm" style={{ marginTop: 12 }} onClick={() => router.push(`/investigations?domain=${key}`)}>
                  View investigations →
                </button>
              )}
            </Panel>
            <Panel title="Lineage" sub="source → pipeline → report (blast radius)">
              <div className="flow col">
                {current.lineage.filter(Boolean).map((n, i) => (
                  <div key={i}><div className="fnode"><b>{n}</b></div>{i < current.lineage.filter(Boolean).length - 1 && <div className="farr">↓</div>}</div>
                ))}
              </div>
            </Panel>
            <Panel title="Data contracts" sub="dbt test status">
              <div className="kv">
                {current.contract_tests.map((t, i) => (
                  <div key={i}><span className="k">{t.name}</span><span className="v"><Badge>{t.status}</Badge></span></div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
