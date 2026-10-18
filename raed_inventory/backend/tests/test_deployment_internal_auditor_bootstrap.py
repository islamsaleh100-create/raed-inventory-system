"""Deployment internal auditor bootstrap — credential from settings only."""
from __future__ import annotations

import secrets

import pytest

from app.core.security import get_password_hash, verify_password
from app.models import Role, RoleName, User, UserRole, UserStatus
from app.services.deployment_internal_auditor_service import (
    INTERNAL_AUDITOR_USERNAME,
    ensure_deployment_internal_auditor_user,
)

INTERNAL_AUDITOR_EMAIL = "audit@raed.com"


def _purge_auditor(db) -> None:
    user = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).first()
    if user:
        db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        db.delete(user)
        db.commit()


def _role(db, name: RoleName) -> Role:
    row = db.query(Role).filter(Role.name == name).first()
    if not row:
        row = Role(name=name, display_name=name.value, description="")
        db.add(row)
        db.flush()
    return row


def _seed_active_auditor(db, password: str) -> User:
    _purge_auditor(db)
    role = _role(db, RoleName.internal_auditor)
    user = User(
        username=INTERNAL_AUDITOR_USERNAME,
        email=INTERNAL_AUDITOR_EMAIL,
        full_name="Internal Auditor",
        hashed_password=get_password_hash(password),
        status=UserStatus.active,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def test_unset_disables_existing_and_old_password_fails(client, db, monkeypatch):
    old_password = "Aa1!" + secrets.token_urlsafe(12)
    user = _seed_active_auditor(db, old_password)
    prior_hash = user.hashed_password

    monkeypatch.setattr("app.services.deployment_internal_auditor_service.settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD", None)

    ensure_deployment_internal_auditor_user(db)

    db.refresh(user)
    assert user.status == UserStatus.inactive
    assert user.hashed_password != prior_hash
    assert not verify_password(old_password, user.hashed_password)

    login = client.post(
        "/api/v1/auth/login",
        json={"username": INTERNAL_AUDITOR_USERNAME, "password": old_password},
    )
    assert login.status_code in (401, 403)


def test_set_password_activates_and_login_works(client, db, monkeypatch):
    _purge_auditor(db)
    new_password = "Bb2!" + secrets.token_urlsafe(14)
    monkeypatch.setattr(
        "app.services.deployment_internal_auditor_service.settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD",
        new_password,
    )

    ensure_deployment_internal_auditor_user(db)

    user = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).one()
    assert user.status == UserStatus.active
    assert verify_password(new_password, user.hashed_password)
    roles = {ur.role.name for ur in user.user_roles}
    assert RoleName.internal_auditor in roles

    login = client.post(
        "/api/v1/auth/login",
        json={"username": INTERNAL_AUDITOR_USERNAME, "password": new_password},
    )
    assert login.status_code == 200, login.text
    assert "internal_auditor" in login.json()["user"]["roles"]


def test_unset_no_row_does_not_create(db, monkeypatch):
    _purge_auditor(db)
    monkeypatch.setattr("app.services.deployment_internal_auditor_service.settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD", None)
    before = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).count()
    assert before == 0

    ensure_deployment_internal_auditor_user(db)

    after = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).count()
    assert after == 0


def test_short_password_treated_as_unset(client, db, monkeypatch):
    old_password = "Aa1!" + secrets.token_urlsafe(12)
    user = _seed_active_auditor(db, old_password)
    monkeypatch.setattr(
        "app.services.deployment_internal_auditor_service.settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD",
        "short",
    )

    ensure_deployment_internal_auditor_user(db)

    db.refresh(user)
    assert user.status == UserStatus.inactive


def test_bootstrap_twice_idempotent(db, monkeypatch):
    _purge_auditor(db)
    password = "Cc3!" + secrets.token_urlsafe(14)
    monkeypatch.setattr(
        "app.services.deployment_internal_auditor_service.settings.DEPLOYMENT_INTERNAL_AUDITOR_PASSWORD",
        password,
    )

    ensure_deployment_internal_auditor_user(db)
    user = db.query(User).filter(User.username == INTERNAL_AUDITOR_USERNAME).one()
    first_hash = user.hashed_password
    first_id = user.id

    ensure_deployment_internal_auditor_user(db)
    db.refresh(user)

    assert user.id == first_id
    assert user.status == UserStatus.active
    assert verify_password(password, user.hashed_password)
    assert verify_password(password, first_hash)
