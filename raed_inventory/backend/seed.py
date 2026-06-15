"""
Seed script for Raed Inventory System
Run: python seed.py
Creates all required initial data including roles, admin user, sample branches, items, etc.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import (
    Base, Role, User, UserRole, Permission, RolePermission,
    Warehouse, Branch, ItemCategory, UnitOfMeasure, Item,
    InventoryVarianceReason, ReceivingVarianceReason, SystemSetting,
    BranchStock, WarehouseStock, RoleName, AvgConsumptionMode
)
from app.core.security import get_password_hash
from decimal import Decimal


def create_tables():
    """
    Safety-net table creation.
    On PostgreSQL: tables must already exist via `alembic upgrade head`.
    This function is a no-op on PostgreSQL and only creates tables on SQLite.
    """
    url = str(engine.url)
    if not url.startswith("sqlite"):
        # On PostgreSQL, trust Alembic. Do not create tables at seed time.
        print("ℹ️  PostgreSQL detected — skipping create_all (use `alembic upgrade head` first)")
        return
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created (SQLite)")


def seed_roles(db: Session):
    roles_data = [
        (RoleName.super_admin, "Super Administrator", "Full system access"),
        (RoleName.admin, "System Administrator", "Administrative access"),
        (RoleName.branch_manager, "Branch Manager", "Branch management and approval"),
        (RoleName.branch_user, "Branch User", "Daily inventory and order entry"),
        (RoleName.warehouse_manager, "Warehouse Manager", "Warehouse management and dispatch"),
        (RoleName.warehouse_user, "Warehouse User", "Picking and dispatch execution"),
        (RoleName.operations_manager, "Operations Manager", "Reports and monitoring"),
    ]
    roles = {}
    for name, display, desc in roles_data:
        existing = db.query(Role).filter(Role.name == name).first()
        if not existing:
            role = Role(name=name, display_name=display, description=desc)
            db.add(role)
            db.flush()
            roles[name] = role
        else:
            roles[name] = existing
    db.commit()
    print(f"✅ Roles seeded: {len(roles)}")
    return roles


def seed_admin_user(db: Session, roles: dict):
    existing = db.query(User).filter(User.username == "admin").first()
    if not existing:
        admin = User(
            username="admin",
            email="admin@raed.com",
            full_name="System Administrator",
            hashed_password=get_password_hash("Admin@2025"),
            status="active",
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role_id=roles[RoleName.super_admin].id))
        db.commit()
        print("✅ Admin user created: admin / Admin@2025")
    else:
        print("ℹ️  Admin user already exists")


def seed_warehouses(db: Session):
    warehouses_data = [
        ("WH-RYD", "مستودع الرياض الرئيسي", "الرياض - المنطقة الصناعية"),
        ("WH-DMM", "مستودع الدمام", "الدمام - المنطقة الصناعية الثانية"),
    ]
    warehouses = {}
    for code, name, location in warehouses_data:
        existing = db.query(Warehouse).filter(Warehouse.warehouse_code == code).first()
        if not existing:
            wh = Warehouse(warehouse_code=code, warehouse_name=name, location=location)
            db.add(wh)
            db.flush()
            warehouses[code] = wh
        else:
            warehouses[code] = existing
    db.commit()
    print(f"✅ Warehouses seeded: {len(warehouses)}")
    return warehouses


def seed_branches(db: Session, warehouses: dict):
    wh_ryd = warehouses.get("WH-RYD")
    wh_dmm = warehouses.get("WH-DMM")

    branches_data = [
        ("BR-RYD-01", "فرع الرياض - العليا", "الرياض", "العليا", wh_ryd.id),
        ("BR-RYD-02", "فرع الرياض - النخيل", "الرياض", "النخيل", wh_ryd.id),
        ("BR-RYD-03", "فرع الرياض - حي الملقا", "الرياض", "الملقا", wh_ryd.id),
        ("BR-RYD-04", "فرع الرياض - الورود", "الرياض", "الورود", wh_ryd.id),
        ("BR-DMM-01", "فرع الدمام - الفيصلية", "الدمام", "الفيصلية", wh_dmm.id),
        ("BR-DMM-02", "فرع الدمام - الشاطئ", "الدمام", "الشاطئ", wh_dmm.id),
        ("BR-KHB-01", "فرع الخبر - التحلية", "الخبر", "التحلية", wh_dmm.id),
    ]

    branches_data += [
        ("BR-RYD-05", "KITCHEN / RIYADH", "Riyadh", "Kitchen", wh_ryd.id),
        ("BR-DMM-03", "KITCHEN / DAM", "Dammam", "Kitchen", wh_dmm.id),
        ("BR-DMM-04", "Onda 1 - ARKAN", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-06", "Onda 13 - Al Malqa", "Riyadh", "Al Malqa", wh_ryd.id),
        ("BR-HSA-01", "Onda 14 - HASSA", "Al Ahsa", "Hassa", wh_dmm.id),
        ("BR-DMM-05", "Onda 16 - Namjah", "Dammam", "Namjah", wh_dmm.id),
        ("BR-DMM-06", "Onda 18 - Al Midra Gym", "Dammam", "Al Midra Gym", wh_dmm.id),
        ("BR-DMM-07", "Onda 2 - HOQAIL", "Khobar", "Hoqail", wh_dmm.id),
        ("BR-RYD-07", "Onda 4 - SEFARAT", "Riyadh", "Sefarat", wh_ryd.id),
        ("BR-DMM-08", "Onda 5 - MUOWASAT", "Dammam", "Muowasat", wh_dmm.id),
        ("BR-RTN-01", "Onda 9 - Ras Tanura", "Ras Tanura", "Ras Tanura", wh_dmm.id),
        ("BR-DMM-09", "ONDA DAU University", "Khobar", "DAU University", wh_dmm.id),
        ("BR-KHB-02", "Pizza 1 - AlKHOBAR", "Khobar", "Al Khobar", wh_dmm.id),
        ("BR-DMM-10", "Pizza 10 - Mazaar", "Dammam", "Mazaar", wh_dmm.id),
        ("BR-RTN-02", "Pizza 15 - Ras Tanura", "Ras Tanura", "Ras Tanura", wh_dmm.id),
        ("BR-DMM-11", "Pizza 3 - Arkan", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-08", "Pizza 4 - Riyadh Takhasosy", "Riyadh", "Takhasosy", wh_ryd.id),
        ("BR-RYD-09", "Pizza 5 - ALULYA", "Riyadh", "Al Ulya", wh_ryd.id),
        ("BR-RYD-10", "Pizza 6 - Riyadh Nada", "Riyadh", "Al Nada", wh_ryd.id),
        ("BR-DMM-12", "Pizza 7 - Aramco", "Dhahran", "Aramco", wh_dmm.id),
        ("BR-KHB-03", "Pizza 9 - Al Azizia", "Khobar", "Al Azizia", wh_dmm.id),
        ("BR-DMM-13", "Ronaldos DAU University", "Khobar", "DAU University", wh_dmm.id),
        ("BR-KHB-04", "SHAWERMA - 1 - Khobar", "Khobar", "Khobar", wh_dmm.id),
        ("BR-DMM-14", "SHAWERMA - 4 - ARKAN", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-11", "SHAWERMA - OLAYA", "Riyadh", "Olaya", wh_ryd.id),
    ]

    branches = {}
    for code, name, city, area, wh_id in branches_data:
        existing = db.query(Branch).filter(Branch.branch_code == code).first()
        if not existing:
            br = Branch(branch_code=code, branch_name=name, city=city, area=area, warehouse_id=wh_id)
            db.add(br)
            db.flush()
            branches[code] = br
        else:
            branches[code] = existing
    db.commit()
    print(f"✅ Branches seeded: {len(branches)}")
    return branches


def seed_demo_users(db: Session, roles: dict, branches: dict, warehouses: dict):
    users_data = [
        # (username, email, name, password, role, branch_code, wh_code)
        ("branch.mgr1", "br.mgr1@raed.com", "مدير فرع العليا", "Raed@2025",
         RoleName.branch_manager, "BR-RYD-01", None),
        ("branch.user1", "br.user1@raed.com", "موظف فرع العليا", "Raed@2025",
         RoleName.branch_user, "BR-RYD-01", None),
        ("branch.mgr2", "br.mgr2@raed.com", "مدير فرع الدمام", "Raed@2025",
         RoleName.branch_manager, "BR-DMM-01", None),
        ("branch.user2", "br.user2@raed.com", "موظف فرع الدمام", "Raed@2025",
         RoleName.branch_user, "BR-DMM-01", None),
        ("wh.mgr1", "wh.mgr1@raed.com", "مدير مستودع الرياض", "Raed@2025",
         RoleName.warehouse_manager, None, "WH-RYD"),
        ("wh.user1", "wh.user1@raed.com", "موظف مستودع الرياض", "Raed@2025",
         RoleName.warehouse_user, None, "WH-RYD"),
        ("ops.mgr", "ops.mgr@raed.com", "مدير العمليات", "Raed@2025",
         RoleName.operations_manager, None, None),
    ]

    for username, email, name, password, role_name, br_code, wh_code in users_data:
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            branch_id = branches[br_code].id if br_code and br_code in branches else None
            wh_id = warehouses[wh_code].id if wh_code and wh_code in warehouses else None
            user = User(
                username=username,
                email=email,
                full_name=name,
                hashed_password=get_password_hash(password),
                status="active",
                branch_id=branch_id,
                warehouse_id=wh_id,
            )
            db.add(user)
            db.flush()
            role = roles.get(role_name)
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    print("✅ Demo users seeded")


def seed_categories(db: Session):
    cats = [
        ("RAW", "مواد خام", "Raw Materials"),
        ("PKG", "مواد تغليف", "Packaging"),
        ("SAUCE", "صلصات وتوابل", "Sauces & Spices"),
        ("DAIRY", "ألبان ومشتقات", "Dairy Products"),
        ("MEAT", "لحوم ودواجن", "Meat & Poultry"),
        ("VEG", "خضروات وفواكه", "Vegetables & Fruits"),
        ("DRY", "مواد جافة", "Dry Goods"),
        ("BEV", "مشروبات", "Beverages"),
        ("CLEAN", "مواد تنظيف", "Cleaning Supplies"),
        ("DISP", "أدوات تقديم", "Disposables"),
    ]
    categories = {}
    for code, name_ar, name_en in cats:
        existing = db.query(ItemCategory).filter(ItemCategory.code == code).first()
        if not existing:
            cat = ItemCategory(code=code, name_ar=name_ar, name_en=name_en)
            db.add(cat)
            db.flush()
            categories[code] = cat
        else:
            categories[code] = existing
    db.commit()
    print("✅ Categories seeded")
    return categories


def seed_units(db: Session):
    units = [
        ("KG", "كيلوجرام", "Kilogram"),
        ("G", "جرام", "Gram"),
        ("L", "لتر", "Liter"),
        ("ML", "ملليلتر", "Milliliter"),
        ("PCS", "قطعة", "Piece"),
        ("BOX", "صندوق", "Box"),
        ("BAG", "كيس", "Bag"),
        ("BTL", "زجاجة", "Bottle"),
        ("CAN", "علبة", "Can"),
        ("PKT", "عبوة", "Packet"),
        ("ROLL", "رول", "Roll"),
        ("DZN", "درزن", "Dozen"),
    ]
    uom_dict = {}
    for code, name_ar, name_en in units:
        existing = db.query(UnitOfMeasure).filter(UnitOfMeasure.code == code).first()
        if not existing:
            u = UnitOfMeasure(code=code, name_ar=name_ar, name_en=name_en)
            db.add(u)
            db.flush()
            uom_dict[code] = u
        else:
            uom_dict[code] = existing
    db.commit()
    print("✅ Units seeded")
    return uom_dict


def seed_items(db: Session, categories: dict, units: dict):
    items_data = [
        # (code, name_ar, name_en, cat, unit, min, max, reorder, safety, lead_days, critical)
        ("ITM-001", "دقيق قمح - 50 كجم", "Wheat Flour 50kg", "RAW", "BAG", 5, 50, 10, 5, 2, True),
        ("ITM-002", "زيت نباتي - 18 لتر", "Vegetable Oil 18L", "RAW", "CAN", 5, 40, 8, 4, 2, True),
        ("ITM-003", "خبز برجر", "Burger Buns", "DRY", "PKT", 10, 100, 20, 10, 1, True),
        ("ITM-004", "صدر دجاج - كجم", "Chicken Breast KG", "MEAT", "KG", 10, 80, 20, 10, 1, True),
        ("ITM-005", "لحم بقري مفروم", "Ground Beef", "MEAT", "KG", 5, 50, 10, 5, 1, True),
        ("ITM-006", "جبن شيدر", "Cheddar Cheese", "DAIRY", "KG", 3, 30, 6, 3, 1, False),
        ("ITM-007", "صلصة طماطم - كجم", "Tomato Sauce KG", "SAUCE", "BAG", 5, 40, 10, 5, 2, False),
        ("ITM-008", "خس طازج", "Fresh Lettuce", "VEG", "KG", 3, 20, 5, 3, 1, False),
        ("ITM-009", "طماطم طازجة", "Fresh Tomatoes", "VEG", "KG", 5, 30, 8, 4, 1, False),
        ("ITM-010", "بصل طازج", "Fresh Onions", "VEG", "KG", 5, 30, 8, 4, 1, False),
        ("ITM-011", "علب تقديم كبيرة", "Large Serving Boxes", "DISP", "BOX", 2, 20, 4, 2, 3, False),
        ("ITM-012", "كاسات بلاستيك", "Plastic Cups", "DISP", "PKT", 3, 30, 5, 3, 3, False),
        ("ITM-013", "مناديل ورقية", "Paper Napkins", "DISP", "PKT", 5, 50, 10, 5, 3, False),
        ("ITM-014", "كيس شاورما", "Shawarma Wrap Bags", "PKG", "PKT", 3, 30, 6, 3, 3, False),
        ("ITM-015", "بهارات شاورما", "Shawarma Spices", "SAUCE", "KG", 2, 20, 4, 2, 3, False),
        ("ITM-016", "صلصة ثوم", "Garlic Sauce", "SAUCE", "KG", 3, 25, 6, 3, 2, False),
        ("ITM-017", "بطاطس مجمدة", "Frozen Fries", "RAW", "BAG", 5, 40, 10, 5, 1, True),
        ("ITM-018", "جبن موزاريلا", "Mozzarella Cheese", "DAIRY", "KG", 3, 25, 6, 3, 1, True),
        ("ITM-019", "عجينة بيتزا", "Pizza Dough", "RAW", "KG", 5, 40, 10, 5, 1, True),
        ("ITM-020", "قهوة مطحونة", "Ground Coffee", "BEV", "KG", 2, 15, 4, 2, 3, True),
        ("ITM-021", "حليب طازج - لتر", "Fresh Milk 1L", "DAIRY", "BTL", 10, 80, 20, 10, 1, False),
        ("ITM-022", "مياه معدنية 500مل", "Mineral Water 500ml", "BEV", "BOX", 5, 50, 10, 5, 2, False),
        ("ITM-023", "سكر أبيض", "White Sugar KG", "DRY", "KG", 5, 40, 8, 4, 3, False),
        ("ITM-024", "ملح طعام", "Table Salt KG", "DRY", "KG", 3, 20, 5, 3, 3, False),
        ("ITM-025", "صابون أطباق", "Dish Soap", "CLEAN", "BTL", 3, 20, 5, 3, 5, False),
    ]

    for code, name_ar, name_en, cat_code, unit_code, mn, mx, rp, ss, lt, crit in items_data:
        existing = db.query(Item).filter(Item.item_code == code).first()
        if not existing:
            cat = categories.get(cat_code)
            unit = units.get(unit_code)
            if cat and unit:
                item = Item(
                    item_code=code,
                    item_name_ar=name_ar,
                    item_name_en=name_en,
                    category_id=cat.id,
                    unit_id=unit.id,
                    min_qty=Decimal(str(mn)),
                    max_qty=Decimal(str(mx)),
                    reorder_point=Decimal(str(rp)),
                    safety_stock=Decimal(str(ss)),
                    lead_time_days=lt,
                    critical_item=crit,
                    average_consumption_mode=AvgConsumptionMode.last_7_days,
                )
                db.add(item)
    db.commit()
    print("✅ Items seeded: 25 items")


def seed_variance_reasons(db: Session):
    inv_reasons = [
        ("تلف / هالك", "Damaged / Spoilage"),
        ("خطأ في الجرد السابق", "Previous Inventory Error"),
        ("سرقة / فقدان", "Theft / Loss"),
        ("صرف داخلي غير مسجل", "Unregistered Internal Use"),
        ("فرق في الوزن", "Weight Difference"),
        ("إرجاع للمستودع", "Return to Warehouse"),
    ]
    for reason_ar, reason_en in inv_reasons:
        existing = db.query(InventoryVarianceReason).filter(
            InventoryVarianceReason.reason_ar == reason_ar
        ).first()
        if not existing:
            db.add(InventoryVarianceReason(reason_ar=reason_ar, reason_en=reason_en))

    recv_reasons = [
        ("منتج تالف عند الاستلام", "Damaged product on receipt"),
        ("كمية ناقصة", "Short quantity"),
        ("اختلاف في المواصفات", "Specification mismatch"),
        ("تاريخ انتهاء قريب", "Near expiry date"),
        ("خطأ في التعبئة", "Packaging error"),
    ]
    for reason_ar, reason_en in recv_reasons:
        existing = db.query(ReceivingVarianceReason).filter(
            ReceivingVarianceReason.reason_ar == reason_ar
        ).first()
        if not existing:
            db.add(ReceivingVarianceReason(reason_ar=reason_ar, reason_en=reason_en))

    db.commit()
    print("✅ Variance reasons seeded")


def seed_system_settings(db: Session):
    settings_data = [
        ("days_of_cover_target", "3", "Target days of stock coverage for replenishment"),
        ("avg_consumption_mode", "last_7_days", "Default consumption calculation window"),
        ("variance_warning_threshold_pct", "10", "Variance % that triggers warning"),
        ("variance_critical_threshold_pct", "25", "Variance % that triggers critical alert"),
        ("auto_generate_order_on_approval", "true", "Auto generate order when inventory approved"),
        ("require_variance_reason", "true", "Require reason for critical variances"),
        ("max_exceptional_order_per_day", "3", "Max exceptional orders per branch per day"),
        ("inventory_reminder_time", "08:00", "Time to send daily inventory reminder"),
    ]
    for key, value, desc in settings_data:
        existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not existing:
            db.add(SystemSetting(key=key, value=value, description=desc))
    db.commit()
    print("✅ System settings seeded")


def seed_initial_warehouse_stock(db: Session, warehouses: dict):
    """Seed initial warehouse stock quantities"""
    wh = warehouses.get("WH-RYD")
    if not wh:
        return

    items = db.query(Item).filter(Item.active == True).all()
    for item in items:
        existing = db.query(WarehouseStock).filter(
            WarehouseStock.warehouse_id == wh.id,
            WarehouseStock.item_id == item.id
        ).first()
        if not existing:
            # Start with reasonable stock levels
            initial_qty = float(item.max_qty) * 0.7
            db.add(WarehouseStock(
                warehouse_id=wh.id,
                item_id=item.id,
                current_qty=Decimal(str(round(initial_qty, 2))),
            ))

    wh_dmm = warehouses.get("WH-DMM")
    if wh_dmm:
        for item in items:
            existing = db.query(WarehouseStock).filter(
                WarehouseStock.warehouse_id == wh_dmm.id,
                WarehouseStock.item_id == item.id
            ).first()
            if not existing:
                initial_qty = float(item.max_qty) * 0.5
                db.add(WarehouseStock(
                    warehouse_id=wh_dmm.id,
                    item_id=item.id,
                    current_qty=Decimal(str(round(initial_qty, 2))),
                ))

    db.commit()
    print("✅ Initial warehouse stock seeded")


def seed_branches_onda(db: Session, warehouses: dict):
    wh_ryd = warehouses.get("WH-RYD")
    wh_dmm = warehouses.get("WH-DMM")
    legacy_branch_codes = [
        "BR-RYD-01", "BR-RYD-02", "BR-RYD-03", "BR-RYD-04",
        "BR-DMM-01", "BR-DMM-02", "BR-KHB-01",
    ]
    branches_data = [
        ("BR-RYD-05", "KITCHEN / RIYADH", "Riyadh", "Kitchen", wh_ryd.id),
        ("BR-DMM-03", "KITCHEN / DAM", "Dammam", "Kitchen", wh_dmm.id),
        ("BR-DMM-04", "Onda 1 - ARKAN", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-06", "Onda 13 - Al Malqa", "Riyadh", "Al Malqa", wh_ryd.id),
        ("BR-HSA-01", "Onda 14 - HASSA", "Al Ahsa", "Hassa", wh_dmm.id),
        ("BR-DMM-05", "Onda 16 - Namjah", "Dammam", "Namjah", wh_dmm.id),
        ("BR-DMM-06", "Onda 18 - Al Midra Gym", "Dammam", "Al Midra Gym", wh_dmm.id),
        ("BR-DMM-07", "Onda 2 - HOQAIL", "Khobar", "Hoqail", wh_dmm.id),
        ("BR-RYD-07", "Onda 4 - SEFARAT", "Riyadh", "Sefarat", wh_ryd.id),
        ("BR-DMM-08", "Onda 5 - MUOWASAT", "Dammam", "Muowasat", wh_dmm.id),
        ("BR-RTN-01", "Onda 9 - Ras Tanura", "Ras Tanura", "Ras Tanura", wh_dmm.id),
        ("BR-DMM-09", "ONDA DAU University", "Khobar", "DAU University", wh_dmm.id),
        ("BR-KHB-02", "Pizza 1 - AlKHOBAR", "Khobar", "Al Khobar", wh_dmm.id),
        ("BR-DMM-10", "Pizza 10 - Mazaar", "Dammam", "Mazaar", wh_dmm.id),
        ("BR-RTN-02", "Pizza 15 - Ras Tanura", "Ras Tanura", "Ras Tanura", wh_dmm.id),
        ("BR-DMM-11", "Pizza 3 - Arkan", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-08", "Pizza 4 - Riyadh Takhasosy", "Riyadh", "Takhasosy", wh_ryd.id),
        ("BR-RYD-09", "Pizza 5 - ALULYA", "Riyadh", "Al Ulya", wh_ryd.id),
        ("BR-RYD-10", "Pizza 6 - Riyadh Nada", "Riyadh", "Al Nada", wh_ryd.id),
        ("BR-DMM-12", "Pizza 7 - Aramco", "Dhahran", "Aramco", wh_dmm.id),
        ("BR-KHB-03", "Pizza 9 - Al Azizia", "Khobar", "Al Azizia", wh_dmm.id),
        ("BR-DMM-13", "Ronaldos DAU University", "Khobar", "DAU University", wh_dmm.id),
        ("BR-KHB-04", "SHAWERMA - 1 - Khobar", "Khobar", "Khobar", wh_dmm.id),
        ("BR-DMM-14", "SHAWERMA - 4 - ARKAN", "Khobar", "Arkan", wh_dmm.id),
        ("BR-RYD-11", "SHAWERMA - OLAYA", "Riyadh", "Olaya", wh_ryd.id),
    ]
    db.query(Branch).filter(Branch.branch_code.in_(legacy_branch_codes)).update(
        {"active": False, "is_deleted": True},
        synchronize_session=False,
    )
    branches = {}
    for code, name, city, area, wh_id in branches_data:
        existing = db.query(Branch).filter(Branch.branch_code == code).first()
        if not existing:
            existing = Branch(branch_code=code, branch_name=name, city=city, area=area, warehouse_id=wh_id)
            db.add(existing)
            db.flush()
        else:
            existing.branch_name = name
            existing.city = city
            existing.area = area
            existing.warehouse_id = wh_id
            existing.active = True
            existing.is_deleted = False
        branches[code] = existing
    db.commit()
    print(f"âœ… Onda branches seeded: {len(branches)}")
    return branches


def seed_demo_users_onda(db: Session, roles: dict, branches: dict, warehouses: dict):
    users_data = [
        ("branch.mgr1", "br.mgr1@raed.com", "Onda Riyadh Kitchen Manager", "Raed@2025", RoleName.branch_manager, "BR-RYD-05", None),
        ("branch.user1", "br.user1@raed.com", "Onda Riyadh Kitchen User", "Raed@2025", RoleName.branch_user, "BR-RYD-05", None),
        ("branch.mgr2", "br.mgr2@raed.com", "Onda Arkan Branch Manager", "Raed@2025", RoleName.branch_manager, "BR-DMM-04", None),
        ("branch.user2", "br.user2@raed.com", "Onda Arkan Branch User", "Raed@2025", RoleName.branch_user, "BR-DMM-04", None),
        ("wh.mgr1", "wh.mgr1@raed.com", "Warehouse Manager Riyadh", "Raed@2025", RoleName.warehouse_manager, None, "WH-RYD"),
        ("wh.user1", "wh.user1@raed.com", "Warehouse User Riyadh", "Raed@2025", RoleName.warehouse_user, None, "WH-RYD"),
        ("ops.mgr", "ops.mgr@raed.com", "Operations Manager", "Raed@2025", RoleName.operations_manager, None, None),
    ]
    for username, email, name, password, role_name, br_code, wh_code in users_data:
        branch_id = branches[br_code].id if br_code and br_code in branches else None
        wh_id = warehouses[wh_code].id if wh_code and wh_code in warehouses else None
        existing = db.query(User).filter(User.username == username).first()
        if not existing:
            existing = User(
                username=username,
                email=email,
                full_name=name,
                hashed_password=get_password_hash(password),
                status="active",
                branch_id=branch_id,
                warehouse_id=wh_id,
            )
            db.add(existing)
            db.flush()
            role = roles.get(role_name)
            if role:
                db.add(UserRole(user_id=existing.id, role_id=role.id))
        else:
            existing.email = email
            existing.full_name = name
            existing.branch_id = branch_id
            existing.warehouse_id = wh_id
            existing.status = "active"
    db.commit()
    print("âœ… Onda demo users seeded")


def seed_items_onda(db: Session, categories: dict, units: dict):
    items_data = [
        ("ONDA-RAW-001", "حبوب قهوة أوندا بليند", "Onda House Blend Beans", "BEV", "KG", 5, 40, 10, 5, 5, True),
        ("ONDA-RAW-002", "حبوب قهوة إثيوبية", "Ethiopian Coffee Beans", "BEV", "KG", 3, 25, 6, 3, 5, True),
        ("ONDA-RAW-003", "حليب كامل الدسم", "Full Fat Milk", "DAIRY", "L", 20, 120, 35, 15, 1, True),
        ("ONDA-RAW-004", "حليب شوفان", "Oat Milk", "DAIRY", "L", 10, 80, 20, 10, 2, True),
        ("ONDA-RAW-005", "حليب لوز", "Almond Milk", "DAIRY", "L", 6, 50, 15, 8, 2, False),
        ("ONDA-RAW-006", "صوص فانيلا", "Vanilla Syrup", "SAUCE", "BTL", 6, 36, 10, 4, 3, False),
        ("ONDA-RAW-007", "صوص كراميل", "Caramel Syrup", "SAUCE", "BTL", 6, 36, 10, 4, 3, False),
        ("ONDA-RAW-008", "صوص بندق", "Hazelnut Syrup", "SAUCE", "BTL", 4, 24, 8, 3, 3, False),
        ("ONDA-RAW-009", "صلصة شوكولاتة", "Chocolate Sauce", "SAUCE", "BTL", 4, 24, 8, 3, 3, False),
        ("ONDA-RAW-010", "ماتشا بودرة", "Matcha Powder", "BEV", "KG", 1, 8, 2, 1, 7, True),
        ("ONDA-RAW-011", "شاي إيرل جراي", "Earl Grey Tea", "BEV", "BOX", 2, 12, 4, 2, 5, False),
        ("ONDA-RAW-012", "سكر أبيض", "White Sugar", "DRY", "KG", 8, 40, 12, 5, 4, False),
        ("ONDA-RAW-013", "أكواب ساخنة 12 أونص", "Hot Cups 12oz", "DISP", "BOX", 8, 50, 15, 6, 5, True),
        ("ONDA-RAW-014", "أكواب باردة 16 أونص", "Cold Cups 16oz", "DISP", "BOX", 8, 50, 15, 6, 5, True),
        ("ONDA-RAW-015", "أغطية أكواب", "Cup Lids", "DISP", "BOX", 8, 50, 15, 6, 5, True),
        ("ONDA-RAW-016", "شفاطات ورقية", "Paper Straws", "DISP", "BOX", 5, 30, 10, 4, 5, False),
        ("ONDA-RAW-017", "أكواب حلى", "Dessert Cups", "DISP", "BOX", 4, 20, 6, 3, 5, False),
        ("ONDA-PRD-001", "أوندا لاتيه", "Onda Latte", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-002", "سبانش لاتيه", "Spanish Latte", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-003", "كابتشينو", "Cappuccino", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-004", "أمريكانو", "Americano", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-005", "فلات وايت", "Flat White", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-006", "آيس لاتيه", "Iced Latte", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-007", "آيس سبانش لاتيه", "Iced Spanish Latte", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-008", "ماتشا لاتيه", "Matcha Latte", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-009", "موهيتو باشن فروت", "Passion Fruit Mojito", "BEV", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-010", "كروسان زبدة", "Butter Croissant", "DRY", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-011", "كوكيز شوكولاتة", "Chocolate Cookies", "DRY", "PCS", 0, 0, 0, 0, 0, False),
        ("ONDA-PRD-012", "تشيزكيك سان سيباستيان", "San Sebastian Cheesecake", "DRY", "PCS", 0, 0, 0, 0, 0, False),
    ]
    desired_codes = {item[0] for item in items_data}
    db.query(Item).filter(Item.item_code.notin_(desired_codes)).update(
        {"active": False, "is_deleted": True},
        synchronize_session=False,
    )
    for code, name_ar, name_en, cat_code, unit_code, mn, mx, rp, ss, lt, crit in items_data:
        cat = categories.get(cat_code)
        unit = units.get(unit_code)
        if not cat or not unit:
            continue
        existing = db.query(Item).filter(Item.item_code == code).first()
        if not existing:
            existing = Item(item_code=code)
            db.add(existing)
        existing.item_name_ar = name_ar
        existing.item_name_en = name_en
        existing.category_id = cat.id
        existing.unit_id = unit.id
        existing.branch_requestable = True
        existing.active = True
        existing.is_deleted = False
        existing.min_qty = Decimal(str(mn))
        existing.max_qty = Decimal(str(mx))
        existing.reorder_point = Decimal(str(rp))
        existing.safety_stock = Decimal(str(ss))
        existing.lead_time_days = lt
        existing.critical_item = crit
        existing.average_consumption_mode = AvgConsumptionMode.last_7_days
    db.commit()
    print(f"âœ… Onda items seeded: {len(items_data)}")


def run():
    print("\n🚀 Starting Raed Inventory System Seed...\n")
    create_tables()
    db = SessionLocal()
    try:
        roles = seed_roles(db)
        seed_admin_user(db, roles)
        warehouses = seed_warehouses(db)
        branches = seed_branches_onda(db, warehouses)
        seed_demo_users_onda(db, roles, branches, warehouses)
        categories = seed_categories(db)
        units = seed_units(db)
        seed_items_onda(db, categories, units)
        seed_variance_reasons(db)
        seed_system_settings(db)
        seed_initial_warehouse_stock(db, warehouses)
        from seed_onda_operations import main as seed_onda_operations_main
        seed_onda_operations_main()

        print("\n" + "="*60)
        print("✅ SEED COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\n📋 Demo Credentials:")
        print("  Admin:          admin / Admin@2025")
        print("  Branch Manager: branch.mgr1 / Raed@2025")
        print("  Branch User:    branch.user1 / Raed@2025")
        print("  WH Manager:     wh.mgr1 / Raed@2025")
        print("  WH User:        wh.user1 / Raed@2025")
        print("  Ops Manager:    ops.mgr / Raed@2025")
        print("\n🌐 API Docs: http://localhost:8000/api/docs")
        print("="*60 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
