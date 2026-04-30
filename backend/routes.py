from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pathlib import Path
import hashlib
import re
import uuid
import os
from datetime import datetime
from database import get_db
from models import Project, Document, Tract, Party, Instrument, Interest, Obligation, OrgMembership, ProjectAccess, User
from pydantic import BaseModel
from exports import OwnershipReportGenerator, RunsheetGenerator, TitleOpinionGenerator, StipulationsGenerator
from facts import resolved_data, resolved_data_many
import extractors
from jobs import ExtractionQueueUnavailable, enqueue_extraction, perform_extraction_job, queue_status
from str_parser import parse_legal_description, parsed_to_dict, section_grid_position
from auth import IS_PRODUCTION, get_current_user
from logging_config import get_logger
from permissions import (
    ORG_ROLE_RANK,
    effective_project_role,
    require_project_role,
    user_accessible_project_ids,
)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

logger = get_logger("section.routes")

router = APIRouter(prefix="/api", tags=["api"])


class ProjectCreate(BaseModel):
    name: str
    jurisdiction: str
    owner_org: str = None
    org_id: int | None = None


class ProjectResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    jurisdiction: str
    created_at: str


@router.post("/projects")
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # If org_id supplied, verify membership
    if project.org_id:
        m = (
            db.query(OrgMembership)
            .filter(
                OrgMembership.user_id == user.id,
                OrgMembership.org_id == project.org_id,
            )
            .first()
        )
        if not m or ORG_ROLE_RANK.get(m.role, 0) < ORG_ROLE_RANK.get("member", 0):
            raise HTTPException(status_code=403, detail="Not a member of that organization")

    db_project = Project(
        name=project.name,
        jurisdiction=project.jurisdiction,
        owner_org=project.owner_org,
        org_id=project.org_id,
        created_by=user.id,
    )
    db.add(db_project)
    db.flush()

    # Grant creator explicit owner access on the project
    pa = ProjectAccess(
        user_id=user.id,
        project_id=db_project.id,
        org_id=project.org_id,  # None for personal projects (column is nullable)
        role="owner",
        granted_by=user.id,
    )
    db.add(pa)
    db.commit()
    db.refresh(db_project)
    return {
        "id": db_project.id,
        "name": db_project.name,
        "jurisdiction": db_project.jurisdiction,
        "created_at": db_project.created_at.isoformat(),
        "your_role": "owner",
    }


@router.get("/projects/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    role = require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    return {
        "id": project.id,
        "name": project.name,
        "jurisdiction": project.jurisdiction,
        "created_at": project.created_at.isoformat(),
        "your_role": role,
    }


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        accessible_ids = user_accessible_project_ids(db, user)
        if not accessible_ids:
            return []
        projects = db.query(Project).filter(Project.id.in_(accessible_ids)).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "jurisdiction": p.jurisdiction,
                "created_at": p.created_at.isoformat(),
                "your_role": effective_project_role(db, user, p.id),
            }
            for p in projects
        ]
    except Exception as e:
        import traceback

        print(f"ERROR in list_projects: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _enqueue_extraction_or_503(db: Session, doc: Document, file_path: Path) -> None:
    try:
        job_id = enqueue_extraction(doc.id, file_path)
    except ExtractionQueueUnavailable as e:
        if not IS_PRODUCTION:
            # Dev fallback: no broker reachable, run extraction inline so a
            # fresh laptop without docker-compose isn't a hard upload failure.
            # perform_extraction_job opens its own SessionLocal and writes
            # final status (including "failed: <exc>") on its own commit, so
            # the request-scoped session just needs to refresh to see it.
            logger.warning(
                "extraction queue unavailable, running inline (dev fallback)",
                extra={"document_id": doc.id, "error": str(e)},
            )
            try:
                perform_extraction_job(doc.id, str(file_path))
            except Exception:
                # Inline job already persisted "failed: <exc>" on its own
                # session; UI surfaces that via /api/documents/{id}/extraction.
                pass
            db.refresh(doc)
            return
        doc.extraction_status = "queue_failed"
        doc.extraction_error = str(e)
        db.commit()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        doc.extraction_status = "queue_failed"
        doc.extraction_error = f"Unable to enqueue extraction: {e}"
        db.commit()
        raise HTTPException(status_code=503, detail="Unable to enqueue extraction job")

    doc.extraction_status = "queued"
    doc.extraction_job_id = job_id
    doc.extraction_error = None
    doc.extraction_warning = None
    doc.extraction_attempts = 0
    db.commit()


@router.post("/projects/{project_id}/documents")
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    force: bool = False,
    model: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "editor")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate caller-supplied model against allowlist. Empty string maps to
    # None ("use server default") so the frontend can clear an override.
    if model == "":
        model = None
    if model is not None and model not in extractors.SUPPORTED_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Unsupported extraction model: {model}")

    raw_name = file.filename or "unnamed"
    safe_name = Path(raw_name.replace("\\", "/")).name or "unnamed"

    contents = await file.read()
    content_hash = hashlib.sha256(contents).hexdigest()

    existing = (
        db.query(Document)
        .filter(
            Document.project_id == project_id,
            Document.content_hash == content_hash,
        )
        .first()
    )
    if existing and not force:
        return {
            "id": existing.id,
            "s3_key": existing.s3_key,
            "filename": safe_name,
            "status": "duplicate",
            "extraction_status": existing.extraction_status,
            "message": "This file already exists in the project",
        }

    if existing and force:
        # Re-ingest the same file: overwrite bytes on disk and re-run extraction.
        # Keeps the document id stable so any references in extracted entities survive.
        existing_path = UPLOAD_DIR / existing.s3_key
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_bytes(contents)
        existing.ocr_status = "pending"
        existing.extraction_status = "queued"
        existing.extraction_job_id = None
        existing.extraction_error = None
        existing.extraction_warning = None
        existing.extraction_attempts = 0
        # Force re-extraction can flip the model — useful for A/B-ing the
        # same doc through Haiku vs Sonnet without re-uploading.
        existing.extraction_model = model
        db.commit()
        db.refresh(existing)
        _enqueue_extraction_or_503(db, existing, existing_path)
        db.refresh(existing)
        return {
            "id": existing.id,
            "s3_key": existing.s3_key,
            "filename": safe_name,
            "status": "queued",
            "extraction_status": "queued",
            "extraction_job_id": existing.extraction_job_id,
            "reprocessed": True,
        }

    project_dir = UPLOAD_DIR / str(project_id)
    project_dir.mkdir(exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = project_dir / unique_name
    file_path.write_bytes(contents)

    doc = Document(
        project_id=project_id,
        s3_key=str(file_path.relative_to(UPLOAD_DIR)),
        mime=file.content_type,
        content_hash=content_hash,
        ocr_status="pending",
        extraction_status="queued",
        extraction_error=None,
        extraction_warning=None,
        extraction_model=model,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    _enqueue_extraction_or_503(db, doc, file_path)
    db.refresh(doc)

    return {
        "id": doc.id,
        "s3_key": doc.s3_key,
        "filename": safe_name,
        "status": "queued",
        "extraction_status": "queued",
        "extraction_job_id": doc.extraction_job_id,
    }


@router.get("/projects/{project_id}/documents/zip")
def download_all_project_documents(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream a zip of every document in this project. Viewer access required.

    Skips documents whose underlying file is missing on disk (logs a warning
    rather than failing the whole archive). Filenames inside the zip strip the
    upload-time UUID prefix so users get the original names back. If multiple
    documents share an original name, later entries get a numeric suffix.
    """
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    docs = db.query(Document).filter(Document.project_id == project_id).all()
    if not docs:
        raise HTTPException(status_code=404, detail="No documents in this project")

    # Build the zip in memory. For projects with thousands of files this would
    # want true streaming via stream_zip or an external tool — punt until the
    # corpus shows pressure.
    import io
    import zipfile

    buf = io.BytesIO()
    used_names: dict[str, int] = {}
    skipped: list[str] = []
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            file_path = UPLOAD_DIR / doc.s3_key
            if not file_path.exists():
                skipped.append(f"{doc.id}:{doc.s3_key}")
                continue
            # Strip the "<uuid>_" prefix that upload_document adds to keep
            # filenames unique on disk; users want the original document name.
            inner = Path(doc.s3_key).name
            if "_" in inner:
                inner = inner.split("_", 1)[1]
            if inner in used_names:
                used_names[inner] += 1
                stem = Path(inner).stem
                suffix = Path(inner).suffix
                inner = f"{stem} ({used_names[inner]}){suffix}"
            else:
                used_names[inner] = 0
            zf.write(file_path, arcname=inner)
    if skipped:
        logger.warning(
            "documents zip: skipped missing files",
            extra={"project_id": project_id, "missing": skipped},
        )
    buf.seek(0)

    safe_project = (
        re.sub(r"[^\w\-]+", "_", project.name or f"project-{project_id}").strip("_") or f"project-{project_id}"
    )
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_project}_documents.zip"'},
    )


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_project_role(db, user, doc.project_id, "viewer")
    file_path = UPLOAD_DIR / doc.s3_key
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    filename = Path(doc.s3_key).name
    if "_" in filename:
        filename = filename.split("_", 1)[1]
    return FileResponse(
        str(file_path),
        media_type=doc.mime or "application/octet-stream",
        filename=filename,
    )


@router.get("/documents/{document_id}/extraction")
def get_document_extraction_status(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_project_role(db, user, doc.project_id, "viewer")

    return {
        "document_id": doc.id,
        "ocr_status": doc.ocr_status,
        "extraction_status": doc.extraction_status,
        "extraction_job_id": doc.extraction_job_id,
        "extraction_attempts": doc.extraction_attempts or 0,
        "extraction_error": doc.extraction_error,
        "extraction_warning": doc.extraction_warning,
        "extraction_model": doc.extraction_model,
        **queue_status(doc.extraction_job_id),
    }


@router.get("/documents/{document_id}/contributions")
def get_document_contributions(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_project_role(db, user, doc.project_id, "viewer")

    instruments = (
        db.query(Instrument).filter(Instrument.source_document_id == document_id).order_by(Instrument.id).all()
    )
    instrument_ids = [i.id for i in instruments]

    obligations = []
    if instrument_ids:
        obligations = (
            db.query(Obligation).filter(Obligation.instrument_id.in_(instrument_ids)).order_by(Obligation.id).all()
        )

    return {
        "document_id": document_id,
        "extraction_status": doc.extraction_status,
        "instruments": [
            {
                "id": i.id,
                "type": i.type,
                "recorded_at": i.recorded_at.isoformat() if i.recorded_at else None,
                "extracted_data": i.extracted_data or {},
            }
            for i in instruments
        ],
        "obligations": [
            {
                "id": o.id,
                "instrument_id": o.instrument_id,
                "type": o.type,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "params": o.params or {},
            }
            for o in obligations
        ],
    }


@router.get("/projects/{project_id}/documents")
def list_documents(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "s3_key": d.s3_key,
            "filename": d.s3_key.split("_", 1)[-1] if "_" in (d.s3_key or "") else d.s3_key,
            "mime": d.mime,
            "ocr_status": d.ocr_status,
            "extraction_status": d.extraction_status,
            "extraction_job_id": d.extraction_job_id,
            "extraction_attempts": d.extraction_attempts or 0,
            "extraction_error": d.extraction_error,
            "extraction_warning": d.extraction_warning,
            "extraction_model": d.extraction_model,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/extraction/models")
def list_extraction_models(
    user: User = Depends(get_current_user),
):
    """Return the allowlist of Claude models the dropdown can pick from."""
    return {
        "default_model": extractors.CLAUDE_MODEL,
        "models": extractors.SUPPORTED_MODELS,
    }


@router.post("/projects/{project_id}/extract")
def extract_document(
    project_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "editor")
    doc = db.query(Document).filter(Document.id == document_id, Document.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = UPLOAD_DIR / doc.s3_key
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    doc.ocr_status = "pending"
    doc.extraction_status = "queued"
    doc.extraction_job_id = None
    doc.extraction_error = None
    doc.extraction_warning = None
    doc.extraction_attempts = 0
    db.commit()

    _enqueue_extraction_or_503(db, doc, file_path)
    db.refresh(doc)

    return {"status": "queued", "document_id": document_id, "extraction_job_id": doc.extraction_job_id}


@router.get("/projects/{project_id}/ownership")
def get_ownership(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tracts = db.query(Tract).filter(Tract.project_id == project_id).all()
    interests = (
        db.query(Interest).join(Tract).options(joinedload(Interest.party)).filter(Tract.project_id == project_id).all()
    )
    lease_count = (
        db.query(Instrument)
        .filter(
            Instrument.project_id == project_id,
            Instrument.type == "lease",
        )
        .count()
    )

    total_acres = sum(t.gross_acres or 0 for t in tracts)
    leased_acres = total_acres if lease_count > 0 else 0

    # Build an index of party name → instrument(s) that mention them, for source tracing.
    project_instruments = db.query(Instrument).filter(Instrument.project_id == project_id).all()
    fact_requests = [
        ("instrument", inst.id, inst.extracted_data if isinstance(inst.extracted_data, dict) else {})
        for inst in project_instruments
    ]
    fact_requests.extend(
        (
            "interest",
            i.id,
            {
                "fraction_numerator": str(i.fraction_numerator),
                "fraction_denominator": str(i.fraction_denominator),
                "mineral_estate": i.mineral_estate or "Unknown",
            },
        )
        for i in interests
    )
    fact_requests.extend(
        ("party", i.party.id, {"name": i.party.name, "type": i.party.type}) for i in interests if i.party
    )
    resolved = resolved_data_many(db, fact_requests)

    source_doc_ids = {inst.source_document_id for inst in project_instruments if inst.source_document_id}
    source_docs = (
        {doc.id: doc for doc in db.query(Document).filter(Document.id.in_(source_doc_ids)).all()}
        if source_doc_ids
        else {}
    )

    party_to_instrument: dict[str, Instrument] = {}
    for inst in project_instruments:
        grantor, grantee = _instrument_parties_from_data(
            resolved.get(("instrument", inst.id), inst.extracted_data if isinstance(inst.extracted_data, dict) else {})
        )
        for name in (grantor, grantee):
            if name and name not in party_to_instrument:
                party_to_instrument[name] = inst

    owners = []
    for i in interests:
        denom = i.fraction_denominator or 1
        num = i.fraction_numerator or 0
        pct = round((num / denom) * 100, 2) if denom else 0

        # Resolve party name through overrides
        party = i.party
        raw_party_name = party.name if party else "Unknown"
        party_resolved = resolved.get(("party", party.id), {}) if party else {}
        party_name = party_resolved.get("name") or raw_party_name
        party_reviewed = party_resolved.get("_reviewed_fields") or {}

        # Resolve interest fields through overrides
        interest_resolved = resolved.get(("interest", i.id), {})
        interest_reviewed = interest_resolved.get("_reviewed_fields") or {}
        mineral_estate = interest_resolved.get("mineral_estate") or "Unknown"

        source_inst = party_to_instrument.get(raw_party_name) or party_to_instrument.get(party_name)
        field = None
        if source_inst:
            data = resolved.get(
                ("instrument", source_inst.id),
                source_inst.extracted_data if isinstance(source_inst.extracted_data, dict) else {},
            )
            grantor, grantee = _instrument_parties_from_data(data)
            if party_name == grantor or raw_party_name == grantor:
                field = "grantor" if "grantor" in (data.get("source_quotes") or {}) else "lessor"
            else:
                field = "grantee" if "grantee" in (data.get("source_quotes") or {}) else "lessee"
        source = _source_for_instrument_from_docs(source_inst, source_docs, field) if source_inst else None

        owners.append(
            {
                "party_id": party.id if party else None,
                "interest_id": i.id,
                "name": party_name,
                "fraction": f"{num}/{denom}",
                "percentage": pct,
                "mineral_estate": mineral_estate,
                "source": source,
                "reviewed": {**party_reviewed, **interest_reviewed},
            }
        )

    return {
        "project_id": project_id,
        "owners": owners,
        "total_acres": total_acres,
        "leased_acres": leased_acres,
        "open_acres": max(total_acres - leased_acres, 0),
    }


@router.get("/projects/{project_id}/obligations")
def get_obligations(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    obligations = db.query(Obligation).filter(Obligation.project_id == project_id).all()
    now = datetime.utcnow()

    def priority_for(days: int) -> str:
        # Negative days = already past the due date. Without this branch the
        # bucketing collapsed all overdue items (years stale) into "high"
        # because they trivially satisfy days <= 30.
        if days < 0:
            return "overdue"
        if days <= 30:
            return "high"
        if days <= 120:
            return "medium"
        return "low"

    items = []
    for o in obligations:
        days_until = (o.due_date - now).days if o.due_date else 0
        source = None
        if o.instrument_id:
            inst = db.query(Instrument).filter(Instrument.id == o.instrument_id).first()
            field = (
                "primary_term"
                if "term" in (o.type or "")
                else "continuous_drilling" if "drilling" in (o.type or "") else None
            )
            source = _source_for_instrument(inst, db, field)

        params = o.params if isinstance(o.params, dict) else {}
        raw_description = params.get("description") or str(o.params or "")
        obl_base = {"description": raw_description, "type": o.type or "Obligation"}
        obl_resolved = resolved_data(db, "obligation", o.id, obl_base)
        obl_reviewed = obl_resolved.get("_reviewed_fields") or {}

        items.append(
            {
                "id": o.id,
                "type": obl_resolved.get("type") or "Obligation",
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "days_until": days_until,
                "priority": priority_for(days_until),
                "description": obl_resolved.get("description") or "",
                "source": source,
                "reviewed": obl_reviewed,
            }
        )

    return {"project_id": project_id, "obligations": items}


def _instrument_parties_from_data(data: dict) -> tuple[str, str]:
    data = data if isinstance(data, dict) else {}
    grantor = data.get("grantor") or data.get("lessor") or ""
    grantee = data.get("grantee") or data.get("lessee") or ""
    return grantor, grantee


def _instrument_parties(inst: Instrument, db: Session) -> tuple[str, str]:
    data = resolved_data(db, "instrument", inst.id, inst.extracted_data)
    return _instrument_parties_from_data(data)


def _source_for_instrument_from_docs(
    inst: Instrument,
    documents_by_id: dict[int, Document],
    field: str = None,
) -> Optional[dict]:
    if not inst or not inst.source_document_id:
        return None
    doc = documents_by_id.get(inst.source_document_id)
    if not doc:
        return None
    filename = doc.s3_key.split("_", 1)[-1] if "_" in (doc.s3_key or "") else (doc.s3_key or "")
    data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
    quotes = data.get("source_quotes") or {}
    quote = quotes.get(field) if field else None
    return {
        "document_id": doc.id,
        "filename": filename,
        "quote": quote,
    }


def _source_for_instrument(inst: Instrument, db: Session, field: str = None) -> Optional[dict]:
    if not inst or not inst.source_document_id:
        return None
    doc = db.query(Document).filter(Document.id == inst.source_document_id).first()
    if not doc:
        return None
    filename = doc.s3_key.split("_", 1)[-1] if "_" in (doc.s3_key or "") else (doc.s3_key or "")
    data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
    quotes = data.get("source_quotes") or {}
    quote = quotes.get(field) if field else None
    return {
        "document_id": doc.id,
        "filename": filename,
        "quote": quote,
    }


@router.get("/projects/{project_id}/runsheet")
def get_runsheet(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    instruments = (
        db.query(Instrument).filter(Instrument.project_id == project_id).order_by(Instrument.recorded_at.asc()).all()
    )

    chain = []
    for inst in instruments:
        grantor, grantee = _instrument_parties(inst, db)
        if not grantor or not grantee:
            status = "missing"
        elif "unknown" in grantor.lower() or "unknown" in grantee.lower():
            status = "flagged"
        else:
            status = "complete"

        data = resolved_data(db, "instrument", inst.id, inst.extracted_data)
        quotes = data.get("source_quotes") or {}
        # For the runsheet row, pick the most representative quote (legal description or grantor)
        best_quote = quotes.get("legal_description") or quotes.get("grantor") or quotes.get("lessor") or None
        source = None
        if inst.source_document_id:
            doc = db.query(Document).filter(Document.id == inst.source_document_id).first()
            if doc:
                filename = doc.s3_key.split("_", 1)[-1] if "_" in (doc.s3_key or "") else (doc.s3_key or "")
                source = {"document_id": doc.id, "filename": filename, "quote": best_quote}

        reviewed = data.get("_reviewed_fields") or {}
        chain.append(
            {
                "instrument_id": inst.id,
                "instrument_type": (inst.type or "instrument").replace("_", " ").title(),
                "grantor": grantor or "Unknown",
                "grantee": grantee or "Unknown",
                "date": inst.recorded_at.isoformat()[:10] if inst.recorded_at else "",
                "status": status,
                "source": source,
                "reviewed": reviewed,
            }
        )

    gaps = []
    for idx in range(len(chain) - 1):
        prev, nxt = chain[idx], chain[idx + 1]
        if prev["grantee"] != nxt["grantor"] and "Unknown" not in (prev["grantee"], nxt["grantor"]):
            gaps.append(
                {
                    "from": prev["grantee"],
                    "to": nxt["grantor"],
                    "missing_document": f"Missing conveyance from {prev['grantee']} to {nxt['grantor']}",
                }
            )
    for item in chain:
        if item["status"] == "flagged":
            gaps.append(
                {
                    "from": item["grantor"],
                    "to": item["grantee"],
                    "missing_document": f"Unknown party in {item['instrument_type']} - curative affidavit needed",
                }
            )

    return {"project_id": project_id, "chain": chain, "gaps": gaps}


@router.get("/projects/{project_id}/risk")
def get_risk(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    instruments = db.query(Instrument).filter(Instrument.project_id == project_id).all()
    leases = [i for i in instruments if (i.type or "").lower() == "lease"]
    obligations = db.query(Obligation).filter(Obligation.project_id == project_id).all()
    now = datetime.utcnow()
    expiring_soon = sum(1 for o in obligations if o.due_date and 0 <= (o.due_date - now).days <= 90)

    royalties = []
    for lease in leases:
        data = lease.extracted_data if isinstance(lease.extracted_data, dict) else {}
        royalty = data.get("royalty")
        if isinstance(royalty, (int, float)):
            royalties.append(float(royalty) * (100 if royalty <= 1 else 1))
        elif isinstance(royalty, str):
            import re as _re

            frac_match = _re.search(r"(\d+)\s*/\s*(\d+)", royalty)
            pct_match = _re.search(r"([\d.]+)\s*%", royalty)
            if frac_match:
                try:
                    royalties.append(int(frac_match.group(1)) / int(frac_match.group(2)) * 100)
                except (ValueError, ZeroDivisionError):
                    pass
            elif pct_match:
                try:
                    royalties.append(float(pct_match.group(1)))
                except ValueError:
                    pass

    royalty_range = {
        "min": round(min(royalties), 3) if royalties else 0,
        "max": round(max(royalties), 3) if royalties else 0,
    }

    flagged = []
    idx = 1
    for inst in instruments:
        grantor, grantee = _instrument_parties(inst, db)
        if "unknown" in (grantor + " " + grantee).lower():
            flagged.append(
                {
                    "id": idx,
                    "lease": f"{(inst.type or 'instrument').replace('_', ' ').title()}",
                    "risk_type": "Title Defect",
                    "severity": "critical",
                    "description": f"Unknown party in chain of title: {grantor or '?'} → {grantee or '?'}. Curative needed.",
                }
            )
            idx += 1

    for o in obligations:
        if o.due_date:
            days = (o.due_date - now).days
            if 0 <= days <= 45:
                desc = (o.params or {}).get("description") if isinstance(o.params, dict) else None
                flagged.append(
                    {
                        "id": idx,
                        "lease": (o.type or "obligation").replace("_", " ").title(),
                        "risk_type": "Expiration",
                        "severity": "high" if days <= 30 else "medium",
                        "description": desc or f"{o.type} due in {days} days",
                    }
                )
                idx += 1

    return {
        "project_id": project_id,
        "total_leases": len(leases),
        "expiring_soon": expiring_soon,
        "royalty_range": royalty_range,
        "flagged_issues": flagged,
    }


@router.get("/projects/{project_id}/export/ownership")
def export_ownership_report(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tracts = db.query(Tract).filter(Tract.project_id == project_id).all()
    interests = db.query(Interest).join(Tract).filter(Tract.project_id == project_id).all()
    lease_count = (
        db.query(Instrument)
        .filter(
            Instrument.project_id == project_id,
            Instrument.type == "lease",
        )
        .count()
    )

    total_acres = sum(t.gross_acres or 0 for t in tracts)
    leased_acres = total_acres if lease_count > 0 else 0

    owners = []
    for i in interests:
        denom = i.fraction_denominator or 1
        num = i.fraction_numerator or 0
        party = i.party
        party_base = {"name": party.name, "type": party.type} if party else {}
        party_resolved = resolved_data(db, "party", party.id, party_base) if party else {}
        party_name = party_resolved.get("name") or (party.name if party else "Unknown")

        interest_base = {"mineral_estate": i.mineral_estate or "", "burdens": str(i.burdens or "None")}
        interest_resolved = resolved_data(db, "interest", i.id, interest_base)

        owners.append(
            {
                "name": party_name,
                "fraction": f"{num}/{denom}",
                "percentage": round((num / denom) * 100, 2) if denom else 0,
                "mineral_estate": interest_resolved.get("mineral_estate") or "Unknown",
                "burdens": interest_resolved.get("burdens") or "None",
            }
        )

    ownership_data = {
        "project_id": project_id,
        "owners": owners,
        "total_acres": total_acres,
        "leased_acres": leased_acres,
        "open_acres": max(total_acres - leased_acres, 0),
    }

    pdf_buffer = OwnershipReportGenerator.generate_pdf(project.name, project.jurisdiction, ownership_data)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_Ownership_Report.pdf"'},
    )


@router.get("/projects/{project_id}/export/runsheet")
def export_runsheet(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    runsheet_data = get_runsheet(project_id, db, user)
    pdf_buffer = RunsheetGenerator.generate_pdf(project.name, project.jurisdiction, runsheet_data)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_Runsheet.pdf"'},
    )


@router.get("/projects/{project_id}/export/title-opinion")
def export_title_opinion(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    runsheet_data = get_runsheet(project_id, db, user)
    ownership_data = get_ownership(project_id, db, user)
    pdf_buffer = TitleOpinionGenerator.generate_pdf(project.name, project.jurisdiction, runsheet_data, ownership_data)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_Title_Opinion.pdf"'},
    )


@router.get("/projects/{project_id}/export/stipulations")
def export_stipulations(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    obligations_data = get_obligations(project_id, db, user)
    pdf_buffer = StipulationsGenerator.generate_pdf(project.name, project.jurisdiction, obligations_data)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{project.name}_Stipulations.pdf"'},
    )


@router.get("/projects/{project_id}/tract-map")
def get_tract_map(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return PLSS grid data for all tracts in a project.
    Each tract gets its legal description parsed, yielding section grid position,
    aliquot coverage, and the instruments recorded against that section.
    """
    require_project_role(db, user, project_id, "viewer")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tracts = db.query(Tract).filter(Tract.project_id == project_id).all()
    instruments = db.query(Instrument).filter(Instrument.project_id == project_id).all()

    def _norm_ld(s: str) -> str:
        """Normalize a legal description for matching: lowercase, collapsed whitespace."""
        return " ".join((s or "").lower().split())

    # Determine leased status per tract via instruments
    leased_legal_descs: set[str] = set()
    for inst in instruments:
        if (inst.type or "").lower() == "lease":
            data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
            ld = data.get("legal_description")
            if ld:
                leased_legal_descs.add(_norm_ld(ld))

    parsed_tracts = []
    township_index: dict[str, dict] = {}  # key: "T{n}{dir} R{n}{dir}"

    for tract in tracts:
        parsed = parse_legal_description(tract.legal_description or "")
        parsed_dict = parsed_to_dict(parsed)

        # Find instruments for this tract
        tract_instruments = []
        for inst in instruments:
            data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
            ld = data.get("legal_description") or ""
            if ld and _norm_ld(ld) == _norm_ld(tract.legal_description or ""):
                resolved = resolved_data(db, "instrument", inst.id, data)
                grantor = resolved.get("grantor") or resolved.get("lessor") or ""
                grantee = resolved.get("grantee") or resolved.get("lessee") or ""
                doc = None
                if inst.source_document_id:
                    d = db.query(Document).filter(Document.id == inst.source_document_id).first()
                    if d:
                        fn = d.s3_key.split("_", 1)[-1] if "_" in (d.s3_key or "") else (d.s3_key or "")
                        doc = {"id": d.id, "filename": fn}
                tract_instruments.append(
                    {
                        "instrument_id": inst.id,
                        "instrument_type": (inst.type or "instrument").replace("_", " ").title(),
                        "grantor": grantor,
                        "grantee": grantee,
                        "date": inst.recorded_at.isoformat()[:10] if inst.recorded_at else None,
                        "document": doc,
                    }
                )

        is_leased = (tract.legal_description or "").strip() in leased_legal_descs

        tract_entry = {
            "tract_id": tract.id,
            "legal_description": tract.legal_description,
            "gross_acres": tract.gross_acres,
            "is_leased": is_leased,
            "parsed": parsed_dict,
            "instruments": tract_instruments,
        }
        parsed_tracts.append(tract_entry)

        # Build township index for the grid view
        for sec in parsed_dict.get("sections", []):
            tn = sec.get("township_number")
            td = sec.get("township_dir")
            rn = sec.get("range_number")
            rd = sec.get("range_dir")
            if tn and td and rn and rd:
                twp_key = f"T{tn}{td} R{rn}{rd}"
                if twp_key not in township_index:
                    township_index[twp_key] = {
                        "key": twp_key,
                        "township_number": tn,
                        "township_dir": td,
                        "range_number": rn,
                        "range_dir": rd,
                        "sections": {},
                    }
                sn = sec.get("section")
                if sn:
                    if sn not in township_index[twp_key]["sections"]:
                        township_index[twp_key]["sections"][sn] = {
                            "section": sn,
                            "grid_position": sec.get("grid_position"),
                            "tracts": [],
                        }
                    township_index[twp_key]["sections"][sn]["tracts"].append(
                        {
                            "tract_id": tract.id,
                            "is_leased": is_leased,
                            "coverage_pct": sec.get("coverage_pct", 1.0),
                            "gross_acres": sec.get("gross_acres") or tract.gross_acres,
                            "aliquot_parts": sec.get("aliquot_parts", []),
                            "instruments": tract_instruments,
                        }
                    )

    # Convert township index sections to lists; sort deterministically
    townships = []
    for twp_data in township_index.values():
        twp_out = dict(twp_data)
        twp_out["sections"] = list(twp_data["sections"].values())
        townships.append(twp_out)
    townships.sort(
        key=lambda t: (
            t["township_number"] or 0,
            t["township_dir"] or "",
            t["range_number"] or 0,
            t["range_dir"] or "",
        )
    )

    return {
        "project_id": project_id,
        "project_name": project.name,
        "jurisdiction": project.jurisdiction,
        "tracts": parsed_tracts,
        "townships": townships,
        "has_plss": any(t["parsed"]["is_plss"] for t in parsed_tracts),
        "non_plss_tracts": [t for t in parsed_tracts if not t["parsed"]["is_plss"]],
    }


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_project_role(db, user, project_id, "owner")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "deleted", "id": project_id}


@router.get("/search")
def global_search(
    q: str = "",
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    term = (q or "").strip()
    if len(term) < 2:
        return {"query": term, "results": {"projects": [], "documents": [], "parties": [], "tracts": []}}

    like = f"%{term}%"
    accessible_ids = user_accessible_project_ids(db, user)

    projects = (
        db.query(Project)
        .filter(
            Project.id.in_(accessible_ids),
            (Project.name.ilike(like)) | (Project.jurisdiction.ilike(like)),
        )
        .limit(limit)
        .all()
    )

    documents = (
        db.query(Document, Project)
        .join(Project, Document.project_id == Project.id)
        .filter(Document.project_id.in_(accessible_ids), Document.s3_key.ilike(like))
        .limit(limit)
        .all()
    )

    parties = (
        db.query(Party, Project)
        .join(Project, Party.project_id == Project.id)
        .filter(Party.project_id.in_(accessible_ids), Party.name.ilike(like))
        .limit(limit)
        .all()
    )

    tracts = (
        db.query(Tract, Project)
        .join(Project, Tract.project_id == Project.id)
        .filter(Tract.project_id.in_(accessible_ids), Tract.legal_description.ilike(like))
        .limit(limit)
        .all()
    )

    def _filename(s3_key: str) -> str:
        if not s3_key:
            return ""
        return s3_key.split("_", 1)[-1] if "_" in s3_key else s3_key

    return {
        "query": term,
        "results": {
            "projects": [{"id": p.id, "name": p.name, "jurisdiction": p.jurisdiction} for p in projects],
            "documents": [
                {
                    "id": d.id,
                    "filename": _filename(d.s3_key),
                    "project_id": proj.id,
                    "project_name": proj.name,
                }
                for d, proj in documents
            ],
            "parties": [
                {
                    "name": party.name,
                    "project_id": proj.id,
                    "project_name": proj.name,
                }
                for party, proj in parties
            ],
            "tracts": [
                {
                    "legal_description": t.legal_description,
                    "project_id": proj.id,
                    "project_name": proj.name,
                }
                for t, proj in tracts
            ],
        },
    }


@router.post("/health")
def health():
    return {"status": "ok"}
