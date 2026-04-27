# LAN PostgreSQL Demo Runbook

## الهدف

تشغيل نسخة ديمو تعتمد على PostgreSQL بدل SQLite لاستخدامها في:

- LAN trial
- supply chain demo
- staging-like local verification

## المتطلبات

- Docker Desktop
- المنافذ:
  - `5432`
  - `8010`

## ملفات التشغيل

- `docker-compose.lan.yml`
- `.env.postgres.local`

## التشغيل

من داخل `backend/`:

```bash
docker compose -f docker-compose.lan.yml up --build
```

ما الذي سيحدث:

1. تشغيل PostgreSQL
2. انتظار readiness
3. تنفيذ `alembic upgrade head`
4. تنفيذ `seed_supply_chain_demo.py`
5. تشغيل FastAPI على المنفذ `8010`

## URLs

- API: `http://localhost:8010`
- Health: `http://localhost:8010/health`
- Docs: `http://localhost:8010/api/docs`

## حسابات الديمو الأساسية

كلمة المرور:

`Raed@2025`

أمثلة:

- `super.admin`
- `branch_ronaldos`
- `area_riyadh`
- `pizza_manager`
- `warehouse_user`
- `delivery_user`

## التحقق السريع

1. افتح `http://localhost:8010/health`
2. سجّل الدخول
3. جرّب مسار:

`Branch Request -> Approve -> Kitchen -> Warehouse -> Delivery`

## الإيقاف

```bash
docker compose -f docker-compose.lan.yml down
```

## الإيقاف مع حذف البيانات

```bash
docker compose -f docker-compose.lan.yml down -v
```

استخدم هذا فقط إذا أردت إعادة بناء الديمو من الصفر.
