# PRODUCT_DECISIONS_FINAL.md

**الحالة:** APPROVED — مغلق للتنفيذ
**تاريخ الإغلاق:** 2026-07-13
**المرجع:** مرحلة 1 من خطة LAN Trial — قرارات المنتج النهائية

---

## نطاق هذا الملف

يوثق القرارات المنتجية المغلقة التي تؤثر على Backend Workflow أو Data Model أو Business Rules.
لا يتضمن قرارات تصميم الـUI التفصيلية — تلك تنتمي لملفات PAGE_SPEC_*.

---

## PD-01 — نوعا طلب التوريد

**القرار:** يوجد نوعان فقط للطلب:

| النوع | الوصف |
|---|---|
| `regular` — اعتيادي | الطلب الاعتيادي ضمن دورة التشغيل المعتادة |
| `urgent` — عاجل | طلب يحتاج أولوية مرتفعة في المعالجة والاعتماد |

**القواعد:**

- المطبخ والمستودع **ليسا نوعَي طلب** — هما مسارا تنفيذ ينتج عنهما Auto Split بعد الاعتماد.
- كل تغيير في نوع الطلب بعد الإرسال يُسجل في Audit Trail (من + إلى + سبب + التوقيت).
- قيمة `type` لا تتغير تلقائياً في أي مرحلة.

**OQ-01 (مفتوح — يُحسم قبل PAGE_SPEC لصفحة تفاصيل الطلب):**
هل يستطيع Branch Manager أو Area Manager تغيير نوع الطلب بعد الإرسال (اعتيادي → عاجل)، ومتى ينتهي هذا الحق (قبل الاعتماد فقط؟ في أي وقت؟)؟

---

## PD-02 — العاجل يمر باعتماد مدير المنطقة — لا Auto-approval

**القرار:**

```
طلب اعتيادي:
    ← Branch submits
    → Area Manager approves/rejects
    → Auto Split (Kitchen + Warehouse)
    → التنفيذ بالأولوية الاعتيادية

طلب عاجل:
    ← Branch submits (مع سبب + needed_by إلزاميَّين)
    → Area Manager approves/rejects سريعاً (SLA مخفَّض)
    → Auto Split (Kitchen + Warehouse)
    → التنفيذ بأولوية مرتفعة
```

**القواعد:**

- **لا يوجد Auto-approval** بأي حال — الاعتماد البشري إلزامي.
- `urgent_reason` (نص) + `needed_by` (timestamp) حقلان إلزاميان عند إرسال طلب عاجل.
- تنبيه فوري لمدير المنطقة عند وصول طلب عاجل.
- بعد الاعتماد يحمل الطلب `priority: HIGH` ويظهر في مقدمة قوائم المطبخ والمستودع والتوصيل.
- Admin يستطيع الاعتماد الاستثنائي مع سبب إلزامي مُسجَّل في Audit Trail — لكنه لا يتجاوز الدورة بدون سجل.

**OQ-03 (مفتوح — يُحسم في PAGE_SPEC صفحة الاعتماد):**
اعتماد Admin الاستثنائي: هل هو نفس زر الاعتماد مع modal يطلب السبب، أم زر منفصل بصرياً مختلف اللون والتسمية؟

---

## PD-03 — SLA قابل للإعداد مع تصعيد بدون اعتماد تلقائي

**القرار:**

قيم SLA لمرحلة اعتماد مدير المنطقة (مرحلة LAN Trial):

| المرحلة | اعتيادي | عاجل |
|---|---|---|
| حد الاعتماد | ساعتان | 15 دقيقة |
| بدء المعالجة بعد الاعتماد | حسب دورة التشغيل | 15 دقيقة |
| التصعيد الأول | بعد ساعة | بعد 10 دقائق |
| تصنيف «متأخر» | بعد ساعتين | بعد 15 دقيقة |

**القواعد:**

- جميع قيم SLA مخزَّنة في جدول إعدادات النظام (`system_settings` أو ما يعادله) — **لا Hardcoded**.
- عند تجاوز SLA: يُرفع علَم `overdue` على الطلب + تصعيد إشعار — **دون تغيير الحالة تلقائياً**.
- SLA الإنتاج والتجهيز والتوصيل **لا يُحدَّد الآن** — يُقاس واقعياً خلال LAN Trial ثم يُحدَّد بناءً على البيانات.
- الإعدادات يعدّلها Admin/Super Admin فقط.

**OQ-02 (مفتوح — يُحسم في Phase 3 التصميم التقني):**
آلية التصعيد: إشعار داخل التطبيق فقط، أم Push Notification، أم flag بصري في القائمة، أم مزيج؟

---

## PD-04 — Delivery Claim مع قفل للمندوب

**القرار:**

State Machine لتنفيذ التوصيل:

```
READY
  └── delivery_user يعمل Claim
        → OUT_FOR_DELIVERY  (مقفول على هذا المندوب)
              ├── DELIVERED              (تسليم كامل)
              └── PARTIALLY_DELIVERED   (تسليم جزئي — يبقى المسار مفتوحاً للكميات المتبقية)
```

**القواعد:**

- مندوب واحد فقط يستطيع Claim نفس الأمر — يُطبَّق بـ Database Transaction + Idempotency Check.
- بعد Claim ينتقل الأمر إلى `OUT_FOR_DELIVERY` ولا يستطيع مندوب آخر Claim نفس الأمر.
- `delivery_user` يعمل Claim فقط — **لا يحرر Claim بنفسه** بعد بدء التوصيل.
- يُسجَّل: `claimed_by` + `claimed_at` + `claim_idempotency_key`.

---

## PD-05 — تحرير Claim وإعادة الإسناد

**القرار — صلاحيات التحرير:**

| الدور | تحرير Claim | إعادة الإسناد | ملاحظة |
|---|---|---|---|
| `delivery_user` | ❌ | ❌ | لا يحرر بنفسه بعد البدء |
| `warehouse_manager` | ✅ | ✅ | مع سبب إلزامي |
| `admin` / `super_admin` | ✅ | ✅ | مع سبب إلزامي + Audit Trail |
| `operations_manager` | ❌ | ❌ | متابعة فقط — دور إشرافي غير تنفيذي |

**حالات التعطل:**

| المرحلة | الإجراء |
|---|---|
| قبل الخروج للتوصيل (Claimed لكن لم يُغادر) | تحرير Claim → يعود الأمر إلى `READY` |
| بعد `OUT_FOR_DELIVERY` | إعادة إسناد رسمية مع سبب + تسليم عهدة |
| بعد تسليم جزئي | إعادة إسناد **الكميات المتبقية فقط** — لا يُمسح التنفيذ السابق |

---

## PD-06 — إعادة الإسناد بعد التسليم الجزئي

**القرار:**

- الكميات المُسلَّمة مسبقاً محفوظة ولا تُلغى.
- الإسناد الجديد يتعلق بالكميات المتبقية فقط.
- يُنشأ سجل جديد في `delivery_assignment_history` (بدلاً من الكتابة فوق السجل القديم).
- حالة الأمر تعكس: "مُسلَّم جزئياً — جزء في إعادة توصيل".

---

## PD-07 — Assignment History + Audit Trail إلزاميان

**القرار — جدول `delivery_assignment_history`:**

```sql
delivery_assignment_history
├── id
├── delivery_order_id          FK
├── claimed_by                 FK → User
├── claimed_at
├── released_by                FK → User (nullable)
├── released_at                (nullable)
├── release_reason             (nullable — نص)
├── previous_driver            FK → User (nullable)
├── new_driver                 FK → User (nullable)
├── status_at_reassignment     (Enum)
├── quantities_delivered_before_reassignment  (JSONB أو related table)
├── remaining_quantities       (JSONB أو related table)
└── created_at
```

**القواعد:**

- كل Claim جديد = سجل جديد في هذا الجدول.
- كل تحرير أو إعادة إسناد = سجل جديد (لا تعديل على السجل القديم).
- يظهر جدول التاريخ كاملاً في صفحة تفاصيل أمر التوصيل لـ warehouse_manager وAdmin.
- يُدرج صراحةً في `DATA_MODEL_CHANGES.md` و`API_CONTRACTS_FINAL.md`.

---

## PD-08 — مفتش الجودة يعمل ضمن فروع مسندة

**القرار:**

مفتش الجودة (`quality_inspector`) لا يستطيع إنشاء زيارة لأي فرع عشوائي — يجب أن يكون الفرع مسنداً إليه بشكل نشط.

**جدول `quality_inspector_branch_assignments`:**

```sql
quality_inspector_branch_assignments
├── id
├── inspector_user_id          FK → User
├── branch_id                  FK → Branch
├── active                     Boolean DEFAULT TRUE
├── effective_from             Date
├── effective_to               Date (nullable — null = نشط حالياً)
├── assigned_by                FK → User
├── created_at
└── updated_at
```

**القيود والقواعد:**

- `UNIQUE (inspector_user_id, branch_id) WHERE active = TRUE` — يمنع تكرار الإسناد النشط.
- Backend scope يُطبَّق على: القائمة + التفاصيل + الإنشاء + التعديل + الحذف + المرفقات.
- Admin و Quality Manager يديران الإسنادات.
- الإسناد المنتهي (`active = FALSE`) لا يمنع **قراءة** الزيارات التاريخية التي أنشأها المفتش سابقاً لذلك الفرع.
- يُدرج صراحةً في: `DATA_MODEL_CHANGES.md` + `API_CONTRACTS_FINAL.md` + PAGE_SPEC لإدارة المستخدمين + PAGE_SPEC لإنشاء زيارة الجودة.

---

## ملخص القرارات

| المعرف | القرار | الحالة |
|---|---|---|
| PD-01 | نوعا الطلب: اعتيادي وعاجل | ✅ مغلق |
| PD-02 | العاجل يمر باعتماد المنطقة — لا Auto-approval | ✅ مغلق |
| PD-03 | SLA قابل للإعداد + تصعيد بدون اعتماد تلقائي | ✅ مغلق |
| PD-04 | Delivery Claim مع قفل للمندوب | ✅ مغلق |
| PD-05 | تحرير Claim: warehouse_manager / admin / super_admin فقط | ✅ مغلق |
| PD-06 | إعادة الإسناد بعد التسليم الجزئي تخص الكميات المتبقية | ✅ مغلق |
| PD-07 | delivery_assignment_history + Audit Trail إلزاميان | ✅ مغلق |
| PD-08 | مفتش الجودة ضمن فروع مسندة عبر جدول مستقل | ✅ مغلق |

## الأسئلة المفتوحة (لا تمنع بدء PAGE_SPEC)

| المعرف | السؤال | يُحسم في |
|---|---|---|
| OQ-01 | هل يمكن تغيير نوع الطلب بعد الإرسال وبواسطة من؟ | PAGE_SPEC — تفاصيل الطلب |
| OQ-02 | آلية التصعيد: إشعار داخلي / Push / flag بصري؟ | Phase 3 — التصميم التقني |
| OQ-03 | Admin Exceptional Approval: نفس الزر أم زر مستقل بصرياً؟ | PAGE_SPEC — صفحة الاعتماد |

---

*تاريخ الإغلاق: 2026-07-13*
