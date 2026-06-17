"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, CatalogItem } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";
import { useAsk } from "@/components/Shell";

export default function CatalogPage() {
  const { data, loading, error } = useFetch(() => api.catalog(), []);
  const [sel, setSel] = useState<string | null>(null);
  const { open } = useAsk();
  const router = useRouter();
  const current = data?.find((c) => c.name === sel) || data?.[0] || null;

  return (
    <>
      <PageHead crumb="Govern / Catalog" title="Data Catalog"
        sub="Metrics, tables, owners, contracts and lineage in one place — the single source for definitions and blast radius." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={5} />}
      {data && current && (
        <div className="grid main-side">
          <Panel title="Metrics & assets" sub="Click to inspect" flush>
            <div className="list">
              {data.map((c) => (
                <div key={c.name} className={`item ${c.status === "attention" ? "medium" : ""}`} onClick={() => setSel(c.name)}>
                  <span className="lead" />
                  <div><div className="t">{c.name}</div><div className="s">{c.kind} · owner {c.owner}{c.domain ? ` · ${c.domain}` : ""}</div></div>
                  <div className="r">{c.investigations ? <Badge t="neu">{c.investigations} inv</Badge> : null}<Badge>{c.status}</Badge></div>
                </div>
              ))}
            </div>
          </Panel>
          <CatalogDrawer c={current} onAsk={() => open(`${current.name} tính từ đâu?`)}
            onView={() => router.push(`/investigations?domain=${current.domain || ""}`)} />
        </div>
      )}
    </>
  );
}

function CatalogDrawer({ c, onAsk, onView }: { c: CatalogItem; onAsk: () => void; onView: () => void }) {
  return (
    <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
      <Panel title={c.name} sub={`${c.kind} · owner ${c.owner}`}
        right={<button className="btn sm" onClick={onAsk}>Ask about this metric</button>}>
        <p style={{ margin: "0 0 12px", lineHeight: 1.55 }}>{c.definition}</p>
        <div className="kv">
          {c.sources.length > 0 && <div><span className="k">Sources</span><span className="v">{c.sources.join(", ")}</span></div>}
          <div><span className="k">Status</span><span className="v"><Badge>{c.status}</Badge></span></div>
          <div><span className="k">Investigations</span><span className="v">{c.investigations ?? 0}</span></div>
        </div>
        {(c.investigations ?? 0) > 0 && <button className="btn sm" style={{ marginTop: 12 }} onClick={onView}>View investigations →</button>}
      </Panel>
      <Panel title="Lineage" sub="blast radius">
        <div className="flow col">
          {c.lineage.map((n, i) => (
            <div key={i}><div className="fnode"><b>{n}</b></div>{i < c.lineage.length - 1 && <div className="farr">↓</div>}</div>
          ))}
        </div>
      </Panel>
      <Panel title="Data contracts" sub="dbt test status">
        <div className="kv">
          {c.contract_tests.map((t, i) => (
            <div key={i}><span className="k">{t.name}</span><span className="v"><Badge>{t.status}</Badge></span></div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
