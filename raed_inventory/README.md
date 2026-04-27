# Raed Branch Daily Inventory & Auto Replenishment System
## نظام الجرد اليومي والتوريد التلقائي لفروع رائد

---

## 📋 نظرة عامة

نظام متكامل لإدارة الجرد اليومي وطلبيات التوريد التلقائي لفروع شركة رائد للأغذية.

### المميزات الرئيسية
- ✅ جرد يومي للفروع مع منطق آلي للفروقات
- ✅ توليد طلبيات تلقائية بعد اعتماد الجرد
- ✅ مسار عمل كامل: فرع ← مستودع ← تجهيز ← صرف ← استلام
- ✅ لوحات تحكم للفرع، المستودع، والعمليات
- ✅ RBAC كامل (7 أدوار مختلفة)
- ✅ تنبيهات المخزون (نافد / تحت الحد / نقطة الطلب)
- ✅ واجهة عربية RTL

---

## 🚀 التشغيل السريع

### الطريقة 1: Docker (موصى بها)

```bash
# 1. تأكد من تثبيت Docker وDocker Compose
docker --version
docker compose version

# 2. انتقل لمجلد المشروع
cd raed_inventory

# 3. شغّل كل شيء
docker compose up -d

# 4. انتظر حتى يكتمل الـ seed (30 ثانية تقريباً)
docker compose logs backend -f

# 5. افتح المتصفح
# Frontend:  http://localhost:3000
# API Docs:  http://localhost:8000/api/docs
```

---

### الطريقة 2: التشغيل المحلي

#### متطلبات أساسية
- Python 3.11+
- Node.js 20+
- PostgreSQL 14+

#### Backend

```bash
# 1. إنشاء قاعدة بيانات PostgreSQL
psql -U postgres
CREATE DATABASE raed_inventory;
CREATE USER raed_user WITH PASSWORD 'raed_pass';
GRANT ALL PRIVILEGES ON DATABASE raed_inventory TO raed_user;
\q

# 2. إعداد البيئة
cd backend
cp .env.example .env
# عدّل DATABASE_URL إذا لزم الأمر

# 3. تثبيت المتطلبات
pip install -r requirements.txt

# 4. تشغيل الـ Seed (يُنشئ الجداول + البيانات الأولية)
python seed.py

# 5. تشغيل الـ Backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# يعمل على: http://localhost:3000
```

---

## 🔑 بيانات الدخول التجريبية

| الدور | اسم المستخدم | كلمة المرور |
|-------|-------------|-------------|
| مدير النظام | `admin` | `Admin@2025` |
| مدير فرع (الرياض-العليا) | `branch.mgr1` | `Raed@2025` |
| موظف فرع (الرياض-العليا) | `branch.user1` | `Raed@2025` |
| مدير فرع (الدمام) | `branch.mgr2` | `Raed@2025` |
| موظف فرع (الدمام) | `branch.user2` | `Raed@2025` |
| مدير مستودع الرياض | `wh.mgr1` | `Raed@2025` |
| موظف مستودع الرياض | `wh.user1` | `Raed@2025` |
| مدير العمليات | `ops.mgr` | `Raed@2025` |

---

## 🏗️ هيكل المشروع

```
raed_inventory/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings & environment
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # All DB models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API endpoints
│   │   │   ├── auth.py          # JWT auth
│   │   │   ├── users.py         # User management
│   │   │   ├── master.py        # Master data CRUD
│   │   │   ├── inventory.py     # Daily inventory
│   │   │   ├── orders.py        # Replenishment orders
│   │   │   └── dashboard.py     # KPIs & dashboards
│   │   ├── services/
│   │   │   ├── inventory_service.py     # Inventory logic
│   │   │   └── replenishment_service.py # Auto-order engine
│   │   └── core/
│   │       ├── auth.py          # JWT dependencies
│   │       └── security.py      # Password & token utils
│   ├── seed.py                  # Database seeder
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router & app shell
│   │   ├── store/               # Redux store
│   │   ├── services/api.js      # Axios API client
│   │   ├── components/
│   │   │   ├── common/          # Shared UI components
│   │   │   └── layout/          # AppLayout + sidebar
│   │   ├── pages/
│   │   │   ├── auth/            # Login
│   │   │   ├── branch/          # Branch workflows
│   │   │   ├── shared/          # Orders, dashboard
│   │   │   └── admin/           # Admin management
│   │   └── utils/helpers.js     # Formatters & constants
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── README.md
└── DEV_NOTES.md
```

---

## 📡 API Endpoints

| Module | Endpoint | Methods |
|--------|----------|---------|
| Auth | `/api/auth/login` | POST |
| Auth | `/api/auth/me` | GET |
| Users | `/api/users/` | GET, POST |
| Users | `/api/users/{id}` | GET, PUT, DELETE |
| Warehouses | `/api/master/warehouses` | GET, POST, PUT, DELETE |
| Branches | `/api/master/branches` | GET, POST, PUT, DELETE |
| Items | `/api/master/items` | GET, POST, PUT, DELETE |
| Categories | `/api/master/categories` | GET, POST |
| Units | `/api/master/units` | GET, POST |
| Inventory | `/api/inventory/` | GET, POST |
| Inventory | `/api/inventory/{id}/submit` | POST |
| Inventory | `/api/inventory/{id}/approve` | POST |
| Inventory | `/api/inventory/{id}/reject` | POST |
| Orders | `/api/orders/` | GET |
| Orders | `/api/orders/{id}/branch-review` | POST |
| Orders | `/api/orders/{id}/submit-to-warehouse` | POST |
| Orders | `/api/orders/{id}/warehouse-review` | POST |
| Orders | `/api/orders/{id}/approve` | POST |
| Orders | `/api/orders/{id}/start-picking` | POST |
| Orders | `/api/orders/{id}/dispatch` | POST |
| Orders | `/api/orders/{id}/receive` | POST |
| Dashboard | `/api/dashboard/branch/{id}` | GET |
| Dashboard | `/api/dashboard/warehouse/{id}` | GET |
| Dashboard | `/api/dashboard/operations` | GET |

**Swagger UI:** http://localhost:8000/api/docs

---

## 🔄 سير العمل اليومي

```
1. موظف الفرع     → يدخل الجرد اليومي (draft)
2. موظف الفرع     → يرسل الجرد للاعتماد (submitted)
3. مدير الفرع     → يعتمد الجرد (approved)
                    ↓ تلقائي: يُنشأ طلب توريد
4. موظف الفرع     → يراجع الطلبية المقترحة
5. مدير الفرع     → يرسل الطلبية للمستودع
6. موظف المستودع  → يراجع الكميات
7. مدير المستودع  → يعتمد الطلبية
8. موظف المستودع  → يبدأ التجهيز → يصرف
9. موظف الفرع     → يؤكد الاستلام ويسجل الفروقات
10. النظام         → يغلق الطلبية تلقائياً
```

---

## 🗃️ قاعدة البيانات

**22 جدول رئيسي:**
`users`, `roles`, `permissions`, `user_roles`, `role_permissions`,
`branches`, `warehouses`, `items`, `item_categories`, `units`,
`branch_stock`, `warehouse_stock`,
`daily_inventory`, `daily_inventory_lines`,
`replenishment_orders`, `replenishment_order_lines`,
`stock_transactions`,
`inventory_variance_reasons`, `receiving_variance_reasons`,
`system_settings`, `audit_logs`

---

## ⚙️ Environment Variables

```env
DATABASE_URL=postgresql://raed_user:raed_pass@localhost:5432/raed_inventory
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 🔮 التطويرات المستقبلية

- [ ] Push notifications (WebSocket)
- [ ] Mobile app (React Native)
- [ ] Barcode scanner integration
- [ ] Advanced analytics & forecasting
- [ ] Multi-language support (EN/AR)
- [ ] Export to Excel/PDF
- [ ] Cloud deployment (Railway/Render)

---

*Raed Food Corporation © 2025 — Built with FastAPI + React + PostgreSQL*
