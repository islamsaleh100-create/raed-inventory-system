# Cursor Handoff — M1-verify: أعد تشغيل uvicorn وتحقق إن dropdown اتعبّى

## السياق
- M1 كود تم تطبيقه بنجاح: endpoint `/users/lookup` متسجّل في `users.py` قبل `/{user_id}`، والـ frontend بيناديه في `TrainingPages.jsx` و `QualityPages.jsx`.
- TestClient عندك رجع 200 لأدمن وbranch_manager.
- **لكن** لمّا فحصنا من المتصفح، الـ request `GET /api/v1/users/lookup` رجع **422** بدل 200.
- السبب الأرجح: الـ uvicorn الشغّال على 8010 لسه بيسيرف الكود القديم (قبل تعديلك) — فـ `/lookup` مش متسجّل عنده → الـ request بتطابق `/{user_id}` → `"lookup"` بتفشل في int validation → **422**.
- تأكيد: `--reload` ممكن ما التقطش التعديل لأن الملف اتحفظ قبل ما uvicorn يبدأ، أو لأن الـ reload watcher فشل، أو لأن uvicorn مش شغّال بـ `--reload` أصلاً.

## المطلوب

### 1) أوقف الـ uvicorn القديم

```powershell
# سد أي process على port 8010
Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue |
    Select-Object -First 1 |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# تأكد إن 8010 فاضي الآن
Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue
```

المفروض الأمر التاني يطبع لا شيء (أو "no matching listeners").

### 2) شغّل uvicorn من جديد من مجلد الـ backend

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path
uvicorn app.main:app --reload --port 8010
```

لازم تظهر:
```
INFO:     Uvicorn running on http://0.0.0.0:8010
INFO:     Application startup complete.
```

لو فيه traceback (مثلاً `ImportError` أو `SyntaxError`) ابعتهولي مباشرةً.

### 3) اختبر من TestClient فوراً — جوا مسار uvicorn

من نافذة PowerShell **تانية** (خلّي uvicorn شغّال):

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path

# استخدم requests ضد uvicorn الشغّال بدل TestClient — ده يتأكد إن uvicorn نفسه بيستجيب صح
python -c "
import requests
from app.core.security import create_access_token
token = create_access_token({'sub': '1'})
r = requests.get('http://localhost:8010/api/v1/users/lookup', headers={'Authorization': f'Bearer {token}'}, timeout=5)
print('status:', r.status_code)
print('count:', len(r.json()) if r.status_code == 200 else r.text[:400])
"
```

**المتوقع**: `status: 200` وcount: رقم ≥ 1.

لو طلع 422 من uvicorn الجديد، الـ route لسه مش متسجّل صح. شوف الـ uvicorn output لما يبدأ — ممكن يكون فيه warning عن route collision.

### 4) تحقق من المتصفح
في المتصفح على `http://localhost:3000/training/new`:
1. اعمل hard refresh: `Ctrl + Shift + R`
2. افتح DevTools → Network tab → فلتر `users/lookup`
3. لازم تلاقي الـ request رجع **200** وبيحمّل list من 8 مستخدمين
4. في الـ page، dropdown الـ "المقيّم (مدير المنطقة)" لازم يكون فيه أسماء

نفس الكلام على `/quality/new` — dropdown "المراجع" لازم يتعبّى.

### 5) الرد
- ✅ + الـ status من خطوة 3 + عدد المستخدمين الظاهرين في الـ dropdown
- ❌ + output uvicorn startup + الـ response body من 422 (لو لسه بيحصل)

## ملاحظة
بعد ما يشتغل، لو مضى وقت طويل ولقيت uvicorn مش بيلتقط تعديلات Python بسهولة، اعتبر إن `--reload` بتاعك مش بيراقب كل الـ folders — ممكن نضيف `--reload-dir app` صراحةً. لكن متحتاجش ده دلوقتي.
