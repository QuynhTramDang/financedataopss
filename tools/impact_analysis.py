"""impact_analysis — blast radius downstream của một asset (table/pipeline) từ lineage memory.

Trả lời câu hỏi senior: "sửa asset này thì ảnh hưởng metric/report/pipeline nào?"
Deterministic: BFS trên đồ thị lineage dựng từ pipeline_memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PIPE = Path(__file__).resolve().parents[1] / "memory" / "pipeline_memory.json"


def _pipelines() -> list[dict]:
    return json.loads(_PIPE.read_text(encoding="utf-8"))


def _build_graph(pipelines: list[dict]) -> dict[str, set[str]]:
    """Đồ thị có hướng: upstream → pipeline → downstream."""
    adj: dict[str, set[str]] = {}
    for p in pipelines:
        name = p["pipeline"]
        adj.setdefault(name, set())
        for u in p.get("upstream", []):
            adj.setdefault(u, set()).add(name)
        for d in p.get("downstream", []):
            adj.setdefault(name, set()).add(d)
            adj.setdefault(d, set())
    return adj


def downstream_closure(asset: str, adj: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(adj.get(asset, set()))
    while stack:
        node = stack.pop()
        if node not in seen:
            seen.add(node)
            stack.extend(adj.get(node, set()))
    return seen


def impact_analysis(asset: str) -> dict[str, Any]:
    pipelines = _pipelines()
    pipeline_by_name = {p["pipeline"]: p for p in pipelines}
    adj = _build_graph(pipelines)

    if asset not in adj:
        return {"asset": asset, "found": False, "affected_pipelines": [],
                "affected_metrics": [], "affected_reports": []}

    closure = downstream_closure(asset, adj)
    affected_pipelines = sorted(n for n in closure if n in pipeline_by_name)
    affected_metrics = sorted(
        {pipeline_by_name[p]["metric"] for p in affected_pipelines if pipeline_by_name[p].get("metric")}
    )
    affected_reports = sorted(n for n in closure if n not in pipeline_by_name)

    return {
        "asset": asset,
        "found": True,
        "affected_pipelines": affected_pipelines,
        "affected_metrics": affected_metrics,
        "affected_reports": affected_reports,
        "blast_radius_size": len(closure),
    }
