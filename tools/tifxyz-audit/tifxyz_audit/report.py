"""Human and JSON report formatting."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Sequence

from .checks import Finding


def summarize(findings: Sequence[Finding]) -> dict[str, int]:
    c = Counter(f.severity for f in findings)
    return {k: int(c.get(k, 0)) for k in ("error", "warning", "info")}


def exit_code(findings: Sequence[Finding], *, strict: bool = False) -> int:
    counts = summarize(findings)
    if counts["error"]:
        return 2
    if strict and counts["warning"]:
        return 1
    return 0


def format_text(findings: Sequence[Finding], dirs: Sequence[Any]) -> str:
    lines: list[str] = []
    lines.append(f"tifxyz-audit: scanned {len(dirs)} tifxyz director{'y' if len(dirs)==1 else 'ies'}")
    counts = summarize(findings)
    lines.append(
        f"summary: {counts['error']} error(s), {counts['warning']} warning(s), "
        f"{counts['info']} info"
    )
    order = {"error": 0, "warning": 1, "info": 2}
    for f in sorted(findings, key=lambda x: (order.get(x.severity, 9), x.code, x.path or "")):
        loc = f" @ {f.path}" if f.path else ""
        lines.append(f"[{f.severity.upper():7}] {f.code}: {f.message}{loc}")
    return "\n".join(lines) + "\n"


def format_json(findings: Sequence[Finding], dirs: Sequence[Any]) -> str:
    payload = {
        "scanned": [str(d) for d in dirs],
        "summary": summarize(findings),
        "findings": [f.to_dict() for f in findings],
    }
    return json.dumps(payload, indent=2) + "\n"
