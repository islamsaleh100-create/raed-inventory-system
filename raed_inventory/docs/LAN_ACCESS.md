# الوصول عبر شبكة LAN (فروع المكتب)

تشغيل Raed Inventory على جهاز Windows واحد ثم فتح الواجهة من أجهزة أخرى على نفس الشبكة (Wi‑Fi / LAN).

## المتطلبات

1. **جدار الحماية (Windows Firewall)**  
   اسمح بالوارد TCP على المنافذ **3000** (واجهة Vite) و **8010** (FastAPI / uvicorn).

   من PowerShell **كمسؤول (Run as Administrator)** داخل مجلد المشروع:

   ```powershell
   cd C:\raed_inventory_system\raed_inventory
   .\setup_lan_firewall.ps1
   ```

   أو أضف القاعدتين يدويًا من **Windows Defender Firewall → Advanced settings → Inbound Rules**.

2. **تشغيل الخادمين مع الاستماع على كل الواجهات**

   - الطريقة الموحّدة: تشغيل `run_local.ps1` (يشغّل الـ backend على `0.0.0.0:8010` والـ frontend على `0.0.0.0:3000`).
   - أو من جذر `raed_inventory`:
     - `start_backend.bat` — uvicorn على المنفذ **8010**
     - `start_frontend.bat` — Vite على المنفذ **3000** مع `--host 0.0.0.0`

   إعدادات Vite في `frontend/vite.config.ts`: `server.host` مفعّل للـ LAN ما لم تضبط `VITE_DEV_BIND_LAN=0` في `.env.local`.

3. **مشاركة الرابط مع الموظفين**

   بعد معرفة عنوان IPv4 للجهاز المضيف (مثلاً من `ipconfig`):

   - الواجهة: `http://<IP>:3000`
   - فحص الـ API: `http://<IP>:8010/api/v1/health`

   في وضع التطوير، طلبات المتصفح تمر عبر مسار `/api/v1` على نفس منفذ الواجهة (بروكسي Vite) نحو الـ backend على الجهاز المضيف، لذلك لا حاجة لتغيير `VITE_API_URL` على أجهزة الفروع طالما يفتحون صفحة `http://<IP>:3000`.

## تحقق سريع (PowerShell على جهاز الخادم)

```powershell
curl http://127.0.0.1:3000 -UseBasicParsing | Select-Object StatusCode
curl "http://$( (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } | Select-Object -First 1).IPAddress ):3000" -UseBasicParsing | Select-Object StatusCode
curl "http://$( (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } | Select-Object -First 1).IPAddress ):8010/api/v1/health" -UseBasicParsing | Select-Object StatusCode
```

المتوقع: **StatusCode 200** للثلاثة بعد تشغيل السيرفرات.
