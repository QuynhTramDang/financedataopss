"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, rawLogUrl, Investigation, LogsResponse, RunCheck, CheckStep } from "@/lib/api";
import { Badge, Panel, PageHead, Loading, Empty, Icon, ICONS, useFetch, tone } from "@/components/ui";
import { useAsk } from "@/components/Shell";

export default function InvestigationDetail() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState(0);
  const [agentBusy, setAgentBusy] = useState(false);
  const { open } = useAsk();
  const { data, loading, error, reload } = useFetch<Investigation>(() => api.investigation(id), [id]);

  async function runAgent() {
    setAgentBusy(true);
    try { await api.runAgent(id); reload(); setTab(0); } finally { setAgentBusy(false); }
  }

  if (error) return <Empty icon="⚠" text={`Không tải được investigation (${error}).`} />;
  if (loading || !data) return <><PageHead crumb="Operate / Investigations" title="Investigation"
    sub="Agent đang phân tích trên warehouse…" /><Loading rows={6} /></>;

  const inv = data;
  const tabs = ["Trace", "Logs", "Evidence & Claims", "Root cause & Patch", "Trust matrix"];
  const awaitingRerun = inv.status === "awaiting_rerun";
  const fixable = inv.status === "needs_approval" || awaitingRerun;
  const reviewId = awaitingRerun ? inv.rerun_approval_id : inv.approval_id;

  return (
    <>
      <PageHead crumb={`Operate / Investigations / ${inv.id}`} title={inv.title}
        sub={`${inv.trigger} · ${inv.metric || ""} · ${inv.date || ""}`}
        actions={<>
          <button className="btn" onClick={() => open(`Vì sao ${inv.metric} ${inv.date} bất thường?`)}>Ask about this metric</button>
          {fixable && reviewId
            ? <Link className="btn primary" href={`/approvals?sel=${reviewId}`}>{awaitingRerun ? "Approve DAG re-run →" : "Review & approve fix →"}</Link>
            : <button className="btn" disabled={agentBusy} onClick={runAgent}>{agentBusy ? "Agent running…" : "Re-run agent"}</button>}
        </>} />

      <div className={`note ${fixable ? "warn" : inv.confidence_route === "escalate" ? "bad" : "ok"}`} style={{ marginBottom: 16 }}>
        <Icon d={fixable ? ICONS.warn : ICONS.check} />
        <div>{awaitingRerun
          ? <><b>Fix merged.</b> The metric must be recomputed on the patched logic. <b>Next action:</b> approve the Airflow DAG re-run in Approvals.</>
          : inv.status === "needs_approval"
            ? <><b>Agent analyzed this on your warehouse</b> and found a safe, validated fix — reconciliation goes to 0% after the patch. <b>Next action:</b> review & approve it in Approvals.</>
            : inv.confidence_route === "escalate"
              ? <><b>Agent analyzed this on your warehouse</b> → no safe code patch (data-quality issue). <b>Next action:</b> escalate to the data owner; don't recompute on bad data.</>
              : <>Agent analysis complete — real LangGraph trace, every number from SQL.</>}</div>
      </div>

      <div className="grid main-side">
        <div>
          <div className="tabs">
            {tabs.map((t, i) => <button key={t} className={tab === i ? "active" : ""} onClick={() => setTab(i)}>{t}</button>)}
          </div>

          {tab === 0 && <TraceView inv={inv} />}
          {tab === 1 && <LogsView id={inv.id} />}
          {tab === 2 && <EvidenceClaims inv={inv} />}
          {tab === 3 && <RootCausePatch inv={inv} />}
          {tab === 4 && <TrustMatrix inv={inv} />}
        </div>

        <SidePanel inv={inv} />
      </div>
    </>
  );
}

function TraceView({ inv }: { inv: Investigation }) {
  return (
    <Panel title="Execution trace" sub="Planner → Tool Executor → Verifier → Decision · governed, 0 raw rows to LLM" flush>
      <div className="pb">
        <div className="trace">
          {inv.trace.map((s, i) => (
            <div key={i} className={`tstage ${s.status}`}>
              <div className="tstage-h">
                <div className="tnode">{s.stage}</div>
                <div><div className="nm">{s.name}</div><div className="ds">{s.detail}</div></div>
                <span className="mono">{s.duration}</span>
              </div>
              {s.calls.length > 0 && (
                <div className="tsub">
                  {s.calls.map((c, j) => (
                    <div key={j} className="tcall">
                      <div>
                        <div className="nm"><Badge t={c.status === "ok" ? "ok" : "warn"}>{c.tier}</Badge>{c.name}</div>
                        <div className="meta">{c.detail}</div>
                      </div>
                      <span className="mono">{c.duration}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        {inv.confidence_route === "escalate" && (
          <div className="note warn" style={{ marginTop: 14 }}>
            <Icon d={ICONS.warn} /><div>Confidence gate routed to <b>escalate</b> — no safe deterministic patch. Handed to a human owner instead of guessing.</div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function EvidenceClaims({ inv }: { inv: Investigation }) {
  return (
    <div className="grid">
      <Panel title="Claim verification" sub="LLM-extracted claims checked by the deterministic rule engine" flush>
        {inv.claims.length === 0 ? <div className="pb"><div className="note acc">No claims yet — investigation still gathering evidence.</div></div> : (
          <table>
            <thead><tr><th>Claim</th><th>Evidence</th><th>Rule</th><th>Status</th></tr></thead>
            <tbody>
              {inv.claims.map((c, i) => (
                <tr key={i}><td>{c.claim}</td><td><Badge t="neu">{c.evidence}</Badge></td>
                  <td className="mono">{c.rule}</td><td><Badge>{c.status}</Badge></td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Evidence" sub="Raw signals collected by governed read-only tools">
        <div className="evi">
          {inv.evidence.map((e, i) => (
            <div key={i} className="evcard"><div className="ty">{e.type}</div><div className="bd">{e.body}</div></div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function LogsView({ id }: { id: string }) {
  const { data, loading, error } = useFetch<LogsResponse>(() => api.logs(id), [id]);
  if (error) return <Empty icon="⚠" text={`Không tải được log (${error}).`} />;
  if (loading || !data) return <Loading rows={5} />;
  if (!data.job) return <Empty text={data.note || "No job log attached."} />;
  const t = data.triage;
  return (
    <div className="grid">
      {t && (
        <Panel title="Failure triage" sub="agents.incident_agent — classified from the real log, then routed by policy"
          right={<Badge t={t.requires_approval ? "warn" : "ok"}>{t.tier}</Badge>}>
          <div className="kv">
            <div><span className="k">Failure type</span><span className="v">{t.failure_type} <span className="cellsub">({Math.round((t.confidence || 0) * 100)}% conf)</span></span></div>
            <div><span className="k">Decided action</span><span className="v">{t.action}{t.auto_action_taken ? " (auto)" : t.requires_approval ? " · approval required" : ""}</span></div>
          </div>
          <div style={{ marginTop: 10, fontSize: 12, fontWeight: 700, color: "var(--muted)" }}>Audit</div>
          <div className="kv" style={{ marginTop: 4 }}>
            {t.audit.map((a, i) => <div key={i}><span className="k mono" style={{ textAlign: "left" }}>{a}</span></div>)}
          </div>
        </Panel>
      )}
      <Panel title="Airflow task log" sub="real task log from the failed DAG run (tools.log_search · MCP boundary)" flush>
        <div className="pb">
          <div className="logview">
            <div className="lh">
              <span className="jb">airflow · {data.job} · task log</span>
              {data.raw_url && <a href={rawLogUrl(data.raw_url)} target="_blank" rel="noreferrer">Open full log ↗</a>}
            </div>
            <div className="logbody">
              {data.lines.map((l) => (
                <div key={l.n} className={`lr ${l.level}`}><span className="ln">{l.n}</span><span className="lt">{l.text}</span></div>
              ))}
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function StepArtifactView({ a }: { a: NonNullable<CheckStep["artifact"]> }) {
  if (a.kind === "diff" && a.diff) return (
    <div className="diff sart">{a.diff.map((d, i) => <div key={i} className={`ln ${d[0]}`}>{d[0] === "add" ? "+ " : d[0] === "del" ? "- " : "  "}{d[1]}</div>)}</div>
  );
  if (a.kind === "tests" && a.tests) return (
    <div className="sart" style={{ display: "grid", gap: 5 }}>
      {a.tests.map((t, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
          <Badge t={t.status === "PASS" ? "ok" : "bad"}>{t.status}</Badge>
          <span className="mono">{t.name}</span>{t.note && <span className="cellsub">{t.note}</span>}
        </div>
      ))}
    </div>
  );
  if (a.kind === "compare") return (
    <div className="checkgrid sart">
      <div className="evcard"><div className="ty">before</div><div className="bd"><Badge t="bad">{a.before_pct}%</Badge> mismatch</div></div>
      <div className="evcard"><div className="ty">after</div><div className="bd"><Badge t="ok">{a.after_pct}%</Badge> mismatch</div></div>
    </div>
  );
  if (a.kind === "yaml" && a.yaml) return <div className="diff sart"><div className="ln ctx" style={{ whiteSpace: "pre-wrap" }}>{a.yaml}</div></div>;
  if (a.kind === "audit" && a.audit) return (
    <div className="sart kv">{a.audit.map((x, i) => <div key={i}><span className="k mono" style={{ textAlign: "left" }}>{x}</span></div>)}</div>
  );
  return null;
}

function RunCheckPanel({ id }: { id: string }) {
  const [res, setRes] = useState<RunCheck | null>(null);
  const [running, setRunning] = useState(false);
  const [revealed, setRevealed] = useState(0);
  async function run() {
    setRunning(true); setRes(null); setRevealed(0);
    try {
      const r = await api.runCheck(id);
      setRes(r);
      const total = r.steps?.length ?? 0;
      for (let i = 1; i <= total; i++) { await new Promise((rs) => setTimeout(rs, 480)); setRevealed(i); }
    } finally { setRunning(false); }
  }
  const steps = res?.steps ?? [];
  return (
    <Panel title="Run the fix & test" sub="Agent proposes a fix, applies it to a sandbox, re-queries the warehouse, then proves it — each step real."
      right={<button className="btn primary sm" disabled={running} onClick={run}>{running ? "Running…" : res ? "Re-run" : "Run fix & test"}</button>}>
      {!res && !running && <div className="note acc"><Icon d={ICONS.check} /><div>Runs the patch against the seeded warehouse step by step: propose → sandbox → re-query → reconcile → regression test. Nothing is deployed.</div></div>}

      {res && res.message && <div className="note warn" style={{ marginBottom: 12 }}><Icon d={ICONS.warn} /><div>{res.message}</div></div>}

      {steps.length > 0 && (
        <div className="steps">
          {steps.map((s, i) => {
            const shown = i < revealed;
            const active = i === revealed && running;
            const cls = active ? "running" : shown ? s.status : "idle";
            return (
              <div key={s.key} className={`step ${cls}`}>
                <div className="sdot">{active ? <span className="spin" /> : shown ? (s.status === "pass" ? "✓" : "✗") : i + 1}</div>
                <div>
                  <div className="stitle">{s.title}</div>
                  {(shown || active) && <div className="sdetail">{active ? "running…" : s.detail}</div>}
                  {shown && s.artifact && <StepArtifactView a={s.artifact} />}
                </div>
                <div>{shown && <Badge t={s.status === "pass" ? "ok" : "bad"}>{s.status}</Badge>}</div>
              </div>
            );
          })}
        </div>
      )}

      {res && !running && res.overall && revealed >= steps.length && steps.length > 0 && (
        <div className={`note ${res.overall === "pass" ? "ok" : "bad"}`} style={{ marginTop: 12 }}>
          <Icon d={res.overall === "pass" ? ICONS.check : ICONS.warn} />
          <div>{res.overall === "pass"
            ? <>Fix proven: reconciliation {res.reconciliation?.before_pct}% → {res.reconciliation?.after_pct}%, and the regression test catches the bug. Ready for approval.</>
            : <>Workflow flagged a blocker — see the failed step above.</>}</div>
        </div>
      )}
    </Panel>
  );
}

function RootCausePatch({ inv }: { inv: Investigation }) {
  const v = inv.validation;
  return (
    <div className="grid">
      <Panel title="Root cause">
        <p style={{ margin: 0, lineHeight: 1.6 }}>{inv.root_cause || "Not concluded — escalated."}</p>
      </Panel>

      <RunCheckPanel id={inv.id} />

      {inv.patch ? (
        <Panel title="Proposed patch" sub={inv.patch.file}
          right={<Badge>{inv.patch.approval_required ? "approval required" : "auto"}</Badge>}>
          <div className="diff">
            {inv.patch.diff.map((d, i) => (
              <div key={i} className={`ln ${d[0]}`}>{d[0] === "add" ? "+ " : d[0] === "del" ? "- " : "  "}{d[1]}</div>
            ))}
          </div>
          <div className="note warn" style={{ marginTop: 12 }}><Icon d={ICONS.warn} /><div>{inv.patch.review}</div></div>
        </Panel>
      ) : (
        <Panel title="Patch"><div className="note acc">No code patch — this anomaly is handled by escalation / operational remediation, not a SQL change.</div></Panel>
      )}

      {v && v.before_pct != null && (
        <Panel title="Validation" sub={`reconciliation · attempt ${v.attempts}/2`}>
          <div className="kv">
            <div><span className="k">Before fix</span><span className="v">{v.before_pct}%</span></div>
            <div><span className="k">After fix</span><span className="v">{v.after_pct}%</span></div>
            <div><span className="k">Result</span><span className="v"><Badge>{v.status}</Badge></span></div>
          </div>
        </Panel>
      )}

      {inv.dbt_test && (
        <Panel title="Regression test (prevents recurrence)" sub={inv.dbt_test.name}
          right={<Badge t={inv.dbt_test.catches_bug ? "ok" : "warn"}>{inv.dbt_test.catches_bug ? "catches bug" : "—"}</Badge>}>
          <div className="note acc" style={{ marginBottom: 10 }}>
            <Icon d={ICONS.check} /><div>before fix: <b>{inv.dbt_test.before_fix_status}</b> → after fix: <b>{inv.dbt_test.after_fix_status}</b></div>
          </div>
          <div className="diff"><div className="ln ctx" style={{ whiteSpace: "pre-wrap" }}>{inv.dbt_test.yaml}</div></div>
        </Panel>
      )}
    </div>
  );
}

function TrustMatrix({ inv }: { inv: Investigation }) {
  const tm = inv.trust_matrix || {};
  const rows = Object.entries(tm).filter(([k]) => k !== "blockers") as [string, { value: string; risk: string }][];
  const blockers = (tm.blockers as string[]) || [];
  return (
    <div className="grid">
      <Panel title="Trust matrix" sub="Readiness scorecard from trust_scorer">
        <div className="kv">
          {rows.map(([k, val]) => (
            <div key={k}><span className="k">{k.replace(/_/g, " ")}</span>
              <span className="v"><Badge t={tone(val.risk)}>{val.value}</Badge></span></div>
          ))}
        </div>
      </Panel>
      {blockers.length > 0 && (
        <Panel title="Blockers" sub="Must clear before action">
          {blockers.map((b, i) => <div key={i} className="note warn" style={{ marginBottom: 8 }}><Icon d={ICONS.warn} /><div>{b}</div></div>)}
        </Panel>
      )}
    </div>
  );
}

function SidePanel({ inv }: { inv: Investigation }) {
  return (
    <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
      <Panel title="State">
        <div className="kv">
          <div><span className="k">Intent</span><span className="v">{inv.intent || "—"}</span></div>
          <div><span className="k">Risk level</span><span className="v">{inv.risk_level || "—"}</span></div>
          <div><span className="k">Issue mode</span><span className="v">{inv.issue_mode || "—"}</span></div>
          <div><span className="k">Confidence</span><span className="v">{inv.confidence_route || "—"}</span></div>
          <div><span className="k">Anomaly</span><span className="v">{inv.anomaly_type || "—"}</span></div>
          <div><span className="k">Tokens</span><span className="v mono">{inv.tokens?.input ?? "—"} in / {inv.tokens?.output ?? "—"} out</span></div>
          <div><span className="k">Raw rows → LLM</span><span className="v">{inv.raw_rows_to_llm} ✓</span></div>
          <div><span className="k">Cost</span><span className="v mono">{inv.cost_usd != null ? `$${inv.cost_usd}` : "—"}</span></div>
        </div>
      </Panel>
      {inv.lineage?.chain && (
        <Panel title="Lineage / blast radius" sub={`${inv.lineage.blast_radius_size ?? inv.lineage.chain.length} assets affected`}>
          <div className="flow col">
            {inv.lineage.chain.map((n, i) => (
              <div key={i}><div className="fnode"><b>{n}</b></div>{i < inv.lineage!.chain!.length - 1 && <div className="farr">↓</div>}</div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
