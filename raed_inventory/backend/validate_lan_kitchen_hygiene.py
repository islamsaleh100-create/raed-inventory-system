#!/usr/bin/env python3
"""
LAN Trial kitchen hygiene validation (read-only).

Ensures only official kitchens exist for LAN trial (no Playwright/Flow/test kitchens).

Usage (from backend/):
  python validate_lan_kitchen_hygiene.py [--write-report]

Exit codes:
  0 = GO or GO WITH WARNINGS (dev DB with extra test kitchens documented)
  1 = NO-GO when run with --strict-lan-trial
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Kitchen

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent.parent

OFFICIAL_KITCHEN_NAMES = (
    "Kitchen Dammam",
    "Kitchen Riyadh",
    "Official Kitchen – Dammam",
    "Official Kitchen - Dammam",
    "Official Kitchen – Riyadh",
    "Official Kitchen - Riyadh",
)

FORBIDDEN_NAME_FRAGMENTS = (
    "flow kitchen",
    "pw kitchen",
    "playwright",
    "test kitchen",
    "demo kitchen",
)


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _is_official(name: str) -> bool:
    n = _normalize(name)
    if name in OFFICIAL_KITCHEN_NAMES:
        return True
    if "kitchen" in n and "dammam" in n and "flow" not in n and "pw" not in n:
        return True
    if "kitchen" in n and "riyadh" in n and "flow" not in n and "pw" not in n:
        return True
    return False


def _is_forbidden(name: str) -> bool:
    n = _normalize(name)
    return any(frag in n for frag in FORBIDDEN_NAME_FRAGMENTS)


def validate(*, strict_lan_trial: bool) -> dict:
    db = SessionLocal()
    try:
        kitchens = db.query(Kitchen).order_by(Kitchen.name).all()
        official = [k for k in kitchens if _is_official(k.name)]
        forbidden = [k for k in kitchens if _is_forbidden(k.name)]
        unexpected = [k for k in kitchens if k not in official and k not in forbidden]

        has_dammam = any("dammam" in _normalize(k.name) for k in official)
        has_riyadh = any("riyadh" in _normalize(k.name) for k in official)

        if strict_lan_trial:
            verdict = "GO" if (not forbidden and not unexpected and has_dammam and has_riyadh) else "NO-GO"
        else:
            if forbidden or unexpected:
                verdict = "GO WITH WARNINGS"
            elif not (has_dammam and has_riyadh):
                verdict = "GO WITH WARNINGS"
            else:
                verdict = "GO"

        return {
            "verdict": verdict,
            "total": len(kitchens),
            "official": [{"id": k.id, "name": k.name, "city": k.city, "active": k.active} for k in official],
            "forbidden": [{"id": k.id, "name": k.name, "city": k.city} for k in forbidden],
            "unexpected": [{"id": k.id, "name": k.name, "city": k.city} for k in unexpected],
            "has_dammam_official": has_dammam,
            "has_riyadh_official": has_riyadh,
            "strict_lan_trial": strict_lan_trial,
        }
    finally:
        db.close()


def write_report(result: dict) -> Path:
    path = REPO_ROOT / "LAN_KITCHEN_HYGIENE_REPORT.md"
    lines = [
        "# LAN Kitchen Hygiene Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC",
        f"**Verdict:** {result['verdict']}",
        "",
        "## Official kitchens required",
        "",
        "- Kitchen Dammam (or Official Kitchen – Dammam)",
        "- Kitchen Riyadh (or Official Kitchen – Riyadh)",
        "",
        "## Summary",
        "",
        f"- Total kitchens in DB: **{result['total']}**",
        f"- Official matches: **{len(result['official'])}**",
        f"- Forbidden test/flow kitchens: **{len(result['forbidden'])}**",
        f"- Other unexpected: **{len(result['unexpected'])}**",
        "",
        "## Forbidden (must not exist on LAN trial DB)",
        "",
    ]
    if result["forbidden"]:
        for k in result["forbidden"]:
            lines.append(f"- `{k['name']}` ({k['city']})")
    else:
        lines.append("- None detected")
    lines += ["", "## Unexpected kitchens", ""]
    if result["unexpected"]:
        for k in result["unexpected"]:
            lines.append(f"- `{k['name']}` ({k['city']})")
    else:
        lines.append("- None")
    lines += ["", "## Official matches", ""]
    for k in result["official"]:
        lines.append(f"- `{k['name']}` — {k['city']} (active={k['active']})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate LAN trial kitchen hygiene")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument(
        "--strict-lan-trial",
        action="store_true",
        help="Fail (NO-GO) if any forbidden or unexpected kitchen exists",
    )
    args = parser.parse_args()
    result = validate(strict_lan_trial=args.strict_lan_trial)
    print(f"Verdict: {result['verdict']}")
    print(f"Official: {len(result['official'])} | Forbidden: {len(result['forbidden'])} | Unexpected: {len(result['unexpected'])}")
    if args.write_report:
        path = write_report(result)
        print(f"Wrote {path}")
    return 0 if result["verdict"] != "NO-GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
