# Test failure triage (pytest)

**Source:** `pytest --tb=line -q` on 2026-04-17, Windows, `ENV_FILE=.env.test` (pytest defaults).  
**Totals:** `FAILED` **105** | `ERROR` **82** | **187** outcome lines | **8 passed** (includes `test_area_manager_inter_branch_transfer`).

**تفصيل الـ 82 `ERROR` (حسب ملف الاختبار):** `test_epic10_13_unittest.py` **22** + `test_epic14_15_unittest.py` **22** + `test_epic4_9_unittest.py` **38** = **82**.

> ملاحظة: المجموعات أدناه تفسّر **السبب الجذري**؛ بعض الاختبارات قد يسقط لأكثر من سبب بعد إصلاح الطبقة الأولى.

---

## المجموعة A — DB setup / schema missing

**العدد (تقديري):** **22** اختبارًا (`ERROR` في `test_epic14_15_unittest.py`).

**الوصف:** `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users` أثناء setup (محاولة تسجيل دخول قبل إنشاء الجداول على الـ engine المستخدم في ذلك الموديول).

**أمثلة ملفات (3):**

- `tests/test_epic14_15_unittest.py`
- (نفس النمط: suite يعتمد على `engine`/`Session` محلي دون `Base.metadata.create_all` متزامن مع `TestClient` من `conftest.py`)

**يُحَل بـ:** إصلاح conftest / توحيد الـ engine مع `tests/conftest.py` أو إعادة توليد DB في الـ fixtures (`create_all` قبل الـ seed).

---

## المجموعة B — API path / response schema drift

**العدد (تقديري):** **~105** `FAILED` + **~60** من أصل **82** `ERROR` (setup) حيث الرسالة `Login failed` / `404 Not Found` على `/api/auth/login` أو مسارات قديمة).

**الوصف:**

- `AssertionError: Login failed ... 404` في `test_epic10_13_unittest.py` و`test_epic4_9_unittest.py` (مسار تسجيل دخول قديم vs `/api/v1/auth/login`).
- `test_epic2_master_data_unittest.py` / `test_epic3_inventory_workflow_unittest.py`: فشل جماعي يتوافق مع توقعات `/api/v1/...` و`KeyError: 'access_token'` عند استجابة غير متوقعة.
- `test_security_and_workflow_fixes*.py`: كثير من `assert 404 == 200` أو `404 == 403` — غالبًا لأن الخطوة السابقة (login أو مسار) لم تصل للـ API الحقيقي.

**أمثلة ملفات (3):**

- `tests/test_epic2_master_data_unittest.py`
- `tests/test_epic3_inventory_workflow_unittest.py`
- `tests/test_epic10_13_unittest.py`

**يُحَل بـ:** تحديث سكيمات الاختبار (مسارات، payloads، مفاتيح JSON) لتطابق الـ API الحالي.

---

## المجموعة C — Fixture / setup errors (pytest `ERROR`)

**العدد:** **82** (كلها `ERROR at setup` في التقرير الملخّص).

**الوصف:** لا تصل الاختبارات إلى الـ assertion بسبب فشل في `setUp`/`fixture` (إما **A** أو **B** أعلاه). حوالي **22** منها `no such table`، وحوالي **60** منها فشل تسجيل الدخول **404**.

**أمثلة ملفات (3):**

- `tests/test_epic10_13_unittest.py`
- `tests/test_epic4_9_unittest.py`
- `tests/test_epic14_15_unittest.py`

**يُحَل بـ:** إصلاح conftest + تحديث مسارات الـ login في الـ mixins المشتركة بين الـ unittest suites.

---

## المجموعة D — Logic / business assertion drift

**العدد (تقديري):** **0–قليل** بعد استبعاد سلسلة الـ 404؛ ظهور `AppError` أو منطق تلقّي مزدوج نادر في اللوج الحالي.

**أمثلة ملفات (3) (مرشّحة لمراجعة منطقية بعد إصلاح B):**

- `tests/test_security_and_workflow_fixes.py` — يظهر في اللوج `AppError: Inventory already approved for this date` (قد يكون ترتيب بيانات الاختبار وليس انحراف منتج).
- `tests/test_security_and_workflow_fixes_unittest.py` — سيناريوهات idempotency / dispatch بعد نجاح الـ HTTP.
- `tests/test_epic1_foundation_unittest.py` — فشلان فقط؛ يحتاجان تمييز 404/إعداد بيئة vs توقعات meta/docs.

**يُحَل بـ:** مراجعة منطقية بعد أن تصبح استجابات الـ API **200/403/409** كما يتوقع الاختبار.

---

## أوامر إعادة التوليد (لـ Codex / محليًا)

```bash
cd raed_inventory/backend
pytest --tb=line -q 2>&1 | grep -E "^FAILED|^ERROR" > /tmp/test_failures.txt
wc -l /tmp/test_failures.txt
head -50 /tmp/test_failures.txt
```

**ملف خام مُولَّد في هذه الجلسة:** `pytest_fail_lines.txt` (نفس محتوى الـ pytest تقريبًا).
