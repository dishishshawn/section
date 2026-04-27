"""
Unit tests for the consolidated permission helpers in backend/permissions.py.

Covers:
 - effective_project_role for owner / admin / editor / viewer / outsider / legacy-creator
 - cross-org ProjectAccess mismatch is ignored (tenant-isolation safety)
 - require_editor raises 403 for viewer; succeeds for editor/owner
 - user_accessible_project_ids is the union of ProjectAccess + org-membership + created_by
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import models
from permissions import (
    effective_project_role,
    require_editor,
    require_project_role,
    user_accessible_project_ids,
)


# ---------------------------------------------------------------------------
# effective_project_role across role classes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "user_key,expected",
    [
        ("owner", "owner"),      # explicit ProjectAccess row with role=owner
        ("editor", "editor"),    # explicit ProjectAccess row with role=editor
        ("viewer", "viewer"),    # explicit ProjectAccess row with role=viewer
        ("admin", "editor"),     # org admin (no PA row) → editor
        ("outsider", None),      # different org entirely → None
    ],
)
def test_effective_project_role_parametrized(db, seed, user_key, expected):
    user = seed[user_key]
    project = seed["project"]
    assert effective_project_role(db, user, project.id) == expected


def test_effective_project_role_legacy_creator(db, seed):
    """A project with org_id=None falls back to created_by → 'owner'."""
    # Create a legacy (personal) project with no org.
    legacy = models.Project(
        name="Legacy Personal",
        jurisdiction="TX",
        org_id=None,
        created_by=seed["outsider"].id,
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)

    assert effective_project_role(db, seed["outsider"], legacy.id) == "owner"
    # An unrelated user with no PA row and no shared org gets None.
    assert effective_project_role(db, seed["editor"], legacy.id) is None


def test_cross_org_project_access_is_ignored(db, seed):
    """
    Safety check: a ProjectAccess row whose org_id does not match the
    project's current org_id must not grant access. Closes the tenant-
    isolation gap noted in the task-4 review.
    """
    project = seed["project"]  # belongs to org_a
    outsider = seed["outsider"]  # only a member of org_b

    # Simulate a stale cross-org grant: PA row references org_b while the
    # project lives in org_a.
    db.add(
        models.ProjectAccess(
            user_id=outsider.id,
            project_id=project.id,
            org_id=seed["org_b"].id,  # mismatched with project.org_id
            role="editor",
            granted_by=seed["owner"].id,
        )
    )
    db.commit()

    # Despite the PA row, effective role must be None — we ignore mismatched
    # grants and fall through. Outsider is not a member of org_a.
    assert effective_project_role(db, outsider, project.id) is None


# ---------------------------------------------------------------------------
# require_editor / require_project_role
# ---------------------------------------------------------------------------

def test_require_editor_rejects_viewer():
    with pytest.raises(HTTPException) as exc:
        require_editor("viewer")
    assert exc.value.status_code == 403


def test_require_editor_rejects_none():
    with pytest.raises(HTTPException) as exc:
        require_editor(None)
    assert exc.value.status_code == 403


def test_require_editor_accepts_editor_and_owner():
    # Should not raise.
    require_editor("editor")
    require_editor("owner")


def test_require_project_role_outsider_gets_404(db, seed):
    with pytest.raises(HTTPException) as exc:
        require_project_role(db, seed["outsider"], seed["project"].id, "viewer")
    assert exc.value.status_code == 404


def test_require_project_role_viewer_cannot_edit(db, seed):
    with pytest.raises(HTTPException) as exc:
        require_project_role(db, seed["viewer"], seed["project"].id, "editor")
    assert exc.value.status_code == 403


def test_require_project_role_editor_succeeds(db, seed):
    role = require_project_role(db, seed["editor"], seed["project"].id, "editor")
    assert role == "editor"


# ---------------------------------------------------------------------------
# user_accessible_project_ids
# ---------------------------------------------------------------------------

def test_user_accessible_project_ids_union(db, seed):
    """
    The helper must union three sources:
      1. Explicit ProjectAccess rows
      2. Projects in orgs the user belongs to
      3. Projects where created_by == user.id (legacy/personal)
    """
    owner = seed["owner"]
    editor = seed["editor"]
    outsider = seed["outsider"]

    # Seed project is visible to owner/editor via explicit PA + org membership.
    seed_project_id = seed["project"].id

    # Add a legacy personal project created by outsider (no org).
    legacy = models.Project(
        name="Outsider Personal",
        jurisdiction="TX",
        org_id=None,
        created_by=outsider.id,
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)

    # Add a second org_a project (no explicit PA for editor) — editor should
    # still see it through org membership.
    second = models.Project(
        name="Second Org Project",
        jurisdiction="TX",
        org_id=seed["org_a"].id,
        created_by=owner.id,
    )
    db.add(second)
    db.commit()
    db.refresh(second)

    # Owner sees seed project + second (org membership + created_by).
    owner_ids = user_accessible_project_ids(db, owner)
    assert seed_project_id in owner_ids
    assert second.id in owner_ids
    assert legacy.id not in owner_ids

    # Editor sees seed project (PA) + second (via org membership).
    editor_ids = user_accessible_project_ids(db, editor)
    assert seed_project_id in editor_ids
    assert second.id in editor_ids
    assert legacy.id not in editor_ids

    # Outsider sees their legacy project (created_by) but not org_a projects.
    outsider_ids = user_accessible_project_ids(db, outsider)
    assert legacy.id in outsider_ids
    assert seed_project_id not in outsider_ids
    assert second.id not in outsider_ids
