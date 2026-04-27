"""
Repurpose 2 unused demo accounts to fit the 8-role operational model:

  branch.user1 (branch_user, موظف فرع العليا)
      → branch_manager, مدير فرع الملز, branch BR-RYD-MALAZ (created if missing)

  wh.user1     (warehouse_user, موظف مستودع الرياض)
      → warehouse_manager, مدير مستودع الدمام, warehouse WH-DMM

Idempotent — safe to run multiple times. Detects already-migrated state.

Run from backend/:
    python repurpose_demo_accounts.py
"""
from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName, Branch, Warehouse


MALAZ_BRANCH_CODE = "BR-RYD-MALAZ"
MALAZ_BRANCH_NAME = "فرع الملز"
MALAZ_CITY = "الرياض"
MALAZ_AREA = "الملز"

DAMMAM_WAREHOUSE_CODE = "WH-DMM"
RIYADH_WAREHOUSE_CODE = "WH-RYD"


def ensure_malaz_branch(db):
    """Create BR-RYD-MALAZ if missing, linked to Riyadh warehouse."""
    br = db.query(Branch).filter(Branch.branch_code == MALAZ_BRANCH_CODE).first()
    if br:
        print(f"  ✓ Branch {MALAZ_BRANCH_CODE} already exists (id={br.id})")
        return br

    wh_ryd = db.query(Warehouse).filter(
        Warehouse.warehouse_code == RIYADH_WAREHOUSE_CODE
    ).first()
    if not wh_ryd:
        print(f"  ! Riyadh warehouse {RIYADH_WAREHOUSE_CODE} missing — cannot create Malaz")
        return None

    br = Branch(
        branch_code=MALAZ_BRANCH_CODE,
        branch_name=MALAZ_BRANCH_NAME,
        city=MALAZ_CITY,
        area=MALAZ_AREA,
        warehouse_id=wh_ryd.id,
    )
    db.add(br)
    db.flush()
    print(f"  + Created branch {MALAZ_BRANCH_CODE} (id={br.id}) linked to WH-RYD")
    return br


def swap_role(db, user, new_role_name):
    """Remove all old role links and add only the new one."""
    new_role = db.query(Role).filter(Role.name == new_role_name).first()
    if not new_role:
        print(f"  ! Role {new_role_name.value} not found — skipping swap")
        return False

    # Drop existing role links for this user
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    db.flush()

    db.add(UserRole(user_id=user.id, role_id=new_role.id))
    return True


def repurpose_branch_user1(db):
    user = db.query(User).filter(User.username == "branch.user1").first()
    if not user:
        print("  ! branch.user1 not found — skipping")
        return

    malaz = ensure_malaz_branch(db)
    if not malaz:
        return

    already_manager = (
        db.query(UserRole)
        .join(Role)
        .filter(UserRole.user_id == user.id, Role.name == RoleName.branch_manager)
        .first()
        is not None
    )

    if already_manager and user.branch_id == malaz.id and user.full_name == "مدير فرع الملز":
        print("  ✓ branch.user1 already repurposed (skipped)")
        return

    swap_role(db, user, RoleName.branch_manager)
    user.full_name = "مدير فرع الملز"
    user.branch_id = malaz.id
    user.warehouse_id = None
    print(f"  + branch.user1 → branch_manager @ {MALAZ_BRANCH_CODE} (مدير فرع الملز)")


def repurpose_wh_user1(db):
    user = db.query(User).filter(User.username == "wh.user1").first()
    if not user:
        print("  ! wh.user1 not found — skipping")
        return

    wh_dmm = db.query(Warehouse).filter(
        Warehouse.warehouse_code == DAMMAM_WAREHOUSE_CODE
    ).first()
    if not wh_dmm:
        print(f"  ! Dammam warehouse {DAMMAM_WAREHOUSE_CODE} missing — skipping")
        return

    already_manager = (
        db.query(UserRole)
        .join(Role)
        .filter(UserRole.user_id == user.id, Role.name == RoleName.warehouse_manager)
        .first()
        is not None
    )

    if already_manager and user.warehouse_id == wh_dmm.id and user.full_name == "مدير مستودع الدمام":
        print("  ✓ wh.user1 already repurposed (skipped)")
        return

    swap_role(db, user, RoleName.warehouse_manager)
    user.full_name = "مدير مستودع الدمام"
    user.warehouse_id = wh_dmm.id
    user.branch_id = None
    print(f"  + wh.user1 → warehouse_manager @ {DAMMAM_WAREHOUSE_CODE} (مدير مستودع الدمام)")


def main():
    db = SessionLocal()
    try:
        print("Repurposing unused demo accounts…")
        repurpose_branch_user1(db)
        repurpose_wh_user1(db)
        db.commit()
        print("\n✅ Done.")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
