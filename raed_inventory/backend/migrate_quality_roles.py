"""
Migrate users with quality_visitor or trainer roles to quality_manager.

Safe to run multiple times — idempotent.
Run from backend/ directory:
    python migrate_quality_roles.py

Reports: number of users affected and preview of changes.
"""
from app.database import SessionLocal
from app.models import User, Role, UserRole, RoleName


OLD_ROLES = [RoleName.quality_visitor, RoleName.trainer]
NEW_ROLE = RoleName.quality_manager


def main():
    db = SessionLocal()
    try:
        # Find the target quality_manager role record
        target_role = db.query(Role).filter(Role.name == NEW_ROLE).first()
        if target_role is None:
            print("ERROR: quality_manager role not found in roles table.")
            return

        # Find all UserRole rows with the old roles
        old_role_records = db.query(Role).filter(Role.name.in_(OLD_ROLES)).all()
        if not old_role_records:
            print("No quality_visitor or trainer role records found. Nothing to do.")
            return

        old_role_ids = [r.id for r in old_role_records]

        affected = (
            db.query(UserRole)
            .filter(UserRole.role_id.in_(old_role_ids))
            .all()
        )

        if not affected:
            print("No users with quality_visitor or trainer roles. Nothing to migrate.")
            return

        print(f"Found {len(affected)} user-role records to migrate.")
        print("\nPreview:")
        for ur in affected:
            user = db.query(User).filter(User.id == ur.user_id).first()
            old_role = db.query(Role).filter(Role.id == ur.role_id).first()
            if user:
                print(f"  - {user.username} ({user.full_name}): {old_role.name.value} -> quality_manager")

        confirm = input("\nProceed with migration? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return

        migrated = 0
        skipped = 0
        for ur in affected:
            # If the user already has quality_manager, just delete the old UserRole
            already_qm = (
                db.query(UserRole)
                .filter(
                    UserRole.user_id == ur.user_id,
                    UserRole.role_id == target_role.id,
                )
                .first()
            )
            if already_qm:
                db.delete(ur)
                skipped += 1
            else:
                ur.role_id = target_role.id
                migrated += 1

        db.commit()
        print(f"\nDone. {migrated} reassigned, {skipped} duplicates removed (user already had quality_manager).")

    finally:
        db.close()


if __name__ == "__main__":
    main()
