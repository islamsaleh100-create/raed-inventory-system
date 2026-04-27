# Raed Inventory System
## Full Production Audit v2 — Readable Report

**Date:** 2026-04-25

## الملخص التنفيذي

النظام تحسن عن المراجعة السابقة، وارتفعت حالته من `52/100` إلى `58/100`.

هذا يعني أن هناك إصلاحات حقيقية تمت، خصوصًا في:

- `Supply Chain V1`
- `Auto Split`
- `reserved_qty`
- استيراد `Supply Item Master`
- جزء من الصلاحيات والـ route guards

لكن رغم ذلك، النظام **ما زال غير جاهز للإنتاج الفعلي**.

الحالة الحالية أقرب إلى:

- Demo ready
- LAN trial ready
- Internal testing ready

وليست بعد:

- Production ready
- High-concurrency ready
- Long-term operationally hardened

## ما الذي تم إصلاحه فعلًا

هناك نقاط مهمة تحسنت فعلًا مقارنة بالمراجعة السابقة:

1. `Auto Split` بعد اعتماد مدير المنطقة أصبح موجودًا ويعمل.
2. `reserved_qty` أثناء split أصبح يُكتب فعليًا.
3. استيراد ملف الأصناف الرسمي أصبح منظمًا وإلى حد كبير صحيح.
4. صلاحيات `Area Manager` في supply chain أصبحت مبنية على `City + Brand`.
5. الواجهة لم تعد مفتوحة بالكامل؛ يوجد `RouteRoleGuard`.
6. بيئة الديمو وseed users أصبحت أوضح وأكثر قابلية للتشغيل.

## ما الذي ما زال يمنع الإنتاج

### 1. قاعدة البيانات ما زالت SQLite

هذه هي أكبر مشكلة حالية.

حتى لو الكود يحتوي على `lock_row()` وقيود إضافية، فإن SQLite لا تعطي نفس حماية التزامن المطلوبة في بيئة تشغيل حقيقية.

النتيجة المحتملة:

- over-issue من المخزون
- race conditions
- تعارض في الاعتمادات
- أخطاء `500` بدل conflict واضح

الخلاصة:

**طالما النظام يعمل على SQLite، فلا يجب اعتباره Production-ready.**

### 2. صلاحية `admin` أوسع من اللازم

حاليًا هناك bypass واسع في `require_roles()`، وهذا يعني أن مستخدمًا بدور `admin` قد يصل إلى مسارات ووظائف كان المفترض أن تُربط بصلاحيات أكثر تحديدًا.

هذا خطر لأن:

- بعض القيود أصبحت تعتمد على service-level checks فقط
- أي endpoint جديد قد ينكشف بسهولة إذا نُسي فيه التحقق الإضافي

### 3. التوصيل لا يدعم Partial Delivery فعليًا

النظام حاليًا يسجل التسليم كأنه كامل عند تنفيذ deliver، حتى لو الواقع كان تسليمًا جزئيًا.

هذا يؤدي إلى:

- زيادة غير صحيحة في `BranchStock`
- إخفاء مشاكل نقص أو تلف أثناء التوصيل
- تقارير inaccurate

### 4. طلب خامات المطبخ غير مكتمل

هناك `KitchenMaterialRequest` ككيان، لكن المسار ليس كاملاً:

- لا يوجد approve/issue/reject workflow حقيقي
- لا يتحول الطلب إلى warehouse fulfillment فعلي
- المطبخ قد يتوقف في `WAITING_FOR_MATERIALS`

### 5. Procurement ما زال Skeleton

الموجود حاليًا ليس نظام شراء متكاملًا، بل مجرد بداية:

- `Supplier`
- `PurchaseRequest`

لكن لا يوجد:

- Purchase Order كامل
- Receipt / GRN
- Invoice flow
- replenishment حقيقي للمستودع

## حالة Supply Chain V1 الآن

إذا حصرنا الحديث في مسار `Supply Chain V1` فقط، فالوضع جيد نسبيًا.

الموجود ويعمل:

- Branch Request
- Area Approval
- Auto Split
- Production Orders
- Warehouse Lines
- Delivery Orders

هذا يعني أن المسار:

`Branch -> Approve -> Split -> Production -> Warehouse -> Delivery`

**موجود ويشتغل**

لكن يجب التفريق بين:

- "يعمل في الديمو"
- و"آمن وجاهز للإنتاج"

المسار الحالي:

- **قابل للعرض والتجربة**
- لكنه **ليس hardened enough** لتشغيل عميل حقيقي تحت ضغط

## حالة Item Master والأصناف

دمج ملف `classified_supply_items.xlsx` خطوة قوية ومهمة جدًا.

والنظام الآن يطبق قواعد جيدة، منها:

- `NOT_REQUESTABLE` لا يظهر في طلبات الفروع
- `RAW` لا يظهر للفروع
- `KITCHEN` items مرتبطة بـ `kitchen_section_id`
- `WAREHOUSE` items تذهب للمستودع
- `BOTH` تعتمد على `default_source`

لكن توجد نقطة ما زالت مهمة:

ليست كل الكيانات downstream تحفظ snapshots كاملة، لذلك إعادة تسمية صنف أو تغيير تصنيفه لاحقًا قد تؤثر على قراءة التاريخ في بعض الجداول.

## حالة الواجهة

الواجهة تحسنت، وبها ربط حقيقي لعدد جيد من الصفحات، خصوصًا صفحات:

- supply chain
- daily inventory
- daily orders
- branch stock

لكن ما زالت هناك ملاحظات:

- بعض الصفحات legacy تحتاج tightening
- بعض الشاشات صالحة للديمو أكثر من كونها جاهزة لبيئة إنتاج
- جزء من منطق admin bypass ما زال موجودًا أيضًا في الواجهة

## حالة الملفات والرفع

التخزين الحالي على local disk داخل التطبيق ليس مناسبًا للإنتاج، خصوصًا على منصات مثل Railway.

المخاطر:

- ضياع الصور والمرفقات بعد restart أو redeploy
- عدم وجود persistent object storage واضح

هذا يعني أن:

**نظام الرفع الحالي جيد للديمو، لكنه غير مناسب للإنتاج.**

## التقييم النهائي

الحالة الحالية يمكن تلخيصها كالتالي:

- **Demo Ready:** نعم
- **LAN Trial Ready:** نعم، بحذر
- **Production Ready:** لا

بصياغة أبسط:

النظام الآن **قوي كنسخة ديمو وتشغيل داخلي**، لكنه **غير جاهز بعد لعميل فعلي أو تشغيل production مستقر**.

## أهم 5 أولويات من الآن

إذا أردنا دفع النظام باتجاه نسخة قابلة للنشر، فهذه أهم 5 أولويات:

1. نقل قاعدة البيانات إلى `PostgreSQL`
2. تضييق `admin bypass` في backend والواجهة
3. دعم `Partial Delivery` بشكل صحيح
4. إكمال `Kitchen Material Request` workflow
5. نقل التخزين من local disk إلى persistent storage مناسب

## التوصية

لا أنصح بفتح Features جديدة الآن إذا كان الهدف هو الوصول إلى نسخة قابلة للنشر.

الأولوية الصحيحة الآن هي:

- stabilization
- database hardening
- permission hardening
- delivery correctness
- storage readiness

## الخلاصة المختصرة جدًا

النظام:

- **ليس فاشلًا**
- **ليس مكتملًا للإنتاج**
- **لكنه أصبح قويًا بما يكفي للديمو والتجربة الداخلية**

والخطوة الصحيحة التالية ليست Feature جديدة، بل:

**Phase تثبيت وإغلاق مخاطر الإنتاج**
