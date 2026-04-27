import sqlite3
from datetime import datetime

DB = 'raed_inventory_local.db'
now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
db = sqlite3.connect(DB)

def get_or_create_brand(name, name_ar):
    row = db.execute("SELECT id FROM delivery_brands WHERE lower(name)=lower(?)", (name,)).fetchone()
    if row:
        print(f"  Brand exists: {name} (id={row[0]})")
        return row[0]
    cur = db.execute("INSERT INTO delivery_brands (name,name_ar,is_active,created_at) VALUES (?,?,1,?)", (name, name_ar, now))
    print(f"  Brand created: {name} (id={cur.lastrowid})")
    return cur.lastrowid

def add_branch(brand_id, name, region, hours, maps):
    row = db.execute("SELECT id FROM delivery_branches WHERE brand_id=? AND lower(name)=lower(?)", (brand_id, name)).fetchone()
    if row:
        print(f"    skip (exists): {name}")
        return
    db.execute(
        "INSERT INTO delivery_branches (brand_id,name,region,regular_hours,google_maps_url,is_active,created_at) VALUES (?,?,?,?,?,1,?)",
        (brand_id, name, region, hours, maps or None, now)
    )
    print(f"    + {name}")

print("\n=== Creating Brands ===")
onda_id     = get_or_create_brand("ONDA",                 "أوندا")
ronaldo_id  = get_or_create_brand("Ronaldos Pizzeria",    "رونالدوز بيتزيريا")
shawarma_id = get_or_create_brand("Shawarma Ala Almazaj", "شاورما على المزاج")

print("\n=== ONDA Branches ===")
add_branch(onda_id, "ONDA Coffee - Al Firdaws",                      "Eastern", "06:00 AM TO 01:00 AM", "https://goo.gl/maps/XsTocFEkh3Z1UsTE6")
add_branch(onda_id, "ONDA Coffee - Ar Rayyan",                       "Eastern", "06:00 AM TO 12:00 AM", "https://maps.app.goo.gl/Diw5M5XWzwXbRH3R7?g_st=iw")
add_branch(onda_id, "ONDA Coffee - North Bldg. Aramco Rastanura",    "Eastern", "06:00 AM TO 03:00 PM", "https://maps.google.com/maps?q=26.724092%2C50.0687368&z=17&hl=en")
add_branch(onda_id, "ONDA Coffee - Najmah Complex Aramco Rastanura", "Eastern", "06:00 AM TO 03:00 PM", "https://maps.google.com/maps?q=26.7167007%2C50.0733126&z=17&hl=en")
add_branch(onda_id, "ONDA Admin Building at Juhaymah Aramco",        "Eastern", "06:00 AM TO 03:00 PM", "https://maps.google.com/maps?q=26.768491744995117%2C49.987091064453125&z=17&hl=en")
add_branch(onda_id, "ONDA Midra Gym ARAMCO",                         "Eastern", "10:00 AM TO 10:00 PM", "")
add_branch(onda_id, "ONDA Coffee - Qurtubah (Mouwasat)",             "Eastern", "06:00 AM TO 12:00 AM", "https://maps.app.goo.gl/i3VpJcv7vcpWHNWj9")
add_branch(onda_id, "ONDA Hessa Square",                             "Eastern", "06:00 AM TO 01:00 AM", "https://maps.app.goo.gl/B7VRXXFcFWzpeVCw7?g_st=iw")
add_branch(onda_id, "ONDA Coffee - Al Safarat",                      "Riyadh",  "06:00 AM TO 01:00 AM", "https://maps.app.goo.gl/VeiyDWDEz7ppnE1g6?g_st=ic")
add_branch(onda_id, "ONDA Coffee - Al Malqa",                        "Riyadh",  "06:00 AM TO 01:00 AM", "https://maps.app.goo.gl/LrTZyveMNU5X8Uwo8")
add_branch(onda_id, "ONDA UNIVERSITY (DARUL ULOOM)",                 "Riyadh",  "07:30 AM TO 04:00 PM", "")

print("\n=== Ronaldos Branches ===")
add_branch(ronaldo_id, "Ronaldos Pizzeria Al Firdous",                          "Eastern", "12:00 PM TO 12:00 AM", "https://goo.gl/maps/veQTS1ZBSXbn6ak1A")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Olaya",                             "Eastern", "12:00 PM TO 12:00 AM", "https://maps.app.goo.gl/wpboU3xSAcbaQsNi7")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Al Khobar Ash Shamaliyah",          "Eastern", "12:00 PM TO 12:00 AM", "https://maps.app.goo.gl/K1wDdcaxdHxxGopMA")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Aziziya",                           "Eastern", "12:00 PM TO 12:00 AM", "https://maps.google.com/maps?q=26.2090832%2C50.1960137&z=17&hl=en")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Jabel Height Aramco Dhahran",       "Eastern", "10:00 AM TO 10:00 PM", "https://maps.app.goo.gl/U7CZtHXQvnX76cKd9")
add_branch(ronaldo_id, "Ronaldos Pizzeria - North Recreation Aramco Rastanura", "Eastern", "10:00 AM TO 10:00 PM", "https://maps.app.goo.gl/pPEoXQjUZhd4wTex5")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Al-Mathar Ash Shamali, Riyadh",     "Riyadh",  "12:00 PM TO 12:00 AM", "https://maps.google.com/maps/search/Ronaldo%E2%80%99s%20Pizzeria/@24.682333,46.669661,17z?hl=en")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Al Takhassousi (An Nakheel)",       "Riyadh",  "12:00 PM TO 12:00 AM", "https://maps.google.com/maps?q=24.7525102%2C46.6392819&z=17&hl=en")
add_branch(ronaldo_id, "Ronaldo University (DARUL ULOOM)",                      "Riyadh",  "No Application",       "")
add_branch(ronaldo_id, "Ronaldos Pizzeria - Nada",                              "Riyadh",  "12:00 PM TO 12:00 AM", "https://maps.google.com/maps/search/Ronaldo%20'S%20Pizzeria/@24.787655,46.616792,17z?hl=en")

print("\n=== Shawarma Branches ===")
add_branch(shawarma_id, "Shawarma Ala Almazaj - Al Firdaws, Dammam",      "Eastern", "12:00 PM TO 01:00 AM", "https://maps.app.goo.gl/GtPXN7kfxjB1NNpV9")
add_branch(shawarma_id, "Shawarma Ala Almazaj - Al Khobar Ash Shamaliyah","Eastern", "12:00 PM TO 01:00 AM", "https://maps.app.goo.gl/t6bp14YT2DuCz13E9")
add_branch(shawarma_id, "Shawarma Ala Almazaj - Olaya Khobar",            "Eastern", "12:00 PM TO 01:00 AM", "https://maps.app.goo.gl/fETwezgeeZMEPaGj9")

db.commit()
db.close()
print("\n✅ All done!")
input("\nPress Enter to close...")
