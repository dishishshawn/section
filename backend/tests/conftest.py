"""
Shared test fixtures:
 - in-memory SQLite (StaticPool) so FastAPI TestClient threads share the DB
 - DB dependency override on the FastAPI app
 - seeded users (owner, admin, editor, viewer, outsider)
 - seeded orgs (org_a, org_b)
 - project in org_a with 1 instrument / 1 interest / 1 party / 1 tract
 - authenticated_client(user) factory that sets the section_session cookie
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make `backend/` importable when running pytest from repo root or from backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Deterministic secret so session cookies are signed consistently across the test run.
os.environ.setdefault("SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault("APP_URL", "http://localhost:3000")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000,http://testserver")

import database  # noqa: E402
import models  # noqa: E402
import auth  # noqa: E402


@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture(scope="function")
def TestSession(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db(TestSession):
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="function")
def app(TestSession):
    """FastAPI app with get_db overridden to return a session on the test engine."""
    # Import here so the app is built only once env is configured.
    import main  # noqa: WPS433

    def _get_db_override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    main.app.dependency_overrides[database.get_db] = _get_db_override
    try:
        yield main.app
    finally:
        main.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    c = TestClient(app)
    # CSRF guard requires Origin to match ALLOWED_ORIGINS on state-changing
    # requests that carry a session cookie.
    c.headers.update({"Origin": "http://testserver"})
    return c


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def seed(db):
    """
    Seed the database with a small multi-tenant fixture:
      orgs:   org_a, org_b
      users:  owner, admin, editor, viewer, outsider
      project (in org_a) with: 1 tract, 1 party, 1 instrument, 1 interest
    """
    org_a = models.Organization(name="Org A", slug="org-a", billing_status="active")
    org_b = models.Organization(name="Org B", slug="org-b", billing_status="active")
    db.add_all([org_a, org_b])
    db.flush()

    def mk_user(email, name):
        u = models.User(email=email, display_name=name, session_version=0)
        db.add(u)
        return u

    owner = mk_user("owner@a.test", "Owner A")
    admin = mk_user("admin@a.test", "Admin A")
    editor = mk_user("editor@a.test", "Editor A")
    viewer = mk_user("viewer@a.test", "Viewer A")
    outsider = mk_user("outsider@b.test", "Outsider B")
    db.flush()

    # Org memberships
    db.add_all([
        models.OrgMembership(user_id=owner.id, org_id=org_a.id, role="owner"),
        models.OrgMembership(user_id=admin.id, org_id=org_a.id, role="admin"),
        models.OrgMembership(user_id=editor.id, org_id=org_a.id, role="member"),
        models.OrgMembership(user_id=viewer.id, org_id=org_a.id, role="member"),
        models.OrgMembership(user_id=outsider.id, org_id=org_b.id, role="owner"),
    ])
    db.flush()

    project = models.Project(
        name="Test Project",
        jurisdiction="TX",
        org_id=org_a.id,
        created_by=owner.id,
    )
    db.add(project)
    db.flush()

    # Explicit ProjectAccess rows so editor/viewer get the expected roles.
    db.add_all([
        models.ProjectAccess(user_id=owner.id, project_id=project.id,
                             org_id=org_a.id, role="owner", granted_by=owner.id),
        models.ProjectAccess(user_id=editor.id, project_id=project.id,
                             org_id=org_a.id, role="editor", granted_by=owner.id),
        models.ProjectAccess(user_id=viewer.id, project_id=project.id,
                             org_id=org_a.id, role="viewer", granted_by=owner.id),
    ])

    tract = models.Tract(
        project_id=project.id,
        legal_description="Section 1, T1N R1E",
        gross_acres=640.0,
    )
    party = models.Party(project_id=project.id, name="Acme Minerals", type="entity")
    db.add_all([tract, party])
    db.flush()

    instrument = models.Instrument(
        project_id=project.id,
        type="deed",
        recorded_at=datetime(2024, 1, 15),
        extracted_data={
            "grantor": "Acme Minerals",
            "grantee": "John Doe",
            "legal_description": "Section 1, T1N R1E",
        },
    )
    db.add(instrument)
    db.flush()

    interest = models.Interest(
        tract_id=tract.id,
        party_id=party.id,
        fraction_numerator=1,
        fraction_denominator=2,
        mineral_estate="mineral",
    )
    db.add(interest)
    db.commit()

    return {
        "org_a": org_a,
        "org_b": org_b,
        "owner": owner,
        "admin": admin,
        "editor": editor,
        "viewer": viewer,
        "outsider": outsider,
        "project": project,
        "tract": tract,
        "party": party,
        "instrument": instrument,
        "interest": interest,
    }


# ---------------------------------------------------------------------------
# Authenticated client factory
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def authenticated_client(app):
    """
    Factory: pass a user (ORM object) and get back a TestClient with a valid
    section_session cookie set. Uses the real cookie serializer so the auth
    dependency exercises the production code path.
    """
    def _make(user):
        cookie = auth.make_session_cookie(user.id, user.session_version or 0)
        c = TestClient(app)
        c.cookies.set("section_session", cookie)
        c.headers.update({"Origin": "http://testserver"})
        return c
    return _make
