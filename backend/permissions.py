"""
Consolidated project/org permission helpers.

Previously `_effective_project_role`, `_user_accessible_project_ids`, and the
various role-guard helpers were duplicated across routes.py and
override_routes.py, which drifted over time. This module is the single source
of truth.

Behavior preserved from the pre-refactor helpers:
 - ProjectAccess (explicit per-user-per-project role) wins when present.
 - Org admin/owner map to project "editor"; org member maps to "viewer".
 - Legacy projects with no org_id fall back to `project.created_by == user.id`
   yielding "owner".

Safety improvement (closes the tenant-isolation gap noted in the task-4
review): if a ProjectAccess row's org_id does not match the project's org_id,
we treat it as no access. This prevents a stale cross-org grant from leaking
visibility.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import OrgMembership, Project, ProjectAccess, User


PROJECT_ROLE_RANK = {"owner": 3, "editor": 2, "viewer": 1}
ORG_ROLE_RANK = {"owner": 3, "admin": 2, "member": 1}


def effective_project_role(
    db: Session, user: User, project: int | Project
) -> Optional[str]:
    """
    Return the caller's effective role on the project, or None if no access.

    `project` may be a Project instance or a project_id (int) — callers in the
    codebase pass either.
    """
    if isinstance(project, Project):
        project_obj = project
        project_id = project.id
    else:
        project_id = int(project)
        project_obj = db.query(Project).filter(Project.id == project_id).first()

    pa = (
        db.query(ProjectAccess)
        .filter(
            ProjectAccess.user_id == user.id,
            ProjectAccess.project_id == project_id,
        )
        .first()
    )
    if pa:
        # Cross-org safety: if the ProjectAccess row references a different
        # org than the project currently belongs to, ignore it. Closes a
        # tenant-isolation gap where a stale grant could persist after a
        # project was reassigned.
        proj_org_id = project_obj.org_id if project_obj else None
        if pa.org_id is not None and proj_org_id is not None and pa.org_id != proj_org_id:
            pass  # fall through to org-membership lookup
        else:
            return pa.role

    if not project_obj or not project_obj.org_id:
        # Legacy projects without org: allow creator through.
        if project_obj and project_obj.created_by == user.id:
            return "owner"
        return None

    m = (
        db.query(OrgMembership)
        .filter(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == project_obj.org_id,
        )
        .first()
    )
    if not m:
        return None
    if m.role in ("owner", "admin"):
        return "editor"
    return "viewer"


def user_accessible_project_ids(db: Session, user: User) -> set[int]:
    """
    Projects the user can see, unioned from:
      - explicit ProjectAccess rows
      - membership in an organization that owns projects
      - legacy `created_by` projects (no org)
    """
    explicit_ids = {
        r[0]
        for r in db.query(ProjectAccess.project_id)
        .filter(ProjectAccess.user_id == user.id)
        .all()
    }

    org_ids = [
        r[0]
        for r in db.query(OrgMembership.org_id)
        .filter(OrgMembership.user_id == user.id)
        .all()
    ]
    if org_ids:
        org_project_ids = {
            r[0]
            for r in db.query(Project.id)
            .filter(Project.org_id.in_(org_ids))
            .all()
        }
    else:
        org_project_ids = set()

    created_ids = {
        r[0]
        for r in db.query(Project.id)
        .filter(Project.created_by == user.id)
        .all()
    }

    return explicit_ids | org_project_ids | created_ids


def require_viewer(role: Optional[str]) -> None:
    """Raise 403 if the role is None (no access at all)."""
    if role is None:
        raise HTTPException(status_code=403, detail="Requires project access")


def require_editor(role: Optional[str]) -> None:
    """Raise 403 unless the role is editor or owner."""
    if role not in ("editor", "owner"):
        raise HTTPException(status_code=403, detail="Requires 'editor' access on this project")


def require_project_role(
    db: Session, user: User, project: int | Project, min_role: str = "viewer"
) -> str:
    """
    Resolve the caller's effective role and gate on `min_role`.
    - Returns the role string on success.
    - Raises 404 when no access at all (mirrors existing behavior so we don't
      leak project existence to outsiders).
    - Raises 403 when the role is insufficient.
    """
    role = effective_project_role(db, user, project)
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if PROJECT_ROLE_RANK.get(role, 0) < PROJECT_ROLE_RANK.get(min_role, 0):
        raise HTTPException(
            status_code=403,
            detail=f"Requires '{min_role}' access on this project",
        )
    return role


def require_org_role(
    db: Session, user: User, org_id: int, min_role: str = "member"
) -> str:
    """
    Gate on organization-level role. Returns the role string on success.
    Raises 403 on missing membership or insufficient rank.
    """
    m = (
        db.query(OrgMembership)
        .filter(OrgMembership.user_id == user.id, OrgMembership.org_id == org_id)
        .first()
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of that organization")
    if ORG_ROLE_RANK.get(m.role, 0) < ORG_ROLE_RANK.get(min_role, 0):
        raise HTTPException(
            status_code=403,
            detail=f"Requires '{min_role}' access on this organization",
        )
    return m.role
