"""LLM-driven planner (orchestrator-workers, bounded).

LLM chỉ ĐỀ XUẤT nên gọi tool nào với input gì (dựa trên đề bài + catalog tool từ registry).
LLM KHÔNG chạy tool, KHÔNG phán verdict. Governance + executor (deterministic) lo phần đó.

Trả về danh sách step thô [{tool, inputs, reason}] hoặc None nếu không có model/LLM lỗi
(caller sẽ dùng fixed fallback plan để vẫn chạy offline + test xanh).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from model_router import LLMSchemaError, ProviderError, get_router

from .registry import ToolRegistry

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "inputs": {"type": "object"},
                    "reason": {"type": "string"},
                },
                "required": ["tool"],
                "additionalProperties": True,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Bạn là planner cho một hệ điều tra dữ liệu Finance. "
    "Chọn các tool CHẨN ĐOÁN cần chạy để tìm nguyên nhân, dựa trên đề bài và danh sách tool. "
    "Chỉ chọn tool trong danh sách. Không bịa tool. Không kết luận root cause — chỉ chọn tool. "
    "Trả JSON {steps:[{tool, inputs, reason}]}."
)


def _catalog(registry: ToolRegistry, allowed_tools: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "tool": r.name,
            "capability": r.capability,
            "description": r.description,
            "required_inputs": r.input_schema.get("required", []),
        }
        for r in registry.list()
        if r.name in allowed_tools
    ]


def build_plan(
    task: dict[str, Any],
    registry: ToolRegistry,
    allowed_tools: set[str],
    *,
    evidence: Optional[list[dict[str, Any]]] = None,
    router: Any = None,
) -> Optional[list[dict[str, Any]]]:
    """Gọi LLM sinh plan. Trả list step thô, [] nếu LLM bảo không cần thêm, None nếu LLM lỗi."""
    router = router or get_router()
    catalog = _catalog(registry, allowed_tools)

    prompt_parts = [
        f"Đề bài điều tra:\n{json.dumps(task, ensure_ascii=False)}",
        f"Tool khả dụng:\n{json.dumps(catalog, ensure_ascii=False)}",
    ]
    if evidence is not None:
        prompt_parts.append(
            "Evidence đã thu được:\n"
            + json.dumps(evidence, ensure_ascii=False)
            + "\n\nChỉ đề xuất tool BỔ SUNG nếu còn thiếu evidence. "
            "Nếu đã đủ, trả steps rỗng."
        )
    prompt = "\n\n".join(prompt_parts)

    try:
        out = router.call_structured(
            route="planner", prompt=prompt, schema=PLAN_SCHEMA, system=_SYSTEM,
        )
    except (LLMSchemaError, ProviderError, Exception):  # noqa: BLE001 — không có model → fallback
        return None

    steps = out.get("steps")
    return steps if isinstance(steps, list) else []
