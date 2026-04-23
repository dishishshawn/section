"""
Resolved-fact read layer.

Every piece of extracted data goes through resolved_data() before being
used in a route response. If a human has overridden a field, the override
wins; otherwise the LLM-extracted value is returned unchanged.

Usage:
    data = resolved_data(db, "instrument", inst.id, inst.extracted_data)
    grantor = data.get("grantor") or data.get("lessor") or ""
"""

from typing import Any
from sqlalchemy.orm import Session
from models import FactOverride


def resolved_data(
    db: Session,
    entity_type: str,
    entity_id: int,
    extracted: Any,
) -> dict:
    """
    Merge latest FactOverride rows on top of extracted_data.
    Returns a plain dict safe for .get() calls.
    """
    base: dict = extracted if isinstance(extracted, dict) else {}

    overrides = (
        db.query(FactOverride)
        .filter(
            FactOverride.entity_type == entity_type,
            FactOverride.entity_id == entity_id,
        )
        .order_by(FactOverride.changed_at.asc())
        .all()
    )

    if not overrides:
        return base

    merged = dict(base)
    seen: set[str] = set()
    # Iterate ascending so last write wins (most recent override is authoritative)
    for ov in overrides:
        merged[ov.field_name] = ov.new_value
        seen.add(ov.field_name)

    # Tag which fields have been reviewed so callers can surface provenance badges
    if seen:
        merged["_reviewed_fields"] = {
            ov.field_name: {
                "new_value": ov.new_value,
                "old_value": ov.old_value,
                "user_display": ov.user_display,
                "changed_at": ov.changed_at.isoformat() if ov.changed_at else None,
                "reason": ov.reason,
            }
            for ov in overrides
            # Keep only the most-recent override per field
        }

    return merged


def get_provenance(merged: dict, field: str) -> dict | None:
    """Return review metadata for a field if it was overridden, else None."""
    reviewed = merged.get("_reviewed_fields") or {}
    return reviewed.get(field)
