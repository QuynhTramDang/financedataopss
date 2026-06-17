"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { api, Approval } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, Icon, ICONS, useFetch } from "@/components/ui";

export default function ApprovalsPage() {
  const { data, loading, error, reload } = useFetch(() => api.approvals(), []);
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("sel");
    if (s) setSel(s);
  }, []);

  const current = data?.find((a) => a.id === sel) || data?.[0] || null;

  async function decide(decision: string) {
    if (!current) return;
    setBusy(true);
    try { await api.decide(current.id, decision); reload(); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHead crumb="Decide / Approvals" title="Approvals"
        sub="A focused inbox for gated actions. Review evidence, diff, impact and rollback before any side effect — then watch the action loop close." />
      {error && <Empty icon="⚠" text={`API không kết nối được (${error}).`} />}
      {loading && <Loading rows={4} />}
      {data && (
        <div className="grid main-side">
          <Panel title="Pending inbox" sub="Actions blocked by governance" flush>
            <div className="list">
              {data.map((a) => (
                <div key={a.id} className={`item ${a.id === current?.id ? "high" : "medium"}`} onClick={() => setSel(a.id)}>
                  <span className="lead" />
                  <div><div className="t">{a.title}</div>
                    <div className="s">incident: <b>{a.investigation_title || a.investigation_id}</b>{a.domain ? ` · ${a.domain}` : ""}</div></div>
                  <div className="r"><Badge t="acc">{a.risk}</Badge><Badge>{a.status}</Badge></div>
                </div>
              ))}
            </div>
          </Panel>
          {current && <ApprovalDrawer a={current} busy={busy} onDecide={decide} onGoApproval={(id) => setSel(id)} />}
        </div>
      )}
    </>
  );
}

function ApprovalDrawer({ a, busy, onDecide, onGoApproval }: { a: Approval; busy: boolean; onDecide: (d: string) => void; onGoApproval: (id: string) => void }) {
  const decided = a.status !== "pending";
  return (
    <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
      <Panel title={a.title} sub={`${a.id} · ${a.automation}`} right={<Badge t="acc">{a.risk}</Badge>}>
        <div className="note acc" style={{ marginBottom: 12 }}><Icon d={ICONS.investigations} />
          <div>Linked incident: <b>{a.investigation_title || a.investigation_id}</b> · <Link href={`/investigations/${a.investigation_id}`} style={{ color: "var(--accent)", fontWeight: 600 }}>View incident →</Link></div></div>
        <div className="note warn"><Icon d={ICONS.warn} /><div><b>Why this is gated</b><br />{a.why}</div></div>
        <div className="kv" style={{ marginTop: 14 }}>
          <div><span className="k">Impact</span><span className="v">{a.impact}</span></div>
          <div><span className="k">Rollback</span><span className="v" style={{ maxWidth: "62%" }}>{a.rollback}</span></div>
        </div>
        <div className="note acc" style={{ marginTop: 12 }}><Icon d={ICONS.check} /><div><b>Validation</b><br />{a.validation}</div></div>
        {!decided ? (
          <div style={{ display: "flex", gap: 8, marginTop: 18 }}>
            <button className="btn ok" disabled={busy} onClick={() => onDecide("approved")}>Approve action</button>
            <button className="btn bad" disabled={busy} onClick={() => onDecide("rejected")}>Reject</button>
            <button className="btn" disabled={busy} onClick={() => onDecide("needs_revision")}>Request changes</button>
          </div>
        ) : <div style={{ marginTop: 16 }}><Badge>{a.status}</Badge></div>}
        {a.mr_merged && a.rerun_approval_id && (
          <div className="note ok" style={{ marginTop: 14 }}><Icon d={ICONS.check} />
            <div><b>MR merged on GitLab ✓</b> — recompute the metric on the fix.
              <div><button className="btn primary sm" style={{ marginTop: 8 }} onClick={() => onGoApproval(a.rerun_approval_id!)}>Approve DAG re-run →</button></div></div></div>
        )}
      </Panel>

      {a.action_result && (
        <Panel title="Action result" sub={a.action_result.mode === "stage1_mr_created"
          ? "create MR (live) → merge on GitLab → approve DAG re-run below"
          : "trigger Airflow → re-validate → notify → memory write-back"}>
          {a.action_result.steps.length === 0
            ? <div className="note bad">No side effects — {a.status}. Memory not written.</div>
            : (
              <div className="trace">
                {a.action_result.steps.map((s, i) => {
                  const tn = s.status === "pending" ? "warn" : s.status === "error" ? "bad" : "ok";
                  return (
                    <div key={i} className={`tstage ${tn}`}>
                      <div className="tstage-h">
                        <div className="tnode">{s.tier}</div>
                        <div><div className="nm">{s.name} <Badge t={tn}>{s.status}</Badge></div>
                          <div className="ds">{s.detail}{" "}
                            {s.link?.startsWith("approval:") && <button className="btn sm" style={{ marginTop: 6 }} onClick={() => onGoApproval(s.link!.split(":")[1])}>Go to re-run approval →</button>}
                            {s.link === "dag" && <Link href={`/investigations/${a.investigation_id}`} style={{ color: "var(--accent)", fontWeight: 600 }}>View Airflow run / DAG →</Link>}
                            {s.link?.startsWith("http") && <a href={s.link} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontWeight: 600 }}>Open MR on GitLab ↗</a>}
                          </div></div>
                        <span />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          <div style={{ marginTop: 12, fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>Audit trail</div>
          <div className="kv" style={{ marginTop: 6 }}>
            {a.action_result.audit.map((x, i) => <div key={i}><span className="k mono" style={{ textAlign: "left" }}>{x}</span></div>)}
          </div>
        </Panel>
      )}
    </div>
  );
}
