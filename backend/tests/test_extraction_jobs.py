from pathlib import Path

import models
import extractors
import routes
from extractors import process_document


def test_upload_enqueues_extraction_job(authenticated_client, seed, monkeypatch):
    seen = {}

    def fake_enqueue(document_id, file_path):
        seen["document_id"] = document_id
        seen["file_path"] = Path(file_path)
        return "job-123"

    monkeypatch.setattr(routes, "enqueue_extraction", fake_enqueue)

    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["extraction_job_id"] == "job-123"
    assert seen["document_id"] == body["id"]
    assert seen["file_path"].exists()


def test_upload_falls_back_to_inline_extraction_when_queue_down(authenticated_client, seed, monkeypatch):
    def boom(*a, **kw):
        raise routes.ExtractionQueueUnavailable("redis down")

    spy = {"called": False}

    def fake_inline(doc_id, path):
        spy["called"] = True
        return {"status": "complete", "document_id": doc_id}

    monkeypatch.setattr(routes, "enqueue_extraction", boom)
    monkeypatch.setattr(routes, "perform_extraction_job", fake_inline)
    monkeypatch.setattr(routes, "IS_PRODUCTION", False)

    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )

    assert r.status_code == 200
    assert spy["called"] is True


def test_upload_503s_in_production_when_queue_down(authenticated_client, seed, monkeypatch):
    def boom(*a, **kw):
        raise routes.ExtractionQueueUnavailable("redis down")

    monkeypatch.setattr(routes, "enqueue_extraction", boom)
    monkeypatch.setattr(routes, "IS_PRODUCTION", True)

    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )

    assert r.status_code == 503


def test_document_extraction_status_includes_queue_and_qa_fields(authenticated_client, seed, db, monkeypatch):
    doc = models.Document(
        project_id=seed["project"].id,
        s3_key="1/example.txt",
        mime="text/plain",
        ocr_status="complete",
        extraction_status="failed: boom",
        extraction_job_id="job-dead",
        extraction_attempts=3,
        extraction_error="boom",
        extraction_warning="Claude extraction input truncated (document_id=1, page_count=2, chars=25000, limit=20000)",
    )
    db.add(doc)
    db.commit()

    monkeypatch.setattr(
        routes,
        "queue_status",
        lambda job_id: {
            "backend": "rq",
            "job_id": job_id,
            "queue_status": "failed",
            "dead_lettered": True,
            "failure": "traceback",
        },
    )

    c = authenticated_client(seed["viewer"])
    r = c.get(f"/api/documents/{doc.id}/extraction")

    assert r.status_code == 200
    body = r.json()
    assert body["extraction_job_id"] == "job-dead"
    assert body["extraction_attempts"] == 3
    assert body["extraction_error"] == "boom"
    assert "truncated" in body["extraction_warning"]
    assert body["dead_lettered"] is True


def test_call_claude_aborts_remaining_chunks_on_fatal_error(monkeypatch):
    """When the first chunk hits a FatalClaudeError (zero balance, bad key),
    we must stop hammering the API instead of running every remaining chunk."""

    long_text = "\n\n".join([f"[PAGE {p}]\nOIL AND GAS LEASE clause text " + ("filler " * 4000) for p in range(1, 5)])
    chunks_called = {"count": 0}

    def fake_once(prompt, text, **kwargs):
        chunks_called["count"] += 1
        if chunks_called["count"] == 1:
            raise extractors.FatalClaudeError("credit balance too low")
        return {"lessor": "should-never-run"}

    monkeypatch.setattr(extractors, "_call_claude_once", fake_once)

    try:
        extractors._call_claude("PROMPT:\n", long_text, document_id=42, page_count=4)
        raise AssertionError("expected FatalClaudeError to propagate")
    except extractors.FatalClaudeError:
        pass

    assert chunks_called["count"] == 1


def test_call_claude_continues_after_non_fatal_chunk_error(monkeypatch):
    """A chunk-level None (transient/parse failure) must not abort siblings —
    only FatalClaudeError does. Other chunks still get a shot."""

    long_text = "\n\n".join([f"[PAGE {p}]\nOIL AND GAS LEASE clause text " + ("filler " * 4000) for p in range(1, 4)])
    chunks_called = {"count": 0}

    def fake_once(prompt, text, **kwargs):
        chunks_called["count"] += 1
        if chunks_called["count"] == 1:
            return None  # transient failure, e.g. parse error
        return {"lessor": "Acme"}

    monkeypatch.setattr(extractors, "_call_claude_once", fake_once)

    result = extractors._call_claude("PROMPT:\n", long_text, document_id=42, page_count=3)
    assert chunks_called["count"] >= 2
    assert result is not None
    assert result.get("lessor") == "Acme"


def test_long_page_marked_extraction_input_is_chunked_without_warning(seed, db, tmp_path, monkeypatch):
    # No real Claude key in tests — force the no-client branch so extraction
    # falls through to the regex fallback instead of hitting the network.
    monkeypatch.setattr(extractors, "_get_client", lambda: None)
    text = "\n\n".join(
        [
            "[PAGE 1]\nOIL AND GAS LEASE\nLESSOR: Alice Mineral Owner\nLESSEE: Beta Energy LLC",
            "[PAGE 2]\nLEGAL DESCRIPTION:\nSection 1, T1N R1E containing 640 acres\nRoyalty: 1/5",
            "[PAGE 3]\nPrimary Term: 3 years\nEffective Date: January 1, 2024",
            "tail " * 5000,
        ]
    )
    path = tmp_path / "large_lease.txt"
    path.write_text(text)
    doc = models.Document(project_id=seed["project"].id, s3_key="large_lease.txt", mime="text/plain")
    db.add(doc)
    db.commit()

    result = process_document(db, doc, path)
    db.refresh(doc)

    assert result["status"] == "complete"
    assert doc.extraction_status == "complete"
    assert doc.page_count == 3
    assert doc.extraction_warning is None


def test_long_unpaged_extraction_input_sets_document_warning(seed, db, tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "_get_client", lambda: None)
    text = "\n".join(
        [
            "OIL AND GAS LEASE",
            "LESSOR: Alice Mineral Owner",
            "LESSEE: Beta Energy LLC",
            "LEGAL DESCRIPTION:\nSection 1, T1N R1E containing 640 acres",
            "tail " * 5000,
        ]
    )
    path = tmp_path / "large_unpaged_lease.txt"
    path.write_text(text)
    doc = models.Document(project_id=seed["project"].id, s3_key="large_unpaged_lease.txt", mime="text/plain")
    db.add(doc)
    db.commit()

    result = process_document(db, doc, path)
    db.refresh(doc)

    assert result["status"] == "complete"
    assert doc.extraction_status == "complete"
    assert doc.page_count is None
    assert doc.extraction_warning is not None
    assert f"document_id={doc.id}" in doc.extraction_warning
    assert "page_count=None" in doc.extraction_warning


def test_claude_call_chunks_long_page_marked_text_and_merges(monkeypatch):
    monkeypatch.setattr(extractors, "CLAUDE_INPUT_CHAR_LIMIT", 140)
    calls = []

    def fake_call_once(prompt, text, document_id=None, page_count=None, chunk_label=None, **kwargs):
        calls.append(
            {
                "prompt": prompt,
                "text": text,
                "document_id": document_id,
                "page_count": page_count,
                "chunk_label": chunk_label,
            }
        )
        if "LESSOR" in text:
            return {
                "lessor": "Alice Mineral Owner",
                "source_quotes": {"lessor": "Alice Mineral Owner grants this lease"},
                "source_pages": {"lessor": 1},
            }
        if "Royalty" in text:
            return {
                "royalty": "1/5",
                "primary_term": "3 years",
                "source_quotes": {"royalty": "Royalty: 1/5"},
                "source_pages": {"royalty": 2},
            }
        return {}

    monkeypatch.setattr(extractors, "_call_claude_once", fake_call_once)
    text = "\n\n".join(
        [
            "[PAGE 1]\nOIL AND GAS LEASE\nLESSOR: Alice Mineral Owner\n" + ("intro " * 18),
            "[PAGE 2]\nRoyalty: 1/5\nPrimary Term: 3 years\n" + ("terms " * 18),
        ]
    )

    result = extractors._call_claude("Prompt:\n", text, document_id=123, page_count=2)

    assert len(calls) > 1
    assert all(len(call["text"]) <= extractors.CLAUDE_INPUT_CHAR_LIMIT for call in calls)
    assert {call["chunk_label"] for call in calls} == {f"{idx}/{len(calls)}" for idx in range(1, len(calls) + 1)}
    assert result["lessor"] == "Alice Mineral Owner"
    assert result["royalty"] == "1/5"
    assert result["source_quotes"] == {
        "lessor": "Alice Mineral Owner grants this lease",
        "royalty": "Royalty: 1/5",
    }
    assert result["source_pages"] == {"lessor": 1, "royalty": 2}


# ---------------------------------------------------------------------------
# Classifier hardening: PSAs route to "psa", unknown filings to "unknown"
# instead of silently masquerading as leases.
# ---------------------------------------------------------------------------


def test_classify_returns_unknown_for_unrecognized_filings():
    # Probate orders, affidavits, court orders shouldn't get a free ride
    # through the lease extractor.
    assert extractors.classify_document("probate_order_2024.pdf", "") == "unknown"
    assert extractors.classify_document("affidavit_of_heirship.pdf", "") == "unknown"
    assert extractors.classify_document("court_order_partition.pdf", "ORDER\n\nThe court hereby...") == "unknown"


def test_classify_returns_psa_for_purchase_and_sale():
    # Filename match
    assert extractors.classify_document("Crescent_Purchase_and_Sale_Agreement.pdf", "") == "psa"
    # Title match
    assert extractors.classify_document("ambiguous.pdf", "PURCHASE AND SALE AGREEMENT\n\nThis Agreement...") == "psa"
    # Body match (must beat the deed/lease keyword fallthroughs)
    body = "This Purchase and Sale Agreement is between Grantor and Grantee..."
    assert extractors.classify_document("doc.pdf", body) == "psa"


def test_process_document_skips_unknown_type(seed, db, tmp_path, monkeypatch):
    # Unknown classification should produce a "skipped: ..." status with
    # no extraction or materialization side effects.
    monkeypatch.setattr(extractors, "_get_client", lambda: None)
    monkeypatch.setattr(extractors, "classify_document", lambda *_a, **_k: "unknown")

    path = tmp_path / "mystery_filing.txt"
    path.write_text("This is some legal filing of indeterminate type.")
    doc = models.Document(project_id=seed["project"].id, s3_key="mystery_filing.txt", mime="text/plain")
    db.add(doc)
    db.commit()

    result = process_document(db, doc, path)
    db.refresh(doc)

    assert result["status"] == "skipped"
    assert result["reason"] == "unknown_type"
    assert "skipped" in (doc.extraction_status or "")
    assert "not recognized" in (doc.extraction_status or "")


def test_process_document_skips_psa(seed, db, tmp_path, monkeypatch):
    monkeypatch.setattr(extractors, "_get_client", lambda: None)
    monkeypatch.setattr(extractors, "classify_document", lambda *_a, **_k: "psa")

    path = tmp_path / "merger_psa.txt"
    path.write_text("PURCHASE AND SALE AGREEMENT\n\nBetween Buyer and Seller...")
    doc = models.Document(project_id=seed["project"].id, s3_key="merger_psa.txt", mime="text/plain")
    db.add(doc)
    db.commit()

    result = process_document(db, doc, path)
    db.refresh(doc)

    assert result["status"] == "skipped"
    assert result["reason"] == "psa"
    assert "PSA" in (doc.extraction_status or "")


# ---------------------------------------------------------------------------
# Consistency-check warnings — surface likely extraction errors as warnings
# instead of letting nonsense rows reach the runsheet.
# ---------------------------------------------------------------------------


def test_lease_consistency_flags_recording_before_effective():
    le = extractors.LeaseExtraction(
        lessor="Acme",
        effective_date="2024-06-01",
        recording_date="2024-05-15",  # before effective — physically impossible
    )
    warnings = extractors._lease_consistency_checks(le)
    assert any("recording_date" in w and "precedes" in w for w in warnings)


def test_lease_consistency_flags_net_exceeds_gross():
    le = extractors.LeaseExtraction(gross_acres=100.0, net_acres=120.0)
    warnings = extractors._lease_consistency_checks(le)
    assert any("net_acres" in w and "gross_acres" in w for w in warnings)


def test_lease_consistency_flags_implausible_bonus_per_acre():
    # Total bonus reported as per-acre (or vice versa) — extreme $/ac.
    le = extractors.LeaseExtraction(bonus=0.05, gross_acres=100.0)
    warnings = extractors._lease_consistency_checks(le)
    assert any("bonus/acre" in w for w in warnings)


def test_deed_consistency_flags_fraction_over_one():
    de = extractors.DeedExtraction(fraction_numerator=3, fraction_denominator=2)
    warnings = extractors._deed_consistency_checks(de)
    assert any("outside (0, 1]" in w for w in warnings)


def test_deed_consistency_flags_zero_denominator():
    de = extractors.DeedExtraction(fraction_numerator=1, fraction_denominator=0)
    warnings = extractors._deed_consistency_checks(de)
    assert any("denominator is 0" in w for w in warnings)


def test_record_consistency_warnings_appends_to_existing(seed, db):
    # Pre-existing warning (truncation note) must be preserved when consistency
    # checks add their own — semicolon-joined.
    doc = models.Document(
        project_id=seed["project"].id,
        s3_key="example.txt",
        mime="text/plain",
        extraction_warning="Claude extraction input truncated (...)",
    )
    db.add(doc)
    db.commit()

    le = extractors.LeaseExtraction(gross_acres=100.0, net_acres=120.0)
    extractors._record_consistency_warnings(doc, lease=le)
    db.commit()
    db.refresh(doc)

    assert "truncated" in (doc.extraction_warning or "")
    assert "net_acres" in (doc.extraction_warning or "")


def test_record_consistency_warnings_noop_on_clean_extraction(seed, db):
    doc = models.Document(project_id=seed["project"].id, s3_key="clean.txt", mime="text/plain")
    db.add(doc)
    db.commit()

    le = extractors.LeaseExtraction(gross_acres=100.0, net_acres=80.0)
    extractors._record_consistency_warnings(doc, lease=le)
    db.refresh(doc)

    assert doc.extraction_warning is None


# ---------------------------------------------------------------------------
# Per-upload model selection (dev dropdown)
# ---------------------------------------------------------------------------


def test_list_extraction_models_returns_allowlist(authenticated_client, seed):
    c = authenticated_client(seed["owner"])
    r = c.get("/api/extraction/models")
    assert r.status_code == 200
    body = r.json()
    assert body["default_model"] == extractors.CLAUDE_MODEL
    ids = {m["id"] for m in body["models"]}
    assert "claude-haiku-4-5-20251001" in ids
    assert "claude-sonnet-4-6" in ids
    assert "claude-opus-4-7" in ids


def test_upload_persists_model_when_supplied(authenticated_client, seed, monkeypatch):
    monkeypatch.setattr(routes, "enqueue_extraction", lambda *a, **k: "job-xyz")

    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents?model=claude-sonnet-4-6",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]

    listing = c.get(f"/api/projects/{seed['project'].id}/documents")
    matching = next(d for d in listing.json() if d["id"] == doc_id)
    assert matching["extraction_model"] == "claude-sonnet-4-6"


def test_upload_rejects_unsupported_model(authenticated_client, seed):
    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents?model=gpt-4o-mini",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )
    assert r.status_code == 400
    assert "Unsupported extraction model" in r.json()["detail"]


def test_upload_without_model_falls_through_to_default(authenticated_client, seed, monkeypatch):
    """Omitted model param means extraction_model stays NULL on the doc, and
    process_document will use the env-default at extraction time."""
    monkeypatch.setattr(routes, "enqueue_extraction", lambda *a, **k: "job-default")

    c = authenticated_client(seed["editor"])
    r = c.post(
        f"/api/projects/{seed['project'].id}/documents",
        files={"file": ("lease.txt", b"Oil and gas lease", "text/plain")},
    )
    assert r.status_code == 200

    listing = c.get(f"/api/projects/{seed['project'].id}/documents")
    matching = next(d for d in listing.json() if d["id"] == r.json()["id"])
    assert matching["extraction_model"] is None


def test_call_claude_once_uses_supplied_model(monkeypatch):
    """The model parameter must reach client.messages.create — without this
    the dropdown is just decoration."""

    captured = {}

    class FakeUsage:
        input_tokens = 1
        output_tokens = 1
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class FakeContent:
        text = '{"lessor": "Acme"}'

    class FakeResponse:
        content = [FakeContent()]
        usage = FakeUsage()

    class FakeMessages:
        def create(self, **kwargs):
            captured["model"] = kwargs.get("model")
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(extractors, "_get_client", lambda: FakeClient())

    extractors._call_claude_once(
        "PROMPT:\n",
        "[PAGE 1]\nLEASE TEXT",
        document_id=1,
        page_count=1,
        model="claude-sonnet-4-6",
    )
    assert captured["model"] == "claude-sonnet-4-6"


def test_call_claude_once_falls_back_to_env_default_when_model_none(monkeypatch):
    captured = {}

    class FakeUsage:
        input_tokens = 1
        output_tokens = 1
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class FakeContent:
        text = '{"lessor": "Acme"}'

    class FakeResponse:
        content = [FakeContent()]
        usage = FakeUsage()

    class FakeMessages:
        def create(self, **kwargs):
            captured["model"] = kwargs.get("model")
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(extractors, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(extractors, "CLAUDE_MODEL", "claude-haiku-4-5-20251001")

    extractors._call_claude_once("PROMPT:\n", "[PAGE 1]\nLEASE TEXT", model=None)
    assert captured["model"] == "claude-haiku-4-5-20251001"
