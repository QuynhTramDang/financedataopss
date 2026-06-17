"""MCP server tối thiểu cho GitLab (SDK `mcp`, stdio) — wrap GitLab REST API v4.

MCP server THẬT, chạy LOCAL, gọi gitlab.com bằng token CỦA BẠN (env, không hardcode). Tool khớp
registry.mcp_tool:
  - get_pipeline_status (read)   ← gitlab_pipeline_status
  - create_merge_request (write) ← gitlab_create_mr  (tạo branch + commit proposal + mở MR)

Env: GITLAB_TOKEN (scope `api`), GITLAB_PROJECT_ID, GITLAB_API_URL (mặc định https://gitlab.com/api/v4).
KHÔNG merge — chỉ TẠO MR (proposal), đúng nguyên tắc no-auto-deploy.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
TOKEN = os.getenv("GITLAB_TOKEN", "")
PROJECT = urllib.parse.quote(str(os.getenv("GITLAB_PROJECT_ID", "")), safe="")

mcp = FastMCP("gitlab")


def _gl(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{BASE}/projects/{PROJECT}{path}", data=data, method=method,
        headers={"PRIVATE-TOKEN": TOKEN, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        return {"_http_error": exc.code, "detail": exc.read().decode(errors="ignore")[:300]}


@mcp.tool()
def get_pipeline_status(ref: str = "") -> dict:
    """Trạng thái pipeline CI mới nhất (theo ref nếu có)."""
    q = f"?ref={urllib.parse.quote(ref)}&per_page=1" if ref else "?per_page=1"
    res = _gl(f"/pipelines{q}")
    if isinstance(res, dict) and res.get("_http_error"):
        return res
    return res[0] if res else {"status": "no_pipeline"}


@mcp.tool()
def create_merge_request(title: str, description: str = "",
                         source_branch: str = "", target_branch: str = "") -> dict:
    """Tạo branch (nếu chưa có) + commit file proposal + mở MR. Trả {iid, web_url, state}."""
    if not target_branch:
        proj = _gl("")
        target_branch = proj.get("default_branch", "main") if isinstance(proj, dict) else "main"
    source_branch = source_branch or "fix/auto"

    # 1) tạo branch off target (bỏ qua nếu đã tồn tại)
    _gl(f"/repository/branches?branch={urllib.parse.quote(source_branch)}"
        f"&ref={urllib.parse.quote(target_branch)}", method="POST")

    # 2) commit 1 file proposal để có diff (không đụng code thật)
    _gl("/repository/commits", method="POST", body={
        "branch": source_branch,
        "commit_message": f"[DataOps Twin] proposal: {title}",
        "actions": [{"action": "create",
                     "file_path": f"proposed/{source_branch.replace('/', '_')}.md",
                     "content": f"# {title}\n\n{description}\n"}],
    })

    # 3) mở MR (nếu trùng → trả MR đang có)
    mr = _gl("/merge_requests", method="POST", body={
        "source_branch": source_branch, "target_branch": target_branch,
        "title": title, "description": description,
    })
    if isinstance(mr, dict) and mr.get("_http_error"):
        existing = _gl(f"/merge_requests?source_branch={urllib.parse.quote(source_branch)}&state=opened")
        if isinstance(existing, list) and existing:
            mr = existing[0]
    return {"iid": mr.get("iid"), "web_url": mr.get("web_url"),
            "state": mr.get("state"), "error": mr.get("_http_error")}


if __name__ == "__main__":
    mcp.run()
