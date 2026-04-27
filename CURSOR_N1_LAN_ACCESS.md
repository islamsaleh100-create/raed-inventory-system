# Cursor Handoff — N1: فتح الـ app للابتوبات الشبكة الداخلية (LAN trial)

## الهدف
إسلام عايز كل مدير منطقة يفتح الـ app من لابتوبه وهو على نفس الواي فاي عبر `http://<host-lan-ip>:3000`.

**نطاق الاستخدام**: تجربة LAN فقط — لما يقفل اللابتوب اللي شغال عليه uvicorn/Vite، الخدمة بتنقطع للكل. ده طبيعي ومقبول.

## الوضع الحالي
- uvicorn شغّال على `127.0.0.1:8010` (localhost فقط — مش متاح للشبكة)
- Vite شغّال على `localhost:3000` (default — مش `host:true`)
- `ALLOWED_ORIGINS` في `backend/app/config.py` فيها `localhost:3000` و `localhost:5173` فقط
- Windows Firewall على الأرجح قافل أي inbound

## التغييرات المطلوبة

### 1) Vite — ربط على كل الشبكات

ملف: `raed_inventory/frontend/vite.config.js`

ضيف `host: true` جوا `server`:

```js
server: {
  host: true,                  // ← جديد: يسمح لأي client على الشبكة
  port: devPort,
  proxy: {
    '/api': {
      target: proxyTarget,
      changeOrigin: true,
    },
  },
},
```

### 2) Backend — أضف LAN origins للـ CORS

الحل الأبسط: ضيف `.env` في `raed_inventory/backend/` (أو حدّث الـ `.env` الموجود) بـ ALLOWED_ORIGINS موسّعة.

ابعت اسكريبت يحدد الـ LAN IP ويحدّث الـ .env تلقائياً:

ملف جديد: `raed_inventory/backend/setup_lan.py`

```python
"""Setup LAN access: detect host LAN IP, update .env ALLOWED_ORIGINS."""
import socket
import os
from pathlib import Path

def get_lan_ip() -> str:
    """Find the LAN IP this machine uses to reach the internet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually connect — just finds the right interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def update_env(ip: str) -> None:
    env_path = Path(__file__).parent / ".env"
    origins = (
        f"http://localhost:3000,http://localhost:5173,"
        f"http://{ip}:3000,http://127.0.0.1:3000"
    )
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        lines = [ln for ln in lines if not ln.startswith("ALLOWED_ORIGINS=")]
    lines.append(f"ALLOWED_ORIGINS={origins}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] .env updated at {env_path}")
    print(f"     ALLOWED_ORIGINS includes: http://{ip}:3000")

if __name__ == "__main__":
    ip = get_lan_ip()
    update_env(ip)
    print()
    print("=" * 60)
    print(f"Share this URL with area managers on the same WiFi:")
    print(f"    http://{ip}:3000")
    print("=" * 60)
```

شغّله مرة واحدة:

```powershell
cd C:\raed_inventory_system\raed_inventory\backend
python setup_lan.py
```

### 3) Windows Firewall — افتح ports 3000 و 8010

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "Raed Frontend (Vite)" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Raed Backend (uvicorn)" -Direction Inbound -Protocol TCP -LocalPort 8010 -Action Allow -Profile Private
```

**ملاحظة**: `-Profile Private` يحصر القاعدة على شبكات Private (زي الواي فاي اللي الراوتر فلاجرها كـ Private). لو الواي فاي عندك Public، غيّرها لـ `Private,Public`.

### 4) اعادة تشغيل uvicorn على `0.0.0.0`

```powershell
# أوقف القديم
Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue |
    Select-Object -First 1 |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# شغّل الجديد
cd C:\raed_inventory_system\raed_inventory\backend
$env:PYTHONPATH = (Get-Location).Path
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

لازم تشوف:
```
INFO:     Uvicorn running on http://0.0.0.0:8010
```

**مهم**: `0.0.0.0` مش `127.0.0.1`.

### 5) اعادة تشغيل Vite

في terminal تانية:

```powershell
cd C:\raed_inventory_system\raed_inventory\frontend
npm run dev
```

لازم تشوف سطرين زي:
```
VITE v... ready in XXX ms
➜  Local:   http://localhost:3000/
➜  Network: http://192.168.X.X:3000/   ← ده اللي المدراء هيستخدموه
```

### 6) تحقق من لابتوب تاني

من لابتوب تاني على نفس الواي فاي:
1. افتح المتصفح على الـ Network URL اللي ظهر من Vite (مثلاً `http://192.168.1.X:3000`)
2. لازم صفحة تسجيل الدخول تفتح
3. جرّب تسجّل دخول بـ admin — لازم يشتغل

لو الصفحة ما فتحتش:
- تأكد إنك على نفس الواي فاي (شغّل `ipconfig` على الـ host ولابتوب المستخدم — الـ subnet لازم يكون نفس الـ `192.168.X.X`)
- جرّب ping: `ping 192.168.X.X` من لابتوب المستخدم للـ host
- لو `ping` يرد لكن المتصفح لأ، المشكلة في الـ Firewall — تأكد من step 3

## الرد المطلوب

بعد التنفيذ، ابعت:
- ✅ الـ LAN IP اللي طلع من `setup_lan.py`
- ✅ output `uvicorn` (يبان فيه `0.0.0.0:8010`)
- ✅ output `npm run dev` (يبان فيه `Network: http://...:3000`)
- ✅ نتيجة الاختبار من لابتوب تاني (فتح الصفحة / تسجيل دخول)

## ملاحظة أمان
- كلمات مرور قوية إجبارية لأي مدير (الـ API بيفرض 8 أحرف + حرف كبير + رقم)
- بما إن ده LAN: لسه آمن نسبياً لأن مش متاح على الإنترنت
- لما إسلام يقفل اللابتوب: الخدمة بتقف للكل. ده متوقع.
- لو احتجت لاحقاً نقل الـ app لسيرفر دايم، ده scope مختلف (task N2).
