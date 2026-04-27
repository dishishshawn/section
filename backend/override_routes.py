"""
PATCH endpoints for human-in-the-loop fact corrections.

Each endpoint writes a FactOverride row and returns the resolved entity
so the frontend can optimistically update without a separate GET.

Allowlisted fields prevent writes to internal/structural columns.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from facts import resolved_data
from models import FactOverride, Instrument, Interest, Obligation, Party, User, Tract
from permissions import (
    effective_project_role as _effective_project_role,
    require_project_role,
)

router = APIRouter(prefix="/api", tags=["overrides"])


def _require_editor(db: Session, user: User, project_id: int):
    """Gate PATCH endpoints: must have editor or owner role on the project."""
    require_project_role(db, user, project_id, "editor")

INSTRUMENT_FIELDS = {
    "grantor", "grantee", "lessor", "lessee",
    "date", "legal_description", "royalty", "type",
    "book", "page", "volume", "recording_number",
}

INTEREST_FIELDS = {
    "fraction_numerator", "fraction_denominator",
    "mineral_estate", "burdens",
}

PARTY_FIELDS = {"name", "type"}

OBLIGATION_FIELDS = {"description", "type"}


class OverrideBody(BaseModel):
    new_value: str
    reason: str | None = None


def _write_override(
    db: Session,
    user: User,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value: str | None,
    new_value: str,
    reason: str | None,
) -> FactOverride:
    ov = FactOverride(
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        user_id=user.id,
        user_display=user.display_name or user.email,
        reason=reason,
        changed_at=datetime.utcnow(),
    )
    db.add(ov)
    db.commit()
    db.refresh(ov)
    return ov


@router.patch("/instruments/{instrument_id}/fields/{field_name}")
def patch_instrument_field(
    instrument_id: int,
    field_name: str,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if field_name not in INSTRUMENT_FIELDS:
        raise HTTPException(status_code=422, detail=f"Field '{field_name}' is not editable")

    inst = db.query(Instrument).filter(Instrument.id == instrument_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")
    _require_editor(db, user, inst.project_id)

    current = resolved_data(db, "instrument", instrument_id, inst.extracted_data)
    old_value = str(current.get(field_name, "")) or None

    ov = _write_override(db, user, "instrument", instrument_id, field_name, old_value, body.new_value, body.reason)

    resolved = resolved_data(db, "instrument", instrument_id, inst.extracted_data)
    return {
        "entity_type": "instrument",
        "entity_id": instrument_id,
        "field": field_name,
        "value": body.new_value,
        "override_id": ov.id,
        "user_display": ov.user_display,
        "changed_at": ov.changed_at.isoformat(),
        "resolved": resolved,
    }


@router.patch("/interests/{interest_id}/fields/{field_name}")
def patch_interest_field(
    interest_id: int,
    field_name: str,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if field_name not in INTEREST_FIELDS:
        raise HTTPException(status_code=422, detail=f"Field '{field_name}' is not editable")

    interest = db.query(Interest).filter(Interest.id == interest_id).first()
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")
    tract = db.query(Tract).filter(Tract.id == interest.tract_id).first()
    if not tract:
        raise HTTPException(status_code=404, detail="Tract not found")
    _require_editor(db, user, tract.project_id)

    # Interests store values as columns, not JSON — read the current column value
    old_value = str(getattr(interest, field_name, "")) or None

    ov = _write_override(db, user, "interest", interest_id, field_name, old_value, body.new_value, body.reason)

    return {
        "entity_type": "interest",
        "entity_id": interest_id,
        "field": field_name,
        "value": body.new_value,
        "override_id": ov.id,
        "user_display": ov.user_display,
        "changed_at": ov.changed_at.isoformat(),
    }


@router.patch("/parties/{party_id}/fields/{field_name}")
def patch_party_field(
    party_id: int,
    field_name: str,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if field_name not in PARTY_FIELDS:
        raise HTTPException(status_code=422, detail=f"Field '{field_name}' is not editable")

    party = db.query(Party).filter(Party.id == party_id).first()
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    _require_editor(db, user, party.project_id)

    old_value = str(getattr(party, field_name, "")) or None

    ov = _write_override(db, user, "party", party_id, field_name, old_value, body.new_value, body.reason)

    return {
        "entity_type": "party",
        "entity_id": party_id,
        "field": field_name,
        "value": body.new_value,
        "override_id": ov.id,
        "user_display": ov.user_display,
        "changed_at": ov.changed_at.isoformat(),
    }


@router.patch("/obligations/{obligation_id}/fields/{field_name}")
def patch_obligation_field(
    obligation_id: int,
    field_name: str,
    body: OverrideBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if field_name not in OBLIGATION_FIELDS:
        raise HTTPException(status_code=422, detail=f"Field '{field_name}' is not editable")

    obl = db.query(Obligation).filter(Obligation.id == obligation_id).first()
    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found")
    _require_editor(db, user, obl.project_id)

    params = obl.params if isinstance(obl.params, dict) else {}
    if field_name == "description":
        old_value = params.get("description") or None
    else:
        old_value = str(getattr(obl, field_name, "")) or None

    ov = _write_override(db, user, "obligation", obligation_id, field_name, old_value, body.new_value, body.reason)

    return {
        "entity_type": "obligation",
        "entity_id": obligation_id,
        "field": field_name,
        "value": body.new_value,
        "override_id": ov.id,
        "user_display": ov.user_display,
        "changed_at": ov.changed_at.isoformat(),
    }


@router.get("/projects/{project_id}/audit")
def get_audit_log(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All overrides for instruments and interests belonging to this project."""
    role = _effective_project_role(db, user, project_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    from models import Instrument as Inst, Interest as Int, Tract, Party as Par, Obligation as Obl

    instrument_ids = [r[0] for r in db.query(Inst.id).filter(Inst.project_id == project_id).all()]
    tract_ids = [r[0] for r in db.query(Tract.id).filter(Tract.project_id == project_id).all()]
    interest_ids = [r[0] for r in db.query(Int.id).filter(Int.tract_id.in_(tract_ids)).all()]
    party_ids = [r[0] for r in db.query(Par.id).filter(Par.project_id == project_id).all()]
    obligation_ids = [r[0] for r in db.query(Obl.id).filter(Obl.project_id == project_id).all()]

    overrides = (
        db.query(FactOverride)
        .filter(
            ((FactOverride.entity_type == "instrument") & (FactOverride.entity_id.in_(instrument_ids))) |
            ((FactOverride.entity_type == "interest") & (FactOverride.entity_id.in_(interest_ids))) |
            ((FactOverride.entity_type == "party") & (FactOverride.entity_id.in_(party_ids))) |
            ((FactOverride.entity_type == "obligation") & (FactOverride.entity_id.in_(obligation_ids)))
        )
        .order_by(FactOverride.changed_at.desc())
        .all()
    )

    return {
        "project_id": project_id,
        "entries": [
            {
                "id": ov.id,
                "entity_type": ov.entity_type,
                "entity_id": ov.entity_id,
                "field": ov.field_name,
                "old_value": ov.old_value,
                "new_value": ov.new_value,
                "user_display": ov.user_display,
                "reason": ov.reason,
                "changed_at": ov.changed_at.isoformat() if ov.changed_at else None,
            }
            for ov in overrides
        ],
    }
