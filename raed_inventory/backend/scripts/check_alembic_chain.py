#!/usr/bin/env python3
"""
check_alembic_chain.py — Pre-commit hook يتحقّق من سلامة سلسلة alembic migrations.

قواعد:
1. كل revision في alembic/versions/*.py يجب أن يحتوي على `revision = "..."`
   و`down_revision` (إما string أو None للـ baseline فقط).
2. يجب ألّا يوجد أكثر من head واحد (لا branches).
3. يجب ألّا يتكرّر نفس down_revision في ملفّين (يعني branch).

Usage:
    python backend/scripts/check_alembic_chain.py

Exit code:
    0 — OK
    1 — Violation (تفاصيل على stderr)
"""
from __future__ import annotations

import pathlib
import re
import sys
from collections import Counter

# يقبل كلا الصيغتين:
#   revision = "abc"
#   revision: str = "abc"
#   revision: Union[str, None] = None
REVISION_RE = re.compile(
    r'^\s*revision(?:\s*:\s*[^=]+?)?\s*=\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)
DOWN_REVISION_RE = re.compile(
    r'^\s*down_revision(?:\s*:\s*[^=]+?)?\s*=\s*(?:["\']([^"\']+)["\']|None)',
    re.MULTILINE,
)


def main() -> int:
    # اعثر على backend/alembic/versions — سواء شُغّل السكربت من الـ repo root
    # أو من داخل backend/.
    here = pathlib.Path(__file__).resolve().parent
    candidates = [
        here.parent / "alembic" / "versions",                 # backend/alembic/versions
        here.parent.parent / "backend" / "alembic" / "versions",  # repo_root/backend/alembic/versions
    ]
    versions_dir = next((p for p in candidates if p.is_dir()), None)
    if versions_dir is None:
        print("[SKIP] alembic/versions directory not found", file=sys.stderr)
        return 0

    revisions: dict[str, str | None] = {}   # revision → down_revision
    errors: list[str] = []

    for py_file in sorted(versions_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        text = py_file.read_text(encoding="utf-8")
        rev_match = REVISION_RE.search(text)
        down_match = DOWN_REVISION_RE.search(text)
        if not rev_match:
            errors.append(f"{py_file.name}: missing `revision = ...`")
            continue
        if not down_match:
            errors.append(f"{py_file.name}: missing `down_revision = ...`")
            continue
        revisions[rev_match.group(1)] = down_match.group(1)  # None إذا baseline

    # Branch detection: أي down_revision مكرّر = branch
    downs = [d for d in revisions.values() if d is not None]
    dup = [rev for rev, cnt in Counter(downs).items() if cnt > 1]
    if dup:
        errors.append(f"Multiple revisions share the same down_revision: {dup}")

    # Head detection: revision ما يُشار إليه من أي down_revision هو head
    heads = set(revisions.keys()) - set(d for d in revisions.values() if d is not None)
    if len(heads) > 1:
        errors.append(f"Multiple heads detected — should be exactly 1. Heads: {sorted(heads)}")

    if errors:
        print("[FAIL] alembic chain check:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"[OK] alembic chain verified ({len(revisions)} revisions, 1 head)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
