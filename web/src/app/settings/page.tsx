"use client";
import { api, API_BASE } from "@/lib/api";
import { Panel, PageHead, Badge, useFetch } from "@/components/ui";

export default function SettingsPage() {
  const { data: gov } = useFetch(() => api.governance(), []);
  return (
    <>
      <PageHead crumb="Operate / Profile & settings" title="Profile & settings"
        sub="Your identity, workspace, and the runtime this console is wired to." />
      <div className="grid c2">
        <Panel title="Profile">
          <div className="kv">
            <div><span className="k">Name</span><span className="v">Trâm Đ.</span></div>
            <div><span className="k">Role</span><span className="v">Data Engineer</span></div>
            <div><span className="k">Email</span><span className="v mono">tramdnq@vng.com.vn</span></div>
            <div><span className="k">Workspace</span><span className="v">Finance DataOps</span></div>
            <div><span className="k">Approval authority</span><span className="v"><Badge t="acc">L2 assisted</Badge></span></div>
          </div>
        </Panel>
        <Panel title="Runtime" sub="Where the console reads from">
          <div className="kv">
            <div><span className="k">API base</span><span className="v mono">{API_BASE}</span></div>
            <div><span className="k">Control plane</span><span className="v">LangGraph workflow (graph/workflow.py)</span></div>
            <div><span className="k">Governance tiers</span><span className="v">{gov ? gov.tiers.length : "…"} loaded</span></div>
            <div><span className="k">Raw rows → LLM</span><span className="v"><Badge t="ok">blocked</Badge></span></div>
            <div><span className="k">Environment</span><span className="v">Production (read-mostly)</span></div>
          </div>
        </Panel>
        <Panel title="Preferences (demo)" sub="UI-only, not persisted yet">
          <div className="kv">
            <div><span className="k">Language</span><span className="v">Tiếng Việt / English</span></div>
            <div><span className="k">Theme</span><span className="v">Light</span></div>
            <div><span className="k">Default time range</span><span className="v">Last 24 hours</span></div>
          </div>
        </Panel>
        <Panel title="Notifications (demo)" sub="UI-only">
          <div className="kv">
            <div><span className="k">Failed runs</span><span className="v"><Badge t="ok">on</Badge></span></div>
            <div><span className="k">Pending approvals</span><span className="v"><Badge t="ok">on</Badge></span></div>
            <div><span className="k">Connector health</span><span className="v"><Badge t="ok">on</Badge></span></div>
          </div>
        </Panel>
      </div>
    </>
  );
}
