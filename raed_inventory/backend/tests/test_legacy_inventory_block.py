"""موديول الجرد القديم محجوب عن مدير الفرع.

اعتماد أي جرد في الموديول القديم ينادي
`replenishment_service.generate_replenishment_order()` تلقائيًا
(`services/inventory_service.py:210`)، و`ReplenishmentOrder.warehouse_id` إجباري.

منذ 2026-08-15 أصبح `branch_manager` هو الدور التشغيلي الوحيد على مستوى الفرع، فبقاؤه في
`_APPROVAL_ROLES` كان يعني أن الفرع يستطيع توليد أمر مستودع بنداء API مباشر — حتى بعد إخفاء
الشاشة من الواجهة. إخفاء المسار ليس حجبًا للـAPI.
"""
from app.core.security import get_password_hash
from app.models import Role, RoleName, User, UserRole

PASSWORD = "Pass@2026"
GUARDED = ("approve", "reject", "trigger-replenishment")


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _user(db, username: str, role_name: RoleName) -> User:
    role = _role(db, role_name)
    row = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(PASSWORD),
        status="active",
        is_deleted=False,
    )
    db.add(row)
    db.flush()
    db.add(UserRole(user_id=row.id, role_id=role.id))
    db.commit()
    return row


def _auth(client, username: str) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_branch_manager_cannot_reach_legacy_approval_endpoints(db, client):
    """403 على كل مسار محروس — قبل أي تحقق من وجود الجرد نفسه."""
    _user(db, "legacy_brmgr", RoleName.branch_manager)
    hdr = _auth(client, "legacy_brmgr")

    for action in GUARDED:
        resp = client.post(f"/api/v1/inventory/1/{action}", headers=hdr)
        assert resp.status_code == 403, (
            f"{action}: توقّعنا 403 لمدير الفرع، وجاء {resp.status_code} — "
            f"الموديول القديم ما زال مفتوحًا للفرع"
        )


def test_admin_is_not_blocked_by_the_change(db, client):
    """الإدارة لم تفقد الصلاحية. 404/422 مقبول (الجرد غير موجود)، 403 ليس مقبولًا."""
    _user(db, "legacy_admin", RoleName.admin)
    hdr = _auth(client, "legacy_admin")

    for action in GUARDED:
        resp = client.post(f"/api/v1/inventory/1/{action}", headers=hdr)
        assert resp.status_code != 403, (
            f"{action}: صلاحية الإدارة انكسرت — رجع 403"
        )


def test_branch_roles_for_data_entry_are_untouched(db, client):
    """`_BRANCH_ROLES` لم تُمس: الإنشاء والترحيل لا يولّدان أمر تجديد، فلا مبرر لتضييقهما."""
    from app.routers import inventory as legacy

    assert "branch_manager" in legacy._BRANCH_ROLES
    assert "branch_user" in legacy._BRANCH_ROLES
    assert "branch_manager" not in legacy._APPROVAL_ROLES
    assert legacy._APPROVAL_ROLES == ("admin", "super_admin")
