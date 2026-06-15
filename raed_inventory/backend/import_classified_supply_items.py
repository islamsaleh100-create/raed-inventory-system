from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal  # noqa: E402
from app.startup_schema import ensure_local_schema_compatibility  # noqa: E402
from app.services.supply_item_master_import_service import import_supply_item_master  # noqa: E402


DEFAULT_WORKBOOK = Path(r"C:\raed_inventory_system\classified_supply_items.xlsx")


def main() -> int:
    workbook_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WORKBOOK
    if not workbook_path.exists():
        print(json.dumps({"error": f"Workbook not found: {workbook_path}"}, ensure_ascii=False))
        return 1

    ensure_local_schema_compatibility()
    db = SessionLocal()
    try:
        result = import_supply_item_master(db, workbook_path)
        payload = result.as_dict()
        payload["workbook_path"] = str(workbook_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
