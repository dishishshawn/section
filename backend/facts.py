"""
Resolved-fact read layer.

Every piece of extracted data goes through resolved_data() before being
used in a route response. If a human has overridden a field, the override
wins; otherwise the LLM-extracted value is returned unchanged.

Usage:
    data = resolved_data(db, "instrument", inst.id, inst.extracted_data)
    grantor = data.get("grantor") or data.get("lessor") or ""
"""

from typing import Any, Iterable
from collections import defaultdict
from sqlalchemy import and_, or_
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


def resolved_data_many(
    db: Session,
    requests: Iterable[tuple[str, int, Any]],
) -> dict[tuple[str, int], dict]:
    """
    Batch variant of resolved_data().

    Fetches all relevant FactOverride rows in one query, then returns resolved
    data keyed by (entity_type, entity_id). Latest override per field wins.
    """
    bases: dict[tuple[str, int], dict] = {}
    ids_by_type: dict[str, set[int]] = defaultdict(set)
    for entity_type, entity_id, extracted in requests:
        if entity_id is None:
            continue
        key = (entity_type, entity_id)
        bases[key] = extracted if isinstance(extracted, dict) else {}
        ids_by_type[entity_type].add(entity_id)

    if not bases:
        return {}

    filters = [
        and_(FactOverride.entity_type == entity_type, FactOverride.entity_id.in_(entity_ids))
        for entity_type, entity_ids in ids_by_type.items()
        if entity_ids
    ]
    overrides = (
        db.query(FactOverride)
        .filter(or_(*filters))
        .order_by(FactOverride.changed_at.asc(), FactOverride.id.asc())
        .all()
        if filters
        else []
    )

    overrides_by_entity: dict[tuple[str, int], list[FactOverride]] = defaultdict(list)
    for ov in overrides:
        overrides_by_entity[(ov.entity_type, ov.entity_id)].append(ov)

    resolved: dict[tuple[str, int], dict] = {}
    for key, base in bases.items():
        entity_overrides = overrides_by_entity.get(key) or []
        if not entity_overrides:
            resolved[key] = base
            continue

        merged = dict(base)
        for ov in entity_overrides:
            merged[ov.field_name] = ov.new_value

        merged["_reviewed_fields"] = {
            ov.field_name: {
                "new_value": ov.new_value,
                "old_value": ov.old_value,
                "user_display": ov.user_display,
                "changed_at": ov.changed_at.isoformat() if ov.changed_at else None,
                "reason": ov.reason,
            }
            for ov in entity_overrides
        }
        resolved[key] = merged

    return resolved


def get_provenance(merged: dict, field: str) -> dict | None:
    """Return review metadata for a field if it was overridden, else None."""
    reviewed = merged.get("_reviewed_fields") or {}
    return reviewed.get(field)
