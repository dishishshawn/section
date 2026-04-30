"""Smoke + auth tests for GET /api/projects/{id}/documents/zip."""

import io
import zipfile

import models
import routes


def _seed_doc(db, project_id: int, filename: str, body: bytes, *, on_disk: bool = True) -> models.Document:
    """Create a Document row and (optionally) write its bytes to UPLOAD_DIR
    using the same path scheme upload_document uses.

    Each test is independent because conftest.engine() rolls a fresh in-memory
    SQLite per test; the only thing that persists across tests is the file
    bytes we write to disk, so we use unique filenames per call.
    """
    project_dir = routes.UPLOAD_DIR / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    s3_key = f"{project_id}/{filename}"
    if on_disk:
        (routes.UPLOAD_DIR / s3_key).write_bytes(body)
    doc = models.Document(
        project_id=project_id,
        s3_key=s3_key,
        mime="application/pdf",
        ocr_status="complete",
        extraction_status="complete",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_zip_streams_all_project_documents(authenticated_client, seed, db):
    pid = seed["project"].id
    _seed_doc(db, pid, "abc123_lease.pdf", b"%PDF-fake-1")
    _seed_doc(db, pid, "def456_deed.pdf", b"%PDF-fake-2")

    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{pid}/documents/zip")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    assert "documents.zip" in r.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(archive.namelist())
    # UUID-style prefix should be stripped — users see the original filename.
    assert "lease.pdf" in names
    assert "deed.pdf" in names


def test_zip_skips_missing_files_without_failing(authenticated_client, seed, db):
    """One doc on disk + one ghost row → zip contains the live file only."""
    pid = seed["project"].id
    _seed_doc(db, pid, "realuuid_alive.pdf", b"%PDF-still-here")
    _seed_doc(db, pid, "missinguuid_ghost.pdf", b"won't reach disk", on_disk=False)

    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{pid}/documents/zip")

    assert r.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(archive.namelist())
    assert "alive.pdf" in names
    assert "ghost.pdf" not in names


def test_zip_dedupes_clashing_original_names(authenticated_client, seed, db):
    """Two docs with the same human-facing name get suffix-numbered inside the zip."""
    pid = seed["project"].id
    _seed_doc(db, pid, "uuid1_lease.pdf", b"%PDF-A")
    _seed_doc(db, pid, "uuid2_lease.pdf", b"%PDF-B")

    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{pid}/documents/zip")

    assert r.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(archive.namelist())
    assert "lease.pdf" in names
    assert "lease (1).pdf" in names


def test_zip_empty_project_returns_404(authenticated_client, seed):
    pid = seed["project"].id
    c = authenticated_client(seed["owner"])
    r = c.get(f"/api/projects/{pid}/documents/zip")
    assert r.status_code == 404


def test_zip_requires_project_access(authenticated_client, seed, db):
    pid = seed["project"].id
    _seed_doc(db, pid, "uuid_inside.pdf", b"%PDF-private")

    c = authenticated_client(seed["outsider"])
    r = c.get(f"/api/projects/{pid}/documents/zip")
    assert r.status_code in (403, 404)
