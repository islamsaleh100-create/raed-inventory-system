"""L1 — one-off DB schema diagnostic (run from backend/)."""
import os
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), "raed_inventory_local.db")
if not os.path.exists(db_path):
    print("DB not found:", db_path)
    raise SystemExit(1)
con = sqlite3.connect(db_path)
cur = con.cursor()

required_tables = [
    "quality_visits",
    "quality_visit_responses",
    "quality_visit_items",
    "quality_visit_sections",
    "quality_visit_attachments",
    "training_assessments",
    "training_templates",
    "training_template_items",
    "replenishment_orders",
]
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
existing = {row[0] for row in cur.fetchall()}
print("=== TABLES ===")
for t in required_tables:
    status = "OK" if t in existing else "MISSING"
    print(f"  [{status}] {t}")

print()
print("=== CRITICAL COLUMNS ===")
checks = [
    ("training_template_items", "text_en"),
    ("training_template_items", "benchmark_en"),
    ("replenishment_orders", "submitted_to_warehouse_at"),
    ("replenishment_orders", "dispatched_at"),
    ("replenishment_orders", "received_at"),
    ("replenishment_orders", "destination_branch_id"),
    ("quality_visit_responses", "corrective_action"),
    ("quality_visit_responses", "action_owner"),
    ("quality_visit_responses", "due_date"),
    ("quality_visit_responses", "resolved_at"),
    ("quality_visit_responses", "resolved_by"),
]
for tbl, col in checks:
    if tbl not in existing:
        print(f"  [SKIP] {tbl}.{col} (table missing)")
        continue
    cur.execute(f"PRAGMA table_info({tbl})")
    cols = {row[1] for row in cur.fetchall()}
    status = "OK" if col in cols else "MISSING"
    print(f"  [{status}] {tbl}.{col}")

print()
print("=== SEED DATA ===")
for tbl in ["training_templates", "training_template_items", "quality_visit_items"]:
    if tbl in existing:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  {tbl}: {cur.fetchone()[0]} rows")

con.close()
