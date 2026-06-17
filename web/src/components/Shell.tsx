"use client";
import { createContext, useContext, useState, ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon, ICONS, Badge, useFetch } from "./ui";
import { api } from "@/lib/api";
import AskPanel from "./AskPanel";

const NAV: { sec?: string; key?: string; label?: string; icon?: string; pill?: "approvals" | "investigations" }[] = [
  { sec: "Operate" },
  { key: "", label: "Overview", icon: ICONS.overview },
  { key: "projects", label: "Projects", icon: ICONS.projects },
  { key: "investigations", label: "Investigations", icon: ICONS.investigations, pill: "investigations" },
  { key: "approvals", label: "Approvals", icon: ICONS.approvals, pill: "approvals" },
  { sec: "Govern" },
  { key: "integrations", label: "Integrations", icon: ICONS.integrations },
  { key: "catalog", label: "Catalog", icon: ICONS.catalog },
  { key: "governance", label: "Governance", icon: ICONS.governance },
  { sec: "Learn" },
  { key: "knowledge", label: "Knowledge", icon: ICONS.knowledge },
];

const AskCtx = createContext<{ open: (prefill?: string) => void }>({ open: () => {} });
export const useAsk = () => useContext(AskCtx);

export default function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [dockOpen, setDockOpen] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>(undefined);
  const [menu, setMenu] = useState<"notif" | "profile" | null>(null);
  const [q, setQ] = useState("");
  const seg = (path || "/").split("/")[1] || "";
  const { data: ov } = useFetch(() => api.overview(), []);

  const openAsk = (p?: string) => { setPrefill(p); setDockOpen(true); };
  const pendingApprovals = ov?.attention.filter((a) => a.kind === "approval").length ?? 0;
  const openInvestigations = ov?.attention.filter((a) => a.kind === "investigation").length ?? 0;
  const notifCount = ov?.attention.length ?? 0;
  const pillCount = (p?: string) => p === "approvals" ? pendingApprovals : p === "investigations" ? openInvestigations : 0;

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (term) router.push(`/investigations?q=${encodeURIComponent(term)}`);
  }
  function gotoAttention(a: { id: string; kind: string }) {
    setMenu(null);
    if (a.kind === "approval") router.push("/approvals");
    else if (a.kind === "integration") router.push("/integrations");
    else router.push(`/investigations/${a.id}`);
  }

  return (
    <AskCtx.Provider value={{ open: openAsk }}>
      <div className="app">
        <aside className="side">
          <div className="brand">
            <div className="mk">F</div>
            <div><h1>Finance DataOps</h1><p>Governed automation console</p></div>
          </div>
          <nav className="nav">
            {NAV.map((n, i) => n.sec
              ? <div className="sec" key={`s${i}`}>{n.sec}</div>
              : (
                <Link key={n.key} href={`/${n.key}`} className={seg === n.key ? "active" : ""}>
                  <Icon d={n.icon!} />{n.label}
                  {n.pill && pillCount(n.pill) > 0 && (
                    <span className={`pill${n.pill === "approvals" ? " amber" : ""}`}>{pillCount(n.pill)}</span>
                  )}
                </Link>
              ))}
          </nav>
          <div className="side-foot"><span className="dot" />Control plane · governed execution</div>
        </aside>

        <main className="main">
          <div className="top">
            <form className="search" onSubmit={submitSearch}>
              <Icon d={ICONS.search} size={15} />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search investigations by id, title, metric…" />
            </form>
            <span className="spacer" />

            <div className="menuwrap">
              <button className={`iconbtn${menu === "notif" ? " on" : ""}`} title="Notifications" onClick={() => setMenu(menu === "notif" ? null : "notif")}>
                <Icon d={ICONS.bell} size={17} />{notifCount > 0 && <span className="nb">{notifCount}</span>}
              </button>
              {menu === "notif" && (
                <div className="menu">
                  <div className="mh">Needs attention <Badge t="bad">{notifCount}</Badge></div>
                  {notifCount === 0 && <div className="mi"><div className="s">All clear — nothing waiting.</div></div>}
                  {ov?.attention.map((a) => (
                    <div key={a.id + a.title} className="mi" onClick={() => gotoAttention(a)}>
                      <div className="t">{a.title}</div><div className="s">{a.status} · {a.sub}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="menuwrap">
              <button className="who" onClick={() => setMenu(menu === "profile" ? null : "profile")}>
                <span className="av">TD</span>
                <div style={{ textAlign: "left" }}><div style={{ fontSize: 12.5, fontWeight: 650 }}>Trâm Đ.</div><small>Data Engineer</small></div>
              </button>
              {menu === "profile" && (
                <div className="menu narrow">
                  <div className="mh">tramdnq@vng.com.vn</div>
                  <Link href="/settings" className="mrow" onClick={() => setMenu(null)}><Icon d={ICONS.overview} size={15} />Profile & settings</Link>
                  <Link href="/governance" className="mrow" onClick={() => setMenu(null)}><Icon d={ICONS.governance} size={15} />Governance policies</Link>
                  <div className="mrow" onClick={() => setMenu(null)} style={{ color: "var(--bad)" }}><Icon d={ICONS.warn} size={15} />Sign out (demo)</div>
                </div>
              )}
            </div>
          </div>
          <section className="content">{children}</section>
        </main>
      </div>

      {menu && <div className="backdrop" onClick={() => setMenu(null)} />}

      {dockOpen
        ? <AskPanel prefill={prefill} onClose={() => setDockOpen(false)} />
        : <button className="fab" title="Ask data" onClick={() => setDockOpen(true)}><Icon d={ICONS.spark} size={20} /><span>Ask data</span></button>}
    </AskCtx.Provider>
  );
}
