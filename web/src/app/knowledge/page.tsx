"use client";
import { api } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, useFetch } from "@/components/ui";

export default function KnowledgePage() {
  const { data, loading, error } = useFetch(() => api.knowledge(), []);
  return (
    <>
      <PageHead crumb="Learn / Knowledge" title="Knowledge"
        sub="What the system learned from past incidents. Each resolved & approved investigation writes back here, so similar cases retrieve the fix next time." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={4} />}
      {data && (
        <Panel title="Learned incidents" sub="incident_memory — written only after validated + approved" flush>
          <table>
            <thead><tr><th>Incident</th><th>Metric</th><th>Root cause</th><th>Fix</th><th>Prevented by</th></tr></thead>
            <tbody>
              {data.learned.map((i) => (
                <tr key={i.incident_id}>
                  <td className="mono">{i.incident_id}</td>
                  <td><Badge t="neu">{i.metric}</Badge></td>
                  <td>{i.root_cause}</td><td>{i.fix}</td>
                  <td><Badge t="ok">{i.prevented_by}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  );
}
