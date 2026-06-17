// API client for the FastAPI control-plane boundary (api/server.py).

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

// ── types (loose; mirror api/fixtures.py) ──
export type Tone = "ok" | "warn" | "bad" | "acc" | "neu";

export interface InvestigationSummary {
  id: string; title: string; metric?: string; date?: string;
  source: string; trigger: string; status: string; severity: string;
  confidence_route?: string; anomaly_type?: string; cost_usd?: number;
  started_at?: string; duration?: string; domain?: string; project?: string;
}

export interface Project {
  key: string; label: string; owner: string; metric: string;
  investigations: number; open: number; needs_approval: number;
}

export interface TraceCall { name: string; tier: string; status: string; duration: string; detail: string; }
export interface TraceStage { stage: string; name: string; status: string; duration: string; detail: string; calls: TraceCall[]; }
export interface Claim { claim: string; evidence: string; rule: string; status: string; }
export interface Evidence { type: string; body: string; }
export type DiffLine = [string, string];
export interface Patch { file: string; diff: DiffLine[]; review: string; risk_level: string; approval_required: boolean; }

export interface Investigation extends InvestigationSummary {
  intent?: string; risk_level?: string; issue_mode?: string;
  tokens?: { input?: number; output?: number }; raw_rows_to_llm?: number;
  root_cause?: string;
  trace: TraceStage[]; claims: Claim[]; evidence: Evidence[];
  patch?: Patch | null;
  validation?: { status: string; attempts: number; before_pct: number | null; after_pct: number | null; tests: { name: string; status: string }[] } | null;
  dbt_test?: { name: string; catches_bug: boolean; before_fix_status: string; after_fix_status: string; yaml: string } | null;
  trust_matrix?: Record<string, { value: string; risk: string } | string[]>;
  lineage?: { asset?: string; chain?: string[]; affected_reports?: string[]; blast_radius_size?: number };
  approval_status?: string;
  agent_run?: boolean;
  approval_id?: string;
  rerun_approval_id?: string;
}

export interface ActionStep { name: string; tier: string; status: string; detail: string; link?: string; }
export interface Approval {
  id: string; investigation_id: string; title: string; automation: string;
  risk: string; impact: string; age: string; why: string; rollback: string;
  validation: string; status: string;
  action_result?: { steps: ActionStep[]; audit: string[]; mode?: string } | null;
  investigation_title?: string; investigation_status?: string; domain?: string;
  stage?: string; mr_merged?: boolean; mr_web_url?: string; rerun_approval_id?: string;
}

export interface Overview {
  kpis: { k: string; v: string; d: string }[];
  attention: { id: string; title: string; severity: string; status: string; sub: string; kind: string }[];
  triggers: { name: string; kind: string; last: string; success: string }[];
}

export interface Integration { name: string; type: string; status: string; auth: string; scopes: string; calls: string; error_rate: string; note: string; }
export interface McpHealth {
  mcp_live: boolean;
  servers: { name: string; enabled: boolean; connected: boolean; tools?: string[]; detail?: string }[];
}
export interface CatalogItem { name: string; kind: string; owner: string; status: string; definition: string; sources: string[]; lineage: string[]; contract_tests: { name: string; status: string }[]; domain?: string; investigations?: number; }
export interface Dag { id: string; status: string; owner: string; sla: string; last: string; runtime: string; success: string; alert: string; project?: string; investigation_id?: string | null; }
export interface Governance {
  tiers: { tier: string; decision: string; examples: string }[];
  audit_posture: { k: string; v: string }[];
  tool_checks: { tool: string; decision: string; tier: string | null; requires_approval: boolean; reason: string }[];
}
export interface AskResponse {
  kind: string; tier: string; answer: string; computed_from: string[];
  reasoning?: string[]; proposed_plan?: string[]; blast_radius?: unknown;
  handoff?: { action: string; prefill: string; metric?: string } | null;
}

export interface LogLine { n: number; level: string; text: string; }
export interface Triage { failure_type: string; confidence: number; action: string; tier: string; requires_approval: boolean; auto_action_taken: string | null; audit: string[]; summary: string; }
export interface LogsResponse { job: string | null; found: boolean; lines: LogLine[]; raw_url: string | null; triage: Triage | null; note?: string; }

export interface StepArtifact {
  kind: "diff" | "tests" | "compare" | "yaml" | "log" | "audit";
  file?: string; diff?: DiffLine[];
  tests?: { name: string; status: string; note: string }[];
  before_pct?: number; after_pct?: number; yaml?: string; job?: string; audit?: string[];
}
export interface CheckStep { key: string; title: string; status: "pass" | "fail" | "running" | "idle"; detail: string; artifact?: StepArtifact | null; }
export interface RunCheck {
  runnable: boolean; kind: string; message?: string; overall?: string;
  steps?: CheckStep[];
  reconciliation?: { before_pct: number; after_pct: number };
  dbt?: { before_fix_status: string; after_fix_status: string; catches_bug: boolean };
}

export const api = {
  overview: () => get<Overview>("/api/overview"),
  projects: () => get<Project[]>("/api/projects"),
  investigations: (q = "") => get<InvestigationSummary[]>(`/api/investigations${q}`),
  investigation: (id: string) => get<Investigation>(`/api/investigations/${id}`),
  approvals: () => get<Approval[]>("/api/approvals"),
  decide: (id: string, decision: string) => post<Approval>(`/api/approvals/${id}`, { decision }),
  integrations: () => get<Integration[]>("/api/integrations"),
  mcpHealth: () => get<McpHealth>("/api/integrations/health"),
  catalog: () => get<CatalogItem[]>("/api/catalog"),
  dags: () => get<Dag[]>("/api/dags"),
  governance: () => get<Governance>("/api/governance"),
  knowledge: () => get<{ learned: { incident_id: string; metric: string; root_cause: string; fix: string; prevented_by: string }[] }>("/api/knowledge"),
  ask: (question: string, metric?: string, date?: string) => post<AskResponse>("/api/ask", { question, metric, date }),
  createFromQuestion: (question: string, metric?: string) => post<{ id: string; title: string }>("/api/investigations/from-question", { question, metric }),
  logs: (id: string) => get<LogsResponse>(`/api/investigations/${id}/logs`),
  runAgent: (id: string) => post<{ ok: boolean; mode: string; investigation: Investigation }>(`/api/investigations/${id}/run-agent`, {}),
  runCheck: (id: string) => post<RunCheck>(`/api/investigations/${id}/run-check`, {}),
};
export const rawLogUrl = (path: string) => `${API_BASE}${path}`;
