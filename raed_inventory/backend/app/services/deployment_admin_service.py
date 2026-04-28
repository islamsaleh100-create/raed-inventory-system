import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.models import Role, RoleName, User, UserRole

logger = logging.getLogger(__name__)


def ensure_deployment_admin_user(db: Session) -> User | None:
    """
    Ensure a canonical deployment admin user exists and has the configured
    username, email, password, and super_admin role.

    This is used both during startup and as a safety net during login if the
    deployment admin credentials drift from what Railway currently provides.
    """
    try:
        super_admin_role = db.query(Role).filter(Role.name == RoleName.super_admin).first()
        if not super_admin_role:
            super_admin_role = Role(
                name=RoleName.super_admin,
                display_name="Super Administrator",
                description="Full system access",
            )
            db.add(super_admin_role)
            db.flush()

        matching_users = (
            db.query(User)
            .filter(
                or_(
                    User.username == settings.ADMIN_USERNAME,
                    User.email == settings.ADMIN_EMAIL,
                )
            )
            .order_by(User.id.asc())
            .all()
        )

        def _priority(user: User) -> tuple[int, int]:
            return (
                0 if user.username == settings.ADMIN_USERNAME and user.email == settings.ADMIN_EMAIL else
                1 if user.username == settings.ADMIN_USERNAME else
                2 if user.email == settings.ADMIN_EMAIL else
                3,
                user.id,
            )

        matching_users.sort(key=_priority)
        admin_user = matching_users[0] if matching_users else None
        if not admin_user:
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                full_name="System Administrator",
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                status="active",
                is_deleted=False,
            )
            db.add(admin_user)
            db.flush()
            logger.info("Deployment admin user created: %s", settings.ADMIN_USERNAME)
        else:
            # Archive duplicates first so the canonical admin can safely claim
            # the configured username/email without hitting unique constraints.
            for duplicate in matching_users[1:]:
                duplicate.is_deleted = True
                if duplicate.username:
                    duplicate.username = f"{duplicate.username}__archived__{duplicate.id}"
                if duplicate.email:
                    duplicate.email = f"{duplicate.id}__archived__{duplicate.email}"
                logger.warning("Deployment admin duplicate archived: user_id=%s", duplicate.id)

            if len(matching_users) > 1:
                db.flush()

            admin_user.username = settings.ADMIN_USERNAME
            admin_user.email = settings.ADMIN_EMAIL
            admin_user.full_name = admin_user.full_name or "System Administrator"
            admin_user.status = "active"
            admin_user.is_deleted = False
            admin_user.hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
            logger.info("Deployment admin user refreshed: %s", settings.ADMIN_USERNAME)

        existing_link = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == admin_user.id,
                UserRole.role_id == super_admin_role.id,
            )
            .first()
        )
        if not existing_link:
            db.add(UserRole(user_id=admin_user.id, role_id=super_admin_role.id))

        db.commit()
        db.refresh(admin_user)
        return admin_user
    except Exception:
        db.rollback()
        logger.exception("Deployment admin bootstrap failed")
        return None
