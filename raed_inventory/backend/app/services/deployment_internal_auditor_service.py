import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.database import engine
from app.models import Role, RoleName, User, UserRole, UserStatus

logger = logging.getLogger(__name__)

INTERNAL_AUDITOR_USERNAME = "audit.officer"
INTERNAL_AUDITOR_EMAIL = "audit@raed.com"
INTERNAL_AUDITOR_FULL_NAME = "Internal Auditor"
INTERNAL_AUDITOR_PASSWORD = "Raed@2025"


def _ensure_internal_auditor_enum_value(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ALTER TYPE rolename ADD VALUE IF NOT EXISTS 'internal_auditor'"))


def ensure_deployment_internal_auditor_user(db: Session) -> User | None:
    """
    Ensure the production internal auditor account exists and remains usable.

    Railway deployments need this account to be reconciled the same way as the
    deployment admin because seed scripts are not part of container startup.
    """
    try:
        _ensure_internal_auditor_enum_value(db)

        role = db.query(Role).filter(Role.name == RoleName.internal_auditor).first()
        if not role:
            role = Role(
                name=RoleName.internal_auditor,
                display_name="Internal Auditor",
                description="Read-only audit oversight with finding creation",
            )
            db.add(role)
            db.flush()

        user = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).first()
        if not user:
            user = User(
                username=INTERNAL_AUDITOR_USERNAME,
                email=INTERNAL_AUDITOR_EMAIL,
                full_name=INTERNAL_AUDITOR_FULL_NAME,
                hashed_password=get_password_hash(INTERNAL_AUDITOR_PASSWORD),
                status=UserStatus.active,
                is_deleted=False,
            )
            db.add(user)
            db.flush()
            logger.info("Deployment internal auditor user created: %s", INTERNAL_AUDITOR_USERNAME)
        else:
            user.email = INTERNAL_AUDITOR_EMAIL
            user.full_name = user.full_name or INTERNAL_AUDITOR_FULL_NAME
            user.hashed_password = get_password_hash(INTERNAL_AUDITOR_PASSWORD)
            user.status = UserStatus.active
            user.is_deleted = False
            logger.info("Deployment internal auditor user refreshed: %s", INTERNAL_AUDITOR_USERNAME)

        existing_link = (
            db.query(UserRole)
            .filter(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
            .first()
        )
        if not existing_link:
            db.add(UserRole(user_id=user.id, role_id=role.id))

        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        logger.exception("Deployment internal auditor bootstrap failed")
        return None
