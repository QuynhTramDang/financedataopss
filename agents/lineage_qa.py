"""lineage_qa — trả lời câu hỏi lineage/impact (L1 read-only, §10 + Senior DE Assistant).

Reuse memory + lineage + impact_analysis. KHÔNG ghi gì, không sinh patch (tier L1).
Hai mode:
  - definition : "net_revenue tính từ đâu / là gì?" → định nghĩa + source + lineage.
  - impact     : "sửa stg_payment ảnh hưởng gì?" → blast radius downstream.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from tools.impact_analysis import impact_analysis

_MEM = Path(__file__).resolve().parents[1] / "memory"

_IMPACT_KW = ("ảnh hưởng", "anh huong", "impact", "sửa", "thay đổi", "change",
              "downstream", "phụ thuộc", "phu thuoc", "break", "nếu đổi")
_DEF_KW = ("tính từ đâu", "từ đâu", "định nghĩa", "nghĩa là", "là gì", "source", "define", "what")


def _load(name: str) -> list[dict]:
    data = json.loads((_MEM / name).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def _known_assets() -> set[str]:
    assets: set[str] = set()
    for p in _load("pipeline_memory.json"):
        assets.add(p["pipeline"])
        assets.update(p.get("upstream", []))
        assets.update(p.get("downstream", []))
    for m in _load("metric_memory.json"):
        assets.add(m["metric"])
    return assets


def detect_asset(question: str) -> Optional[str]:
    low = question.lower()
    matches = [a for a in _known_assets()
               if a.lower() in low or a.replace("_", " ").lower() in low]
    return max(matches, key=len) if matches else None   # ưu tiên match dài nhất


def _metric_record(metric: str) -> Optional[dict]:
    for m in _load("metric_memory.json"):
        if m["metric"] == metric:
            return m
    return None


def answer(question: str, router=None) -> dict[str, Any]:
    asset = detect_asset(question)
    low = question.lower()
    is_impact = any(k in low for k in _IMPACT_KW)

    base = {"question": question, "asset": asset, "tier": "L1_read_only"}

    if not asset:
        return {**base, "mode": "unknown",
                "answer": "Chưa nhận ra asset/metric trong câu hỏi. Nêu rõ tên bảng/pipeline/metric."}

    if is_impact:
        impact = impact_analysis(asset)
        if not impact["found"]:
            return {**base, "mode": "impact",
                    "answer": f"Không tìm thấy lineage cho '{asset}'."}
        ans = (f"Sửa `{asset}` ảnh hưởng: "
               f"pipelines={impact['affected_pipelines']}, "
               f"metrics={impact['affected_metrics']}, "
               f"reports={impact['affected_reports']}.")
        return {**base, "mode": "impact", "blast_radius": impact, "answer": ans}

    # definition mode
    metric = _metric_record(asset)
    if metric:
        ans = (f"{metric['metric']} = {metric['definition']}. "
               f"Source: {metric.get('source_tables')}. Owner: {metric.get('owner')}.")
        return {**base, "mode": "definition", "metric": metric, "answer": ans}

    # asset là table/pipeline → cho biết nó feed vào đâu
    impact = impact_analysis(asset)
    ans = (f"`{asset}` feed vào: pipelines={impact['affected_pipelines']}, "
           f"metrics={impact['affected_metrics']}, reports={impact['affected_reports']}.")
    return {**base, "mode": "definition", "blast_radius": impact, "answer": ans}
