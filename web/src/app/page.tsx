"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Metric, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function OverviewPage() {
  const { data, loading, error } = useFetch(() => api.overview(), []);

  return (
    <>
      <PageHead crumb="Operate / Overview" title="Overview"
        sub="What needs you first, then how the triggers are running. One control surface — work, then context." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}). Chạy: python -m uvicorn api.server:app --port 8000`} />}
      {loading && <Loading rows={4} />}
      {data && (
        <>
          <div className="grid c4">
            {data.kpis.map((m) => <Metric key={m.k} k={m.k} v={m.v} d={m.d} />)}
          </div>
          <div className="grid main-side" style={{ marginTop: 16 }}>
            <Panel title="Today's attention" sub="Work that needs a human action" flush
              right={<Link className="link" href="/approvals">All approvals →</Link>}>
              <div className="list">
                {data.attention.map((a) => {
                  const href = a.kind === "approval" ? "/approvals" : a.kind === "integration" ? "/integrations" : `/investigations/${a.id}`;
                  return (
                    <Link key={a.id + a.title} href={href} className={`item ${a.severity}`}>
                      <span className="lead" />
                      <div><div className="t">{a.title}</div><div className="s">{a.sub}</div></div>
                      <div className="r"><Badge>{a.status}</Badge></div>
                    </Link>
                  );
                })}
              </div>
            </Panel>
            <Panel title="Trigger health" sub="What can open an investigation" flush>
              <div className="list">
                {data.triggers.map((t) => (
                  <div key={t.name} className="item">
                    <span className="lead" />
                    <div><div className="t">{t.name}</div><div className="s">last fired {t.last}</div></div>
                    <div className="r"><Badge t="neu">{t.kind}</Badge>{t.success !== "—" && <Badge t="ok">{t.success}</Badge>}</div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
