"""L1 — add missing ORM columns to SQLite (idempotent)."""
import os
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), "raed_inventory_local.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

def ensure_column(table: str, col_def: str) -> None:
    col_name = col_def.split()[0]
    cur.execute(f"PRAGMA table_info({table})")
    cols = {r[1] for r in cur.fetchall()}
    if col_name in cols:
        print(f"Skip {table}.{col_name} (exists)")
        return
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
        print(f"Added {table}.{col_name}")
    except Exception as e:
        print(f"Failed {table}.{col_name}: {e}")

for d in [
    "resolved_by INTEGER",
    "resolved_at DATETIME",
    "numeric_value NUMERIC(12,2)",
    "text_value TEXT",
    "is_resolved BOOLEAN DEFAULT 0",
]:
    ensure_column("quality_visit_responses", d)

for d in [
    "visitor_signature VARCHAR(200)",
    "visitor_signed_at DATETIME",
    "branch_mgr_signature VARCHAR(200)",
    "branch_mgr_signed_at DATETIME",
]:
    ensure_column("quality_visits", d)

for d in [
    "text_en TEXT",
    "benchmark_ar TEXT",
    "benchmark_en TEXT",
    "numeric_unit VARCHAR(20)",
    "response_type VARCHAR(10) DEFAULT 'yes_no'",
]:
    ensure_column("quality_visit_items", d)

for d in [
    "rejection_reason TEXT",
    "evaluator_signature VARCHAR(200)",
    "evaluator_signed_at DATETIME",
    "approver_signature VARCHAR(200)",
    "approver_signed_at DATETIME",
]:
    ensure_column("training_assessments", d)

ensure_column("training_templates", "name_en VARCHAR(200)")
ensure_column("training_template_sections", "name_en VARCHAR(100)")

ensure_column("replenishment_orders", "destination_branch_id INTEGER")

con.commit()
con.close()
print("Done.")
