"""code_search — tìm đoạn code liên quan trong pipeline SQL + trích enum được handle.

Hỗ trợ tìm ĐA-FILE theo lineage (metric → dtm → ods → stg) để chỉ đúng tầng chứa logic/bug,
thay vì chỉ đọc cố định một file. Dùng làm evidence cho root cause ("pipeline có handle value này không").
"""

from __future__ import annotations

import re
from typing import Any, Optional

from database.connection import read_sql_file


def code_search(
    pattern: str,
    source: Optional[str] = None,
    repo_paths: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Tìm các dòng chứa `pattern` (case-insensitive) trong code SQL.

    Nguồn (BẮT BUỘC một trong hai, không fallback file mặc định — fail-loud):
      - `source`      : tìm thẳng trên chuỗi cho trước (test/inline).
      - `repo_paths`  : tìm trên nhiều file theo lineage (mỗi match kèm `file`).

    Trả {matches: [{file, line_no, text}], handled_values: [...], files_searched: [...]}.
    handled_values = các literal '...' xuất hiện trên dòng có chứa `pattern`.
    """
    pat = pattern.lower()

    if source is not None:
        files: list[tuple[Optional[str], str]] = [(None, source)]
    elif repo_paths:
        files = []
        for rp in repo_paths:
            try:
                files.append((rp, read_sql_file(rp)))
            except OSError:
                continue  # file lineage không tồn tại → bỏ qua, không làm vỡ
    else:
        raise ValueError("code_search yêu cầu `repo_paths` hoặc `source` (không có file mặc định).")

    matches: list[dict[str, Any]] = []
    handled: set[str] = set()
    for label, text in files:
        for i, line in enumerate(text.splitlines(), start=1):
            # bỏ phần comment ('--...') — chỉ xét code thực thi
            code = line.split("--", 1)[0]
            if not code.strip():
                continue
            if pat in code.lower():
                matches.append({"file": label, "line_no": i, "text": code.strip()})
                for lit in re.findall(r"'([^']+)'", code):
                    handled.add(lit)

    return {
        "matches": matches,
        "handled_values": sorted(handled),
        "files_searched": [label for label, _ in files],
    }
