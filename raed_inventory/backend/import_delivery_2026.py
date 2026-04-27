import json, urllib.request

BASE = "http://localhost:8000/api/v1"

# ─── البيانات المستخرجة من الملف ─────────────────────────────────────────────
ROWS = [
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Khobar Ash Shamaliyah","app_name":"HungerStation","orders":108,"revenue":10169.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Firdaws","app_name":"HungerStation","orders":456,"revenue":42377.75},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Takhassousi","app_name":"HungerStation","orders":110,"revenue":9860.75},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Ulaya","app_name":"HungerStation","orders":143,"revenue":12396.25},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Nada","app_name":"HungerStation","orders":76,"revenue":7371.0},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Khuzama","app_name":"HungerStation","orders":141,"revenue":12468.0},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Mathar Ash Shamali","app_name":"HungerStation","orders":44,"revenue":431050.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Najmah","app_name":"HungerStation","orders":9,"revenue":324.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Malqa","app_name":"HungerStation","orders":30,"revenue":1105.75},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Qurtubah","app_name":"HungerStation","orders":124,"revenue":3541.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Safarat","app_name":"HungerStation","orders":99,"revenue":3237.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Firdaws","app_name":"HungerStation","orders":112,"revenue":3459.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Hessa","app_name":"HungerStation","orders":62,"revenue":1783.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Rayyan","app_name":"HungerStation","orders":20,"revenue":588.0},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Firdaws","app_name":"HungerStation","orders":310,"revenue":17947.59},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Aziziah","app_name":"HungerStation","orders":139,"revenue":7930.7},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Nada","app_name":"HungerStation","orders":89,"revenue":5692.44},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Khobar Ash Shamaliyah","app_name":"HungerStation","orders":82,"revenue":4761.92},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Olaya","app_name":"HungerStation","orders":75,"revenue":4306.73},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Takhassousi","app_name":"HungerStation","orders":59,"revenue":3584.73},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Mathar","app_name":"HungerStation","orders":35,"revenue":2012.96},
    {"year":2026,"month":1,"brand_name":"Griddle","branch_name":"Al Firdaws","app_name":"HungerStation","orders":96,"revenue":16233.0},
    {"year":2026,"month":1,"brand_name":"Griddle","branch_name":"Al Khobar","app_name":"HungerStation","orders":67,"revenue":11012.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Khobar Ash Shamaliyah","app_name":"Keeta","orders":42,"revenue":4305.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Firdaws","app_name":"Keeta","orders":189,"revenue":18072.25},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Takhassousi","app_name":"Keeta","orders":29,"revenue":2716.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Ulaya","app_name":"Keeta","orders":39,"revenue":3668.75},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Nada","app_name":"Keeta","orders":20,"revenue":1952.0},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Khuzama","app_name":"Keeta","orders":39,"revenue":3511.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Najmah","app_name":"Keeta","orders":4,"revenue":159.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Malqa","app_name":"Keeta","orders":12,"revenue":462.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Qurtubah","app_name":"Keeta","orders":47,"revenue":1483.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Safarat","app_name":"Keeta","orders":38,"revenue":1296.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Firdaws","app_name":"Keeta","orders":42,"revenue":1358.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Hessa","app_name":"Keeta","orders":22,"revenue":672.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Rayyan","app_name":"Keeta","orders":9,"revenue":288.0},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Firdaws","app_name":"Keeta","orders":89,"revenue":5203.5},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Khobar Ash Shamaliyah","app_name":"Keeta","orders":42,"revenue":2456.0},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Olaya","app_name":"Keeta","orders":29,"revenue":1698.5},
    {"year":2026,"month":1,"brand_name":"Griddle","branch_name":"Al Firdaws","app_name":"Keeta","orders":42,"revenue":7245.0},
    {"year":2026,"month":1,"brand_name":"Griddle","branch_name":"Al Khobar","app_name":"Keeta","orders":29,"revenue":4897.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Khobar Ash Shamaliyah","app_name":"Ninja","orders":20,"revenue":1987.5},
    {"year":2026,"month":1,"brand_name":"Ronaldos Pizzeria","branch_name":"Al Firdaws","app_name":"Ninja","orders":89,"revenue":8234.75},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Qurtubah","app_name":"Ninja","orders":29,"revenue":912.5},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Safarat","app_name":"Ninja","orders":20,"revenue":685.0},
    {"year":2026,"month":1,"brand_name":"ONDA Coffee","branch_name":"Firdaws","app_name":"Ninja","orders":18,"revenue":578.0},
    {"year":2026,"month":1,"brand_name":"Shawarma Ala Almazaj","branch_name":"Al Firdaws","app_name":"Ninja","orders":42,"revenue":2456.0},
    {"year":2026,"month":1,"brand_name":"Griddle","branch_name":"Al Firdaws","app_name":"Ninja","orders":29,"revenue":4923.5},
]

print(f"Total rows to import: {len(ROWS)}")

# ─── تسجيل الدخول ────────────────────────────────────────────────────────────
login_data = json.dumps({"username":"admin","password":"Admin@2024"}).encode()
req = urllib.request.Request(f"{BASE}/auth/login", data=login_data,
                              headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req) as r:
    token = json.loads(r.read())["access_token"]
print("Logged in OK")

# ─── استيراد ─────────────────────────────────────────────────────────────────
payload = json.dumps({"batch_name":"import_jan_2026","rows":ROWS}).encode()
req = urllib.request.Request(
    f"{BASE}/delivery/import",
    data=payload,
    headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
)
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())

print(f"\n✅ Done!")
print(f"   Imported : {result['imported']}")
print(f"   Skipped  : {result['skipped']}")
print(f"   Unmatched: {result['unmatched']}")
input("\nPress Enter to close...")
