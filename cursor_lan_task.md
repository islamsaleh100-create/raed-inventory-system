# مهمة لكورسر — تفعيل وصول LAN لنظام رائد

## السياق
تم تعديل ملفات الإعداد بالفعل لدعم LAN:
- `frontend/vite.config.ts` → `host: true` + proxy على 8010
- `frontend/package.json` → script `dev:lan`
- `start_frontend.bat` → `--host 0.0.0.0 --port 3000`
- `start_backend.bat` → `--host 0.0.0.0 --port 8010`
- `setup_lan_firewall.ps1` → قواعد Firewall للمنفذين

**المتبقي:** تشغيل القواعد على Windows + إعادة تشغيل السيرفرين + التحقق من الوصول من لابتوب آخر.

IP الجهاز المستضيف: **10.40.201.232**

---

## الخطوات المطلوبة

### 1) إيقاف السيرفرات الحالية
أغلق أي نوافذ `start_backend.bat` و `start_frontend.bat` شغالة.
تأكد من إنهاء أي عملية على المنفذين:

```powershell
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Get-NetTCPConnection -LocalPort 8010 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### 2) إضافة قواعد Windows Firewall (Administrator)
افتح PowerShell كـ **Administrator** ثم شغّل:

```powershell
cd "C:\path\to\raed_inventory_system\raed_inventory"
.\setup_lan_firewall.ps1
```

تأكد من ظهور رسالة نجاح لكل قاعدة (Frontend 3000 + Backend 8010).

### 3) إعادة تشغيل السيرفرين
شغّل الاثنين في نافذتين منفصلتين:

```
start_backend.bat
start_frontend.bat
```

انتظر حتى تظهر:
- Backend: `Uvicorn running on http://0.0.0.0:8010`
- Frontend: `Network: http://10.40.201.232:3000`

### 4) التحقق محلياً على الجهاز المستضيف
```powershell
Invoke-WebRequest http://10.40.201.232:8010/api/v1/health -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest http://10.40.201.232:3000 -UseBasicParsing | Select-Object StatusCode
```
المتوقع: `200` لكل منهما.

### 5) التحقق من لابتوب آخر على نفس الواي فاي
من متصفح لابتوب زميل:
- افتح `http://10.40.201.232:3000`
- سجّل دخول بحساب تجريبي (مثلاً `am_riyadh`)
- تأكد أن شاشات النظام تحمّل طلبيات وبيانات من الـ API

### 6) في حالة فشل الوصول من اللابتوب الآخر
تحقق بالترتيب:
1. هل الجهازان على نفس الشبكة؟ (`ping 10.40.201.232` من اللابتوب الآخر)
2. هل الـ Profile في Firewall الـ "Private" أم "Public"؟ القاعدة تحتاج تكون شاملة للـ Profile الحالي.
3. هل هناك VPN شغّال يعزل الجهاز؟
4. شغّل هذا لتأكيد أن المنافذ مفتوحة خارجياً:
   ```powershell
   Test-NetConnection -ComputerName 10.40.201.232 -Port 3000
   Test-NetConnection -ComputerName 10.40.201.232 -Port 8010
   ```

### 7) التسليم
بعد نجاح التحقق، أعلم المستخدم:
- الرابط للموظفين: `http://10.40.201.232:3000`
- أن الـ IP قد يتغير إذا أعاد الراوتر توزيع العناوين — يُفضّل حجز IP ثابت من إعدادات الراوتر لاحقاً.

---

## ملاحظات
- لا تقم بتعديل ملفات الإعداد إلا إذا وجدت مشكلة جديدة — التعديلات السابقة صحيحة.
- إذا فشل تشغيل `setup_lan_firewall.ps1` بسبب Execution Policy، شغّل:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\setup_lan_firewall.ps1
  ```
