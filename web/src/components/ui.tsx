"use client";
import { useEffect, useState, ReactNode } from "react";
import Link from "next/link";

// status text -> tone (color carries meaning)
const TONE: Record<string, string> = {
  active: "ok", success: "ok", healthy: "ok", verified: "ok", resolved: "ok", done: "ok", pass: "ok", ok: "ok", allowed: "ok", L3: "ok",
  paused: "warn", attention: "warn", pending: "warn", "needs_approval": "warn", "needs approval": "warn",
  "pending approval": "warn", "retry scheduled": "warn", running: "warn", warn: "warn", "needs_revision": "warn", medium: "warn", med: "warn", awaiting_rerun: "warn", L2: "acc",
  failed: "bad", degraded: "bad", high: "bad", escalated: "bad", rejected: "bad", blocked: "bad", bad: "bad",
  L1: "neu",
};
export const tone = (s?: string) => TONE[(s || "").trim()] || "neu";

export function Badge({ children, t }: { children: ReactNode; t?: string }) {
  const tn = t || tone(String(children));
  return <span className={`badge b-${tn}`}><span className="d" />{children}</span>;
}

export function Icon({ d, size = 16 }: { d: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
  );
}

export function Panel({ title, sub, right, children, flush }: {
  title: string; sub?: string; right?: ReactNode; children: ReactNode; flush?: boolean;
}) {
  return (
    <section className="panel">
      <div className="ph"><div><h3>{title}</h3>{sub && <div className="sub">{sub}</div>}</div>{right}</div>
      <div className={`pb${flush ? " flush" : ""}`}>{children}</div>
    </section>
  );
}

export function Metric({ k, v, d }: { k: string; v: string; d?: string }) {
  return <div className="panel metric"><div className="k">{k}</div><div className="v">{v}</div>{d && <div className="d">{d}</div>}</div>;
}

const CRUMB_HREF: Record<string, string> = {
  Overview: "/", Investigations: "/investigations", Approvals: "/approvals",
  Integrations: "/integrations", Catalog: "/catalog", "Data Catalog": "/catalog",
  Governance: "/governance", Knowledge: "/knowledge",
};

export function PageHead({ crumb, title, sub, actions }: { crumb: string; title: string; sub: string; actions?: ReactNode }) {
  const segs = crumb.split("/").map((s) => s.trim());
  return (
    <div className="head">
      <div>
        <div className="crumb">
          {segs.map((s, i) => {
            const href = CRUMB_HREF[s];
            const last = i === segs.length - 1;
            return (
              <span key={i}>
                {href && !last ? <Link href={href} className="crumb-link">{s}</Link> : <span>{s}</span>}
                {!last && <span className="crumb-sep"> / </span>}
              </span>
            );
          })}
        </div>
        <h2>{title}</h2><p>{sub}</p>
      </div>
      <div className="actions">{actions}</div>
    </div>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  return <div className="panel pb" style={{ display: "grid", gap: 12 }}>
    {Array.from({ length: rows }).map((_, i) => <div key={i} className="skeleton" style={{ width: `${90 - i * 8}%` }} />)}
  </div>;
}

export function Empty({ icon = "∅", text }: { icon?: string; text: string }) {
  return <div className="panel"><div className="empty"><div className="ic">{icon}</div><p>{text}</p></div></div>;
}

// client data hook
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[] = []): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fn().then((d) => { if (alive) { setData(d); setError(null); } })
      .catch((e) => { if (alive) setError(String(e.message || e)); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}

export const ICONS = {
  overview: "M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z",
  investigations: "M4 6h16M4 12h10M4 18h7",
  approvals: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z M9 12l2 2 4-5",
  integrations: "M9 7H7a5 5 0 0 0 0 10h2m6-10h2a5 5 0 0 1 0 10h-2M8 12h8",
  catalog: "M5 4h13v16H6a2 2 0 0 1-1-2zM8 8h7M8 12h7",
  governance: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z",
  knowledge: "M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2zM8 8h7M8 12h5",
  projects: "M3 7h7l2 2h9v10H3zM3 7V5h5l2 2",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14m10 17-4.3-4.3",
  spark: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2",
  bell: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 0 0 4 0",
  check: "M9 12l2 2 4-5",
  warn: "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
};
