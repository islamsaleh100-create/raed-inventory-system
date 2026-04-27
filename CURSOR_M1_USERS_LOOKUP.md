# Cursor Handoff — M1: dropdown فاضي في `المقيّم` و `المراجع`

## الشكوى
- صفحة **تقييم تدريبي جديد** `/training/new`: خانة **المقيّم (مدير المنطقة)** dropdown فاضي، مش بيعطي خيار.
- صفحة **زيارة جودة جديدة** `/quality/new`: خانة **المراجع** نفس المشكلة.
- المستخدم عايز يقدر ياختار من قائمة بأسماء الموظفين اللي مسجّلين في النظام (مش يكتب نص حر — الـ FK لازم يفضل موجود).

## الـ root cause (أكيد)
الـ endpoint `GET /api/v1/users/` محجوز على `admin` و `super_admin` فقط:

```python
# backend/app/routers/users.py:111
current_user: User = Depends(require_roles("admin", "super_admin"))
```

لما `area_manager` أو `branch_manager` أو `quality_visitor` يفتح صفحة تقييم أو زيارة، الـ frontend ببعت `GET /users/?page_size=500` والـ backend ترجع 403. الـ frontend ببلعها silently:

```jsx
// frontend/src/pages/training/TrainingPages.jsx:300
usersApi.list({ page_size: 500 }).catch(() => ({ data: { items: [] } }))
```

→ `users = []` → الـ `<select>` كله options فاضي → dropdown ظاهر لكن مافيهش أي اختيار.

نفس المشكلة في `quality/QualityPages.jsx` عند التعبئة الأولية.

## الحل — 3 خطوات

### خطوة 1 (backend) — ضيف endpoint خفيف للـ lookup

ملف: `backend/app/routers/users.py`

ضيف route جديد قبل route `"/{user_id}"` (وقبل `@router.get("/")` أحسن):

```python
@router.get("/lookup")
def users_lookup(
    search: Optional[str] = None,
    role: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        "admin", "super_admin",
        "area_manager", "branch_manager",
        "quality_visitor", "quality_manager",
        "trainer", "operations_manager", "warehouse_manager",
    )),
):
    """
    Lightweight user lookup for form dropdowns (trainer/visitor/assessor pickers).
    Returns only id, full_name/username, and role names — no PII like email/phone.
    Accessible to all roles that need to pick users when creating visits/assessments.
    """
    q = db.query(User).options(
        joinedload(User.user_roles).joinedload(UserRole.role)
    ).filter(User.is_deleted == False)

    if active_only:
        q = q.filter(User.status == "active")

    if search:
        q = q.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%"))
        )

    if role:
        q = q.join(UserRole, UserRole.user_id == User.id) \
             .join(Role, Role.id == UserRole.role_id) \
             .filter(Role.name == role)

    users = q.order_by(User.full_name.asc().nullslast(), User.username.asc()).limit(500).all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "roles": [ur.role.name.value for ur in u.user_roles],
            "branch_id": u.branch_id,
        }
        for u in users
    ]
```

**ملاحظات**:
- مفيش paging — 500 كافية (كل شركة عندها ~50-80 مستخدم).
- ما بيرجّعش email/phone/status/created_at — فلا PII لأدوار مش admin.
- `active_only=True` by default — الموظفين المعطّلين ماينفعش يتقيّموا.
- فلتر `role` اختياري: الـ frontend ممكن يجيب `area_manager` بس في خانة المقيّم.

### خطوة 2 (frontend) — ضيف `usersApi.lookup` واستخدمه في الفورمين

ملف: `frontend/src/services/api.js`

في object `usersApi`:

```js
export const usersApi = {
  list: (params) => api.get('/users/', { params }),
  // M1: lightweight lookup for form dropdowns (works for non-admin roles too)
  lookup: (params) => api.get('/users/lookup', { params }),
  // ...
}
```

ملف: `frontend/src/pages/training/TrainingPages.jsx`

في `TrainingAssessmentFormPage` (حوالي line 298-313)، غيّر:

```jsx
// قديم
usersApi.list({ page_size: 500 }).catch(() => ({ data: { items: [] } })),

// جديد
usersApi.lookup().catch(() => ({ data: [] })),
```

وفي الـ handler للـ response (حوالي line 306):

```jsx
// قديم
const uList = Array.isArray(usersRes.data) ? usersRes.data : (usersRes.data?.items || [])

// جديد — الـ lookup بيرجع list مباشرة
const uList = Array.isArray(usersRes.data) ? usersRes.data : []
```

ملف: `frontend/src/pages/quality/QualityPages.jsx`

في `QualityVisitFormPage` — شاور على الـ load effect (حوالي line 450-470). نفس التغيير: بدل `usersApi.list({ page_size: 500 })` استخدم `usersApi.lookup()`.

**لازم تتحقق**: بعد التبديل، لما `currentUser` auto-fill بتاعه يتطبق (line 470)، لازم `users` يكون فيه الـ currentUser — لو مش موجود، ضيفه يدوياً كـ fallback في قائمة الخيارات:

```jsx
{users.map(u => (
  <option key={u.id} value={u.id}>
    {u.full_name || u.username || `#${u.id}`}
  </option>
))}
{/* fallback لو currentUser مش في قائمة lookup */}
{currentUser?.id && !users.find(u => u.id === currentUser.id) && (
  <option value={currentUser.id}>
    {currentUser.full_name || currentUser.username || `#${currentUser.id}`} (أنت)
  </option>
)}
```

### خطوة 3 — اختبار

```powershell
cd c:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path

# 1) API يشتغل لـ admin
python -c "
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
client = TestClient(app)
token = create_access_token(subject='1')  # admin
r = client.get('/api/v1/users/lookup', headers={'Authorization': f'Bearer {token}'})
print('admin status:', r.status_code, '| count:', len(r.json()) if r.status_code==200 else r.text[:200])
"
```

ولو فيه area_manager user في DB (مثلاً id=5):
```powershell
python -c "
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
client = TestClient(app)
token = create_access_token(subject='5')  # area_manager
r = client.get('/api/v1/users/lookup', headers={'Authorization': f'Bearer {token}'})
print('area_manager status:', r.status_code, '| count:', len(r.json()) if r.status_code==200 else r.text[:200])
"
```

**المتوقع**: الاتنين يرجعوا 200 وقائمة بالمستخدمين (≥2).

### اختبار المتصفح
1. Hard refresh (`Ctrl+Shift+R`) على `http://localhost:3000/training/new`
2. لازم تلاقي dropdown الموظف والمقيّم فيهم كل المستخدمين
3. نفس الشيء على `/quality/new` — خانة المراجع فيها كل المستخدمين

## الرد
- ✅ + screenshot للـ dropdowns بعد الإصلاح
- ❌ + أي traceback من الـ TestClient أو uvicorn

## ملاحظة أمان
الـ endpoint ده بيرجع أسماء موظفين لكل من له أي دور نظامي. ده مقبول في نطاق شركة داخلية — لو احتجت تقييده أكتر (مثلاً area_manager يشوف بس موظفين منطقته) ممكن نضيف فلتر `branch_id` لاحقاً لكن ده scope مختلف.
