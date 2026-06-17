"""Đảm bảo repo root nằm trên sys.path + cách ly memory write-back khỏi file thật khi test."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# memory_writeback ghi vào file tạm khi chạy test (không đụng memory/incident_memory.json thật)
os.environ.setdefault(
    "DATAOPS_INCIDENT_MEMORY",
    str(Path(tempfile.gettempdir()) / "dataops_test_incident_memory.json"),
)
