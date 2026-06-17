"""notify_teams — gửi thông báo vào MS Teams qua Incoming Webhook (không qua MCP — webhook thuần).

Không có TEAMS_WEBHOOK_URL → no-op (skipped), không làm vỡ luồng. Dùng ở apply_remediation.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


def notify_teams(text: str) -> dict[str, Any]:
    url = os.getenv("TEAMS_WEBHOOK_URL")
    if not url:
        return {"status": "skipped", "reason": "no TEAMS_WEBHOOK_URL"}
    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)  # noqa: S310 — webhook nội bộ
        return {"status": "sent"}
    except Exception as exc:  # noqa: BLE001 — notify lỗi không được làm vỡ luồng
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
