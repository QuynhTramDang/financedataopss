"""lineage_lookup — tìm upstream/downstream của một asset (từ pipeline memory)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PIPE = Path(__file__).resolve().parents[1] / "memory" / "pipeline_memory.json"


def lineage_lookup(asset: str) -> dict[str, Any]:
    """Trả lineage cho pipeline có tên/asset khớp. {pipeline, upstream, downstream, repo_path}."""
    pipelines = json.loads(_PIPE.read_text(encoding="utf-8"))

    def _fmt(p):
        return {"pipeline": p["pipeline"], "upstream": p.get("upstream", []),
                "downstream": p.get("downstream", []), "repo_path": p.get("repo_path"),
                "found": True}

    # ưu tiên match đúng tên pipeline
    for p in pipelines:
        if p["pipeline"] == asset:
            return _fmt(p)
    # fallback: asset là upstream/downstream của pipeline nào đó
    for p in pipelines:
        if asset in (*p.get("upstream", []), *p.get("downstream", [])):
            return _fmt(p)
    return {"asset": asset, "found": False}
