"""
سكريبت لإدخال الفروع عبر الـ API المحلي
شغّله من مجلد backend بعد تسجيل الدخول للنظام
"""
import urllib.request
import urllib.parse
import json

BASE = "http://localhost:8000/api/v1"

# ─── الخطوة 1: تسجيل الدخول ─────────────────────────────────────────────────

def login(username, password):
    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

# ─── الخطوة 2: إنشاء براند ───────────────────────────────────────────────────

def post(path, body, token):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:200]}")
        return None

# ─── البراندات المطلوب إنشاؤها إذا مش موجودة ────────────────────────────────

BRANDS_TO_CREATE = [
    {"name": "ONDA",                 "name_ar": "أوندا"},
    {"name": "Ronaldos Pizzeria",    "name_ar": "رونالدوز بيتزيريا"},
    {"name": "Shawarma Ala Almazaj", "name_ar": "شاورما على المزاج"},
]

# ─── البيانات ─────────────────────────────────────────────────────────────────

BRANCHES = [
    # ONDA — Eastern
    {"brand_name": "ONDA", "name": "ONDA Coffee - Al Firdaws",                       "region": "Eastern", "regular_hours": "06:00 AM TO 01:00 AM", "google_maps_url": "https://goo.gl/maps/XsTocFEkh3Z1UsTE6"},
    {"brand_name": "ONDA", "name": "ONDA Coffee - Ar Rayyan",                        "region": "Eastern", "regular_hours": "06:00 AM TO 12:00 AM", "google_maps_url": "https://maps.app.goo.gl/Diw5M5XWzwXbRH3R7?g_st=iw"},
    {"brand_name": "ONDA", "name": "ONDA Coffee - North Bldg. Aramco Rastanura",     "region": "Eastern", "regular_hours": "06:00 AM TO 03:00 PM", "google_maps_url": "https://maps.google.com/maps?q=26.724092%2C50.0687368&z=17&hl=en"},
    {"brand_name": "ONDA", "name": "ONDA Coffee - Najmah Complex Aramco Rastanura",  "region": "Eastern", "regular_hours": "06:00 AM TO 03:00 PM", "google_maps_url": "https://maps.google.com/maps?q=26.7167007%2C50.0733126&z=17&hl=en"},
    {"brand_name": "ONDA", "name": "ONDA Admin Building at Juhaymah Aramco",         "region": "Eastern", "regular_hours": "06:00 AM TO 03:00 PM", "google_maps_url": "https://maps.google.com/maps?q=26.768491744995117%2C49.987091064453125&z=17&hl=en"},
    {"brand_name": "ONDA", "name": "ONDA Midra Gym ARAMCO",                          "region": "Eastern", "regular_hours": "10:00 AM TO 10:00 PM", "google_maps_url": None},
    {"brand_name": "ONDA", "name": "ONDA Coffee - Qurtubah (Mouwasat)",              "region": "Eastern", "regular_hours": "06:00 AM TO 12:00 AM", "google_maps_url": "https://maps.app.goo.gl/i3VpJcv7vcpWHNWj9"},
    {"brand_name": "ONDA", "name": "ONDA Hessa Square",                              "region": "Eastern", "regular_hours": "06:00 AM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/B7VRXXFcFWzpeVCw7?g_st=iw"},
    # ONDA — Riyadh
    {"brand_name": "ONDA", "name": "ONDA Coffee - Al Safarat",                       "region": "Riyadh",  "regular_hours": "06:00 AM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/VeiyDWDEz7ppnE1g6?g_st=ic"},
    {"brand_name": "ONDA", "name": "ONDA Coffee - Al Malqa",                         "region": "Riyadh",  "regular_hours": "06:00 AM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/LrTZyveMNU5X8Uwo8"},
    {"brand_name": "ONDA", "name": "ONDA UNIVERSITY (DARUL ULOOM)",                  "region": "Riyadh",  "regular_hours": "07:30 AM TO 04:00 PM", "google_maps_url": None},
    # Ronaldos — Eastern
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria Al Firdous",                          "region": "Eastern", "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://goo.gl/maps/veQTS1ZBSXbn6ak1A"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Olaya",                             "region": "Eastern", "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.app.goo.gl/wpboU3xSAcbaQsNi7"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Al Khobar Ash Shamaliyah",          "region": "Eastern", "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.app.goo.gl/K1wDdcaxdHxxGopMA"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Aziziya",                           "region": "Eastern", "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.google.com/maps?q=26.2090832%2C50.1960137&z=17&hl=en"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Jabel Height Aramco Dhahran",       "region": "Eastern", "regular_hours": "10:00 AM TO 10:00 PM", "google_maps_url": "https://maps.app.goo.gl/U7CZtHXQvnX76cKd9"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - North Recreation Aramco Rastanura", "region": "Eastern", "regular_hours": "10:00 AM TO 10:00 PM", "google_maps_url": "https://maps.app.goo.gl/pPEoXQjUZhd4wTex5"},
    # Ronaldos — Riyadh
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Al-Mathar Ash Shamali, Riyadh",       "region": "Riyadh",  "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.google.com/maps/search/Ronaldo%E2%80%99s%20Pizzeria/@24.682333,46.669661,17z?hl=en"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Al Takhassousi (An Nakheel, Riyadh)", "region": "Riyadh",  "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.google.com/maps?q=24.7525102%2C46.6392819&z=17&hl=en"},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldo University (DARUL ULOOM)",                        "region": "Riyadh",  "regular_hours": "No Application",       "google_maps_url": None},
    {"brand_name": "Ronaldos Pizzeria", "name": "Ronaldos Pizzeria - Nada",                                "region": "Riyadh",  "regular_hours": "12:00 PM TO 12:00 AM", "google_maps_url": "https://maps.google.com/maps/search/Ronaldo%20'S%20Pizzeria/@24.787655,46.616792,17z?hl=en"},
    # Shawarma
    {"brand_name": "Shawarma Ala Almazaj", "name": "Shawarma Ala Almazaj - Al Firdaws, Dammam",       "region": "Eastern", "regular_hours": "12:00 PM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/GtPXN7kfxjB1NNpV9"},
    {"brand_name": "Shawarma Ala Almazaj", "name": "Shawarma Ala Almazaj - Al Khobar Ash Shamaliyah", "region": "Eastern", "regular_hours": "12:00 PM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/t6bp14YT2DuCz13E9"},
    {"brand_name": "Shawarma Ala Almazaj", "name": "Shawarma Ala Almazaj - Olaya Khobar",             "region": "Eastern", "regular_hours": "12:00 PM TO 01:00 AM", "google_maps_url": "https://maps.app.goo.gl/fETwezgeeZMEPaGj9"},
]

# ─── Main ─────────────────────────────────────────────────────────────────────

print("=" * 60)
print("  Raed Inventory — Branch Seeder")
print("=" * 60)

username = input("\nUsername (default: admin): ").strip() or "admin"
password = input("Password: ").strip()

print("\nLogging in...")
try:
    token = login(username, password)
    print(f"Logged in OK\n")
except Exception as e:
    print(f"Login failed: {e}")
    input("Press Enter to exit...")
    exit(1)

# جمع الـ brand IDs الموجودة
print("Fetching existing brands...")
req = urllib.request.Request(
    f"{BASE}/delivery/brands",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req) as r:
    existing_brands = {b["name"].lower(): b["id"] for b in json.loads(r.read())}
print(f"Found {len(existing_brands)} existing brands\n")

# إنشاء البراندات الناقصة
for b in BRANDS_TO_CREATE:
    if b["name"].lower() not in existing_brands:
        print(f"Creating brand: {b['name']} ...")
        result = post("/delivery/brands", b, token)
        if result:
            existing_brands[b["name"].lower()] = result["id"]
            print(f"  Brand created: {b['name']} (id={result['id']})")
        else:
            print(f"  Failed to create brand: {b['name']}")
    else:
        print(f"Brand exists: {b['name']}")
print()

inserted = 0
skipped  = 0

for br in BRANCHES:
    brand_name = br["brand_name"]
    brand_id   = existing_brands.get(brand_name.lower())

    if not brand_id:
        print(f"Brand '{brand_name}' not found — skipping {br['name']}")
        skipped += 1
        continue

    payload = {
        "brand_id":       brand_id,
        "name":           br["name"],
        "region":         br["region"],
        "regular_hours":  br["regular_hours"],
        "google_maps_url": br["google_maps_url"],
    }

    result = post("/delivery/branches", payload, token)
    if result:
        inserted += 1
        print(f"  ✓ {br['name']}")
    else:
        skipped += 1
        print(f"  ✗ {br['name']} (already exists or error)")

print(f"\n{'='*60}")
print(f"  Done: {inserted} inserted, {skipped} skipped")
print(f"{'='*60}")
input("\nPress Enter to close...")
