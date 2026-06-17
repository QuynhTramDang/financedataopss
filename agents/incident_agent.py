"""incident_agent — xử lý job-fail như senior DE (Step 17).

Flow: đọc log → phân loại → quyết action theo tier:
  transient    → L3 auto-retry (reversible) + audit "no manual action".
  schema_drift → L2 propose patch/PR → human approve.
  code_bug     → L2 propose fix → human approve.
  data_quality → L3 notify_owner + escalate.
  permission   → escalate (notify owner) — không auto.
  unknown      → escalate.
Mọi action ghi audit. L3 chỉ chạy action trong allow-list (action_policy).
"""

from __future__ import annotations

from typing import Any

from governance.action_policy import decide_action, is_autonomous_allowed
from tools.log_search import log_search
from tools.run_classifier import classify_failure


def handle_incident(job: str, log_text: str | None = None) -> dict[str, Any]:
    """Xử lý 1 incident job-fail. Trả kết quả gồm action, auto-action (nếu có), audit, message."""
    if log_text is None:
        found = log_search(job)
        log_text = found["log"]
        if not found["found"]:
            return {"job": job, "failure_type": "unknown",
                    "action": "escalate", "summary": f"Không tìm thấy log cho job '{job}'."}

    cls = classify_failure(log_text)
    ftype = cls["failure_type"]
    decision = decide_action(ftype)

    audit: list[str] = [f"classified={ftype} (conf={cls['confidence']})"]
    auto_action_taken = None

    # Chỉ chạy tự động nếu: autonomous + action nằm trong allow-list L3
    if decision["autonomous"] and is_autonomous_allowed(decision["action"]):
        auto_action_taken = decision["action"]
        if decision["action"] == "retry_job":
            audit.append("auto-retry với exponential backoff → success (giả lập)")
        else:
            audit.append(f"auto {decision['action']} (reversible)")
    else:
        audit.append(f"đề xuất: {decision['action']} (tier {decision['tier']}, "
                     f"approval={'required' if decision['requires_approval'] else 'no'})")

    summary = _summary(job, ftype, cls, decision, auto_action_taken)
    return {
        "job": job,
        "failure_type": ftype,
        "confidence": cls["confidence"],
        "action": decision["action"],
        "tier": decision["tier"],
        "requires_approval": decision["requires_approval"],
        "auto_action_taken": auto_action_taken,
        "audit": audit,
        "summary": summary,
    }


def _summary(job, ftype, cls, decision, auto) -> str:
    next_step = ("No manual action needed." if auto == "retry_job"
                 else f"{decision['action']} (cần human approval)"
                 if decision["requires_approval"] else f"{decision['action']}")
    return (
        f"[Incident] {job} failed\n"
        f"Likely cause: {ftype} (matched: {', '.join(cls['matched']) or 'n/a'})\n"
        f"Action: {auto or decision['action']} (tier {decision['tier']})\n"
        f"Next step: {next_step}\n"
        f"Confidence: {int(cls['confidence'] * 100)}%"
    )
