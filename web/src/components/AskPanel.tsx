"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, AskResponse } from "@/lib/api";
import { Icon, ICONS } from "./ui";

interface Turn { q: string; a?: AskResponse; loading?: boolean; }

const SUGGESTIONS = [
  "net_revenue tính từ đâu?",
  "Sửa stg_payment ảnh hưởng gì?",
  "net_revenue tuần này bao nhiêu?",
  "Vì sao net_revenue tuần này giảm?",
];

export default function AskPanel({ prefill, onClose }: { prefill?: string; onClose: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const router = useRouter();
  const bodyRef = useRef<HTMLDivElement>(null);

  async function createInvestigation(question: string, metric?: string) {
    setCreating(true);
    try {
      const r = await api.createFromQuestion(question, metric);
      onClose();
      router.push(`/investigations/${r.id}`);
    } finally { setCreating(false); }
  }

  useEffect(() => { if (prefill) setQ(prefill); }, [prefill]);
  useEffect(() => { bodyRef.current?.scrollTo(0, bodyRef.current.scrollHeight); }, [turns]);

  async function send(text: string) {
    const question = text.trim();
    if (!question) return;
    setQ("");
    setTurns((t) => [...t, { q: question, loading: true }]);
    try {
      const a = await api.ask(question);
      setTurns((t) => t.map((x, i) => i === t.length - 1 ? { ...x, a, loading: false } : x));
    } catch (e) {
      setTurns((t) => t.map((x, i) => i === t.length - 1
        ? { ...x, loading: false, a: { kind: "error", tier: "L1_read_only", answer: `API không phản hồi (${String(e)}).`, computed_from: [] } }
        : x));
    }
  }

  return (
    <aside className="chatpop">
      <div className="dh">
        <span className="spark"><Icon d={ICONS.spark} size={15} /></span>
        <div><b>Ask data</b><br /><small>read-only · L1 · số do tool tính</small></div>
        <button className="x" onClick={onClose}>×</button>
      </div>

      <div className="db" ref={bodyRef}>
        {turns.length === 0 && (
          <div className="suggest">
            <b>Hỏi nhanh về dữ liệu (không tự sửa lỗi)</b>
            <div className="chips">
              {SUGGESTIONS.map((s) => <span key={s} className="chip" onClick={() => send(s)}>{s}</span>)}
            </div>
            <p style={{ marginTop: 14, lineHeight: 1.5 }}>
              Trả lời dựa trên định nghĩa metric, lineage và số liệu tổng hợp có kiểm chứng.
              Câu hỏi hàm ý sửa lỗi sẽ được bàn giao sang một investigation.
            </p>
          </div>
        )}

        {turns.map((t, i) => (
          <div key={i} style={{ display: "grid", gap: 8 }}>
            <div className="ans" style={{ background: "var(--accent-soft)", borderColor: "transparent" }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{t.q}</div>
            </div>
            {t.loading && <div className="skeleton" style={{ width: "80%" }} />}
            {t.a && (
              <div className="ans">
                <div className="q">{t.a.kind} · {t.a.tier}</div>
                <div style={{ fontSize: 13, lineHeight: 1.55 }}>{t.a.answer}</div>
                {t.a.reasoning && t.a.reasoning.length > 0 && (
                  <ul style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: 12.5, lineHeight: 1.55, color: "var(--ink-2)" }}>
                    {t.a.reasoning.map((r, k) => <li key={k} dangerouslySetInnerHTML={{ __html: r.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>") }} />)}
                  </ul>
                )}
                {t.a.proposed_plan && t.a.proposed_plan.length > 0 && (
                  <div className="chips" style={{ marginTop: 8 }}>
                    {t.a.proposed_plan.map((p) => <span key={p} className="chip" style={{ cursor: "default" }}>{p}</span>)}
                  </div>
                )}
                {t.a.computed_from?.length > 0 && (
                  <div className="from">computed from: {t.a.computed_from.join(", ")}</div>
                )}
                {t.a.handoff?.action === "create_investigation" && (
                  <button className="btn primary sm" style={{ marginTop: 10 }} disabled={creating}
                    onClick={() => createInvestigation(t.q, t.a!.handoff!.metric)}>
                    {creating ? "Creating…" : "Create investigation →"}
                  </button>
                )}
                {t.a.handoff?.action === "open_investigation" && (
                  <button className="btn primary sm" style={{ marginTop: 10 }}
                    onClick={() => { onClose(); router.push("/investigations"); }}>Open investigation →</button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <form className="df" onSubmit={(e) => { e.preventDefault(); send(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Hỏi về metric, doanh thu, lineage…" />
        <button className="btn primary sm" type="submit">Hỏi</button>
      </form>
    </aside>
  );
}
