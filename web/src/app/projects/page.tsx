"use client";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function ProjectsPage() {
  const router = useRouter();
  const { data, loading, error } = useFetch(() => api.projects(), []);

  return (
    <>
      <PageHead crumb="Operate / Projects" title="Projects"
        sub="Each finance domain is a project backed by its own warehouse tables, metric contract and reconciliation baseline — all running on real seeded data." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={4} />}
      {data && (
        <div className="grid c2">
          {data.map((p) => (
            <div key={p.key} className="panel" style={{ cursor: "pointer" }}
              onClick={() => router.push(`/projects/${p.key}`)}>
              <div className="ph">
                <div><h3>{p.label}</h3><div className="sub">owner {p.owner} · metric <span className="mono">{p.metric}</span></div></div>
                {p.needs_approval > 0 ? <Badge t="warn">{p.needs_approval} need approval</Badge> : <Badge t="ok">healthy</Badge>}
              </div>
              <div className="pb">
                <div className="grid c3">
                  <Stat k="Investigations" v={p.investigations} />
                  <Stat k="Open" v={p.open} />
                  <Stat k="Need approval" v={p.needs_approval} />
                </div>
                <div className="note acc" style={{ marginTop: 12 }}>
                  Open this project → its metrics, definitions, lineage and live investigations.
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Stat({ k, v }: { k: string; v: number }) {
  return <div><div style={{ fontSize: 24, fontWeight: 750, letterSpacing: "-.02em" }}>{v}</div>
    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 3 }}>{k}</div></div>;
}
