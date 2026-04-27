-- =============================================================================
-- STAGING / PostgreSQL — معاينة DDL لمراجعة revision e5f6a7b8c9d0 فقط
-- (ملف: alembic/versions/20260417_0004_e5f6a7b8c9d0_phase3_integrity_indexes.py)
-- =============================================================================
--
-- لماذا ليس مخرجات `alembic upgrade head --sql` مباشرة؟
--   - على SQLite، فرع `batch_alter_table` في هذا الـ migration يتطلّب اتصالاً
--     حياً لـ reflection؛ `alembic upgrade d4e5f6a7b8c9:e5f6a7b8c9d0 --sql` يفشل برسالة:
--     "batch mode with dialect sqlite requires a live database connection".
--   - بيئة staging عندكم PostgreSQL؛ هذا الملف يعكس فرع `_is_postgresql()` +
--     أوامر `create_index` الظاهرة في السكربت (بدون IF NOT EXISTS — كما في الكود؛
--     على DB فيها الفهارس مسبقاً قد تحتاج تنظيف يدوي أو تشغيل migration على DB
--     لم تُطبَّق عليها بعد).
--
-- قبل التطبيق: شغّل PRE_MIGRATION_DATA_CHECK.md على نفس الـ DSN.
-- =============================================================================

BEGIN;

-- ─── CHECK constraints (PostgreSQL branch من الـ migration) ───
ALTER TABLE branch_stock
  ADD CONSTRAINT ck_branch_stock_current_nonneg
  CHECK (current_qty >= 0);

ALTER TABLE branch_stock
  ADD CONSTRAINT ck_branch_stock_reserved_nonneg
  CHECK (reserved_qty >= 0);

ALTER TABLE branch_stock
  ADD CONSTRAINT ck_branch_stock_transit_nonneg
  CHECK (in_transit_qty >= 0);

ALTER TABLE warehouse_stock
  ADD CONSTRAINT ck_warehouse_stock_current_nonneg
  CHECK (current_qty >= 0);

ALTER TABLE warehouse_stock
  ADD CONSTRAINT ck_warehouse_stock_reserved_nonneg
  CHECK (reserved_qty >= 0);

-- ─── Indexes (من استدعاءات _safe_create_index في نفس الـ migration) ───
CREATE INDEX ix_users_branch_id ON users (branch_id);
CREATE INDEX ix_users_warehouse_id ON users (warehouse_id);
CREATE INDEX ix_users_is_deleted ON users (is_deleted);

CREATE INDEX ix_branches_warehouse_id ON branches (warehouse_id);
CREATE INDEX ix_branches_active ON branches (active, is_deleted);
CREATE INDEX ix_warehouses_active ON warehouses (active, is_deleted);

CREATE INDEX ix_items_category_id ON items (category_id);
CREATE INDEX ix_items_active_not_deleted ON items (active, is_deleted);

CREATE INDEX ix_branch_stock_branch_id ON branch_stock (branch_id);
CREATE INDEX ix_branch_stock_item_id ON branch_stock (item_id);
CREATE INDEX ix_warehouse_stock_warehouse_id ON warehouse_stock (warehouse_id);
CREATE INDEX ix_warehouse_stock_item_id ON warehouse_stock (item_id);

CREATE INDEX ix_daily_inventory_branch_date ON daily_inventory (branch_id, inventory_date);
CREATE INDEX ix_daily_inventory_status ON daily_inventory (status);
CREATE INDEX ix_daily_inventory_lines_inv_item ON daily_inventory_lines (inventory_id, item_id);

CREATE INDEX ix_orders_branch_status_created ON replenishment_orders (branch_id, status, created_at);
CREATE INDEX ix_orders_warehouse_status ON replenishment_orders (warehouse_id, status);
CREATE INDEX ix_orders_status_created ON replenishment_orders (status, created_at);
CREATE INDEX ix_order_lines_order_item ON replenishment_order_lines (order_id, item_id);

CREATE INDEX ix_stock_tx_item_date ON stock_transactions (item_id, transaction_date);
CREATE INDEX ix_stock_tx_type_date ON stock_transactions (transaction_type, transaction_date);
CREATE INDEX ix_stock_tx_source ON stock_transactions (source_type, source_id);
CREATE INDEX ix_stock_tx_destination ON stock_transactions (destination_type, destination_id);

CREATE INDEX ix_audit_user_id ON audit_logs (user_id);
CREATE INDEX ix_audit_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX ix_audit_created_at ON audit_logs (created_at);

CREATE INDEX ix_idempotency_expires_at ON idempotency_requests (expires_at);

CREATE INDEX ix_qv_branch_date ON quality_visits (branch_id, visit_date);
CREATE INDEX ix_qv_status ON quality_visits (status);
CREATE INDEX ix_qv_responses_visit ON quality_visit_responses (visit_id);

CREATE INDEX ix_train_branch_date ON training_assessments (branch_id, assessment_date);
CREATE INDEX ix_train_trainee ON training_assessments (trainee_id);

CREATE INDEX ix_delivery_records_brand_period ON delivery_records (brand_id, year, month);
CREATE INDEX ix_delivery_records_branch ON delivery_records (branch_id);

-- Alembic يحدّث صف الإصدار (يُنفَّذ من Alembic، ليس دائماً في --sql)
-- UPDATE alembic_version SET version_num = 'e5f6a7b8c9d0' WHERE ...;

COMMIT;

-- =============================================================================
-- مرجع: `alembic current` (ENV_FILE=.env، SQLite محلي) — 2026-04-17
--   Rev: f6a7b8c9d0e1 (head)
--   (قاعدة المطور عند التشغيل كانت بالفعل على head؛ الملف أعلاه = DDL لـ 0004 فقط)
-- =============================================================================
-- مرجع: `alembic history --verbose` (أول مقاطع)
--   f6a7b8c9d0e1 (head) ← e5f6a7b8c9d0 ← d4e5f6a7b8c9 ← c3d4e5f6a7b8 ← ...
--   revision تالية بعد 0004: 20260417_0005_f6a7b8c9d0e1_add_order_type_inter_branch.py
-- =============================================================================
