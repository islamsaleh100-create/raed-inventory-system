# DEV_NOTES — Raed Inventory System
## القرارات الهندسية والملاحظات التقنية

---

## 1. اختيار التقنيات

### Backend: FastAPI
- أسرع من Flask/Django للـ APIs
- Built-in OpenAPI docs
- Type hints + Pydantic = validation تلقائي
- Async-ready للمستقبل

### Database: PostgreSQL + SQLAlchemy
- لم نستخدم Alembic migrations في هذه النسخة — الجداول تُنشأ عبر `Base.metadata.create_all()`
- **للإنتاج:** يُوصى بإضافة Alembic لإدارة migrations بشكل صحيح:
  ```bash
  alembic init migrations
  alembic revision --autogenerate -m "initial"
  alembic upgrade head
  ```

### Frontend: React + Vite + Tailwind
- Vite بدلاً من CRA: أسرع بكثير في التطوير
- Tailwind: utility-first = تصميم سريع ومتسق
- Redux Toolkit: state management للـ auth فقط — باقي الـ state محلي (useState)

---

## 2. قرارات Architecture

### Seed بدلاً من Migrations
في هذه النسخة الأولى، `seed.py` يقوم بإنشاء الجداول والبيانات معاً لسهولة التشغيل.
في بيئة إنتاج حقيقية، يجب الفصل بين:
- Database migrations (Alembic)
- Seed data (seed.py)

### Soft Delete
جميع الجداول الرئيسية (`users`, `items`, `branches`, `warehouses`) تستخدم `is_deleted = True`
بدلاً من الحذف الفعلي للحفاظ على سلامة البيانات والـ audit trail.

### Stock Transactions Ledger
كل تغيير في المخزون يُسجَّل في `stock_transactions`. هذا يمكّن:
- حساب متوسط الاستهلاك
- Audit trail كامل
- إعادة بناء الرصيد في أي وقت

### Auto Replenishment Formula
```
suggested_qty = max(0, target_qty - available_qty)
target_qty   = (avg_daily_usage × days_of_cover) + safety_stock
available_qty = current_stock + in_transit + open_orders - reserved
```
- `days_of_cover` قابل للتعديل من System Settings (افتراضي: 3 أيام)
- يتم الرجوع لـ `min_qty` كـ fallback إذا لم يكن هناك تاريخ استهلاك

---

## 3. الأمان

### JWT
- Token صالح لـ 8 ساعات (`ACCESS_TOKEN_EXPIRE_MINUTES=480`)
- يُخزَّن في `localStorage` (للتبسيط) — في الإنتاج يُفضَّل HttpOnly Cookie

### Passwords
- bcrypt hashing عبر `passlib`
- لا يوجد minimum complexity validation في هذه النسخة (6 chars فقط) — يمكن تشديده

### RBAC
- Role checking يتم في كل endpoint عبر `require_roles()` dependency
- `super_admin` يمر دائماً (bypass)

---

## 4. ما لم يُنفَّذ (Backlog)

| الميزة | السبب | الأولوية |
|--------|--------|----------|
| Alembic Migrations | تعقيد إضافي للنسخة الأولى | عالية |
| Audit Logs API | الجدول موجود، لكن لا يوجد endpoint | متوسطة |
| Push Notifications | يحتاج WebSocket | منخفضة |
| Export Excel/PDF | يحتاج libraries إضافية | متوسطة |
| Barcode Integration | يحتاج hardware | منخفضة |
| Advanced Reports | بيانات كافية متاحة للبناء عليها | متوسطة |
| Unit Tests | بُدئ الهيكل، لم تُكتَّب tests | عالية |
| Rate Limiting | يحتاج slowapi أو nginx | متوسطة |
| Email Notifications | يحتاج SMTP config | منخفضة |

---

## 5. أداء قاعدة البيانات

### Indexes المُضافة
```sql
idx_daily_inv_branch_date  — daily_inventory(branch_id, inventory_date)
idx_order_branch           — replenishment_orders(branch_id)
idx_order_status           — replenishment_orders(status)
idx_stock_tx_item          — stock_transactions(item_id)
idx_stock_tx_date          — stock_transactions(transaction_date)
```

### UniqueConstraints
- `daily_inventory`: فرع واحد + يوم واحد = جرد واحد فقط
- `branch_stock`: فرع + صنف = سجل واحد
- `warehouse_stock`: مستودع + صنف = سجل واحد

---

## 6. متغيرات البيئة للإنتاج

```env
# يجب تغيير هذه القيم في الإنتاج
SECRET_KEY=<random 64 char string>
DATABASE_URL=postgresql://<user>:<strong_password>@<host>:5432/<db>
DEBUG=false
ALLOWED_ORIGINS=https://your-domain.com
```

---

## 7. التوسعة المستقبلية

### Multi-warehouse support
النظام يدعم حالياً ارتباط فرع بمستودع واحد عبر `branches.warehouse_id`.
لدعم مستودعات متعددة لنفس الفرع: يلزم جدول `branch_warehouse_mapping`.

### Real-time notifications
يمكن إضافة WebSocket عبر `fastapi-socketio` أو `broadcaster`:
```python
@app.websocket("/ws/{branch_id}")
async def websocket_endpoint(websocket: WebSocket, branch_id: int):
    await manager.connect(websocket, branch_id)
```

### Mobile App
API جاهز للاستخدام من React Native أو Flutter.
يُوصى بإضافة `/api/mobile/` prefix لـ endpoints مُحسَّنة للموبايل.

---

## 8. تشغيل Tests

```bash
cd backend
pytest tests/ -v
# (Tests بُنيت كـ placeholder — يُوصى بكتابة tests كاملة)
```

---

*Last updated: 2025 — Islam (HR & Payroll Operations Manager, Raed Food Corporation)*
