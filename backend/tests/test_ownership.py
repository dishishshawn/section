from datetime import datetime, timedelta

import models


def test_ownership_resolves_overrides_and_source_badges(authenticated_client, seed, db):
    doc = models.Document(
        project_id=seed["project"].id,
        s3_key="1/uploaded_lease.pdf",
        mime="application/pdf",
        extraction_status="complete",
    )
    db.add(doc)
    db.flush()

    seed["instrument"].source_document_id = doc.id
    seed["instrument"].extracted_data = {
        "grantor": "Acme Minerals",
        "grantee": "John Doe",
        "source_quotes": {"grantor": "Acme Minerals conveys an undivided interest"},
    }
    db.add_all(
        [
            models.FactOverride(
                entity_type="party",
                entity_id=seed["party"].id,
                field_name="name",
                old_value="Acme Minerals",
                new_value="Acme Minerals LLC",
                user_display="Editor",
                reason="normalize suffix",
                changed_at=datetime.utcnow(),
            ),
            models.FactOverride(
                entity_type="interest",
                entity_id=seed["interest"].id,
                field_name="mineral_estate",
                old_value="mineral",
                new_value="executive rights",
                user_display="Editor",
                reason="manual review",
                changed_at=datetime.utcnow() + timedelta(milliseconds=1),
            ),
        ]
    )
    db.commit()

    c = authenticated_client(seed["viewer"])
    r = c.get(f"/api/projects/{seed['project'].id}/ownership")

    assert r.status_code == 200
    owner = r.json()["owners"][0]
    assert owner["name"] == "Acme Minerals LLC"
    assert owner["mineral_estate"] == "executive rights"
    assert owner["source"]["document_id"] == doc.id
    assert owner["source"]["filename"] == "lease.pdf"
    assert owner["source"]["quote"] == "Acme Minerals conveys an undivided interest"
    assert set(owner["reviewed"]) == {"name", "mineral_estate"}
