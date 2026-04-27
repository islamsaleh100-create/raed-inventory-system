# Pre-migration data check (before `20260417_0004` CHECK constraints)

**DB المفحوصة:** SQLite محلي حسب `DATABASE_URL` في `.env`  
`sqlite:///C:/raed_inventory_system/raed_inventory/backend/raed_inventory_local.db`  
**تاريخ التشغيل:** 2026-04-17

> **تصحيح أسماء الأعمدة:** جدول `items` في الموديل الحالي يستخدم **`min_qty`** و **`max_qty`** (وليس `min_level` / `max_level`). الاستعلامات أدناه تستخدم الأسماء الفعلية.

---

## نتائج الـ SELECT (COUNT)

| check_name | count |
|------------|------:|
| branch_stock_negative_current | 0 |
| branch_stock_negative_reserved | 0 |
| branch_stock_negative_transit (`in_transit_qty < 0`) | 0 |
| warehouse_stock_negative_current | 0 |
| warehouse_stock_negative_reserved | 0 |
| items_bad_min_qty (`min_qty < 0`) | 0 |
| items_max_lt_min_qty (`max_qty < min_qty`) | 0 |

**الخلاصة:** لا توجد صفوف مخالفة في نسخة SQLite المحلية المفحوصة؛ **ترقية Alembic 0004 لا يُتوقع أن تفشل بسبب بيانات سالبة على هذه النسخة**.

---

## إعادة التشغيل على staging

شغّل نفس المنطق على PostgreSQL staging (استبدل اتصال DSN):

```sql
SELECT 'branch_stock_negative_current' AS check_name, COUNT(*)::bigint AS cnt
  FROM branch_stock WHERE current_qty < 0
UNION ALL
SELECT 'branch_stock_negative_reserved', COUNT(*)::bigint
  FROM branch_stock WHERE reserved_qty < 0
UNION ALL
SELECT 'branch_stock_negative_transit', COUNT(*)::bigint
  FROM branch_stock WHERE in_transit_qty < 0
UNION ALL
SELECT 'warehouse_stock_negative_current', COUNT(*)::bigint
  FROM warehouse_stock WHERE current_qty < 0
UNION ALL
SELECT 'warehouse_stock_negative_reserved', COUNT(*)::bigint
  FROM warehouse_stock WHERE reserved_qty < 0
UNION ALL
SELECT 'items_bad_min_qty', COUNT(*)::bigint
  FROM items WHERE min_qty < 0
UNION ALL
SELECT 'items_max_lt_min_qty', COUNT(*)::bigint
  FROM items WHERE max_qty < min_qty;
```

---

## استعلامات UPDATE مقترحة (لا تُنفَّذ تلقائيًا)

> **تحذير:** لا تشغّلها إلا بعد مراجعة؛ أضف تسجيلات `stock_transactions` حسب سياسة الـ ledger عندكم.

### 1) تصفير كميات سالبة في `branch_stock`

```sql
-- معاينة الصفوف المتأثرة
SELECT id, branch_id, item_id, current_qty, reserved_qty, in_transit_qty
FROM branch_stock
WHERE current_qty < 0 OR reserved_qty < 0 OR in_transit_qty < 0;

-- تصحيح آمن للأرضية عند الصفر (بدون ledger — للمراجعة فقط)
UPDATE branch_stock SET current_qty = 0 WHERE current_qty < 0;
UPDATE branch_stock SET reserved_qty = 0 WHERE reserved_qty < 0;
UPDATE branch_stock SET in_transit_qty = 0 WHERE in_transit_qty < 0;
```

### 2) تصفير سالبة في `warehouse_stock`

```sql
SELECT id, warehouse_id, item_id, current_qty, reserved_qty
FROM warehouse_stock
WHERE current_qty < 0 OR reserved_qty < 0;

UPDATE warehouse_stock SET current_qty = 0 WHERE current_qty < 0;
UPDATE warehouse_stock SET reserved_qty = 0 WHERE reserved_qty < 0;
```

### 3) إصلاح `items` عند `max_qty < min_qty` أو `min_qty < 0`

```sql
SELECT id, item_code, min_qty, max_qty FROM items WHERE min_qty < 0 OR max_qty < min_qty;

UPDATE items SET min_qty = 0 WHERE min_qty < 0;
-- مثال: ضبط max ليكون على الأقل min
UPDATE items SET max_qty = min_qty WHERE max_qty < min_qty;
```

### 4) اقتراح تسجيل ledger (مبدئي — يتطلب أعمدة/Enums عندكم)

لكل صف تم تعديل `current_qty` في `branch_stock`، يمكن إدراج `stock_transactions` بنوع **`adjustment_in`** أو **`adjustment_out`** حسب إشارة الفرق، مع `notes` توضح تصحيح ما قبل migration `e5f6a7b8c9d0`. **نفّذ عبر خدمة التطبيق أو سكربت يحترم القيود والـ tenant_id إن وُجد.**

---

## قرار خارج النطاق

- لم يُنفَّذ أي `UPDATE` فعلي على قاعدة البيانات.
- لم يُتصل بـ PostgreSQL staging (البيئة هنا بدون `psycopg2` لـ `.env.staging`).
