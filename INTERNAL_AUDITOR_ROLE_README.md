# Internal Auditor Role

حساب المراجع الداخلي في النسخة الحالية:

- `username`: `audit.officer`
- `password`: `Raed@2025`
- `email`: `audit@raed.com`
- `role`: `internal_auditor`

## الهدف

دور `internal_auditor` مخصص للمراجعة والرقابة فقط:

- يرى بيانات التشغيل عبر النظام
- يراجع السجل والتقارير والملاحظات
- يضيف `audit findings`
- لا ينفذ أي تعديل تشغيلي على الطلبات أو الإنتاج أو المستودع أو التسليم

## الصفحات الأساسية

- `/audit/dashboard`
- `/audit/findings`
- `/audit/trail`

كما يمكنه الدخول قراءةً فقط إلى صفحات مثل:

- `/supply-chain/control`
- `/supply-chain/branch-requests`
- `/supply-chain/approvals`
- `/supply-chain/kitchen`
- `/supply-chain/warehouse`
- `/supply-chain/delivery`
- `/quality`
- `/training`
- `/documents`

## قواعد الصلاحيات

- كل عمليات `GET` المسموح بها لهذا الدور متاحة للقراءة
- كل عمليات `POST / PATCH / PUT / DELETE` التشغيلية محجوبة
- الاستثناء الوحيد للكتابة:
  - `/api/v1/audit/findings`
  - `/api/v1/audit/findings/{id}`
  - `/api/v1/audit/findings/{id}/acknowledge` للمستخدمين الإداريين/المديرين المعنيين

## الحماية

الحماية مطبقة بطبقتين:

1. الواجهة تخفي أزرار التنفيذ عن `internal_auditor`
2. الـ backend middleware يمنع أي كتابة تشغيلية ويعيد `403`

## التحقق المنفذ

- Backend tests:
  - `C:\raed_inventory_system\raed_inventory\backend\tests\test_internal_auditor.py`
- Browser tests:
  - `C:\raed_inventory_system\raed_inventory\frontend\tests\internal-auditor.spec.ts`

تم التحقق من:

- login والانتقال إلى `/audit/dashboard`
- عرض صفحات المراجعة
- إنشاء finding من الواجهة
- حظر الكتابة التشغيلية
- إخفاء أزرار التنفيذ في:
  - approvals
  - warehouse
  - delivery

## ملاحظات النسخة الحالية

- هذه نسخة `MVP` قوية للدور
- بعض الصفحات القرائية خارج سلسلة الإمداد قد تحتاج لاحقًا تلميع UI إضافي إذا أردتم توحيد رسائل `read-only` في كل النظام
- الـ exports الحالية تعتمد على CSV في صفحات audit
