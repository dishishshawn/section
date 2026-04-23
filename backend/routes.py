from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pathlib import Path
import hashlib
import uuid
import os
from datetime import datetime
from database import get_db, SessionLocal
from models import Project, Document, Tract, Party, Instrument, Interest, Obligation
from pydantic import BaseModel
from exports import OwnershipReportGenerator
from extractors import process_document

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter(prefix="/api", tags=["api"])

class ProjectCreate(BaseModel):
    name: str
    jurisdiction: str
    owner_org: str = None

class ProjectResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    jurisdiction: str
    created_at: str

@router.post("/projects")
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(
        name=project.name,
        jurisdiction=project.jurisdiction,
        owner_org=project.owner_org
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return {"id": db_project.id, "name": db_project.name, "jurisdiction": db_project.jurisdiction, "created_at": db_project.created_at.isoformat()}

@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project.id, "name": project.name, "jurisdiction": project.jurisdiction, "created_at": project.created_at.isoformat()}

@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    try:
        projects = db.query(Project).all()
        return [{"id": p.id, "name": p.name, "jurisdiction": p.jurisdiction, "created_at": p.created_at.isoformat()} for p in projects]
    except Exception as e:
        import traceback
        print(f"ERROR in list_projects: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

def _run_extraction(document_id: int, file_path_str: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            process_document(db, doc, Path(file_path_str))
    except Exception as e:
        print(f"[extraction worker] document {document_id} failed: {e}")
    finally:
        db.close()


@router.post("/projects/{project_id}/documents")
async def upload_document(
    project_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    raw_name = file.filename or "unnamed"
    safe_name = Path(raw_name.replace("\\", "/")).name or "unnamed"

    contents = await file.read()
    content_hash = hashlib.sha256(contents).hexdigest()

    existing = db.query(Document).filter(
        Document.project_id == project_id,
        Document.content_hash == content_hash,
    ).first()
    if existing:
        return {
            "id": existing.id,
            "s3_key": existing.s3_key,
            "filename": safe_name,
            "status": "duplicate",
            "extraction_status": existing.extraction_status,
            "message": "This file already exists in the project",
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
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_extraction, doc.id, str(file_path))

    return {
        "id": doc.id,
        "s3_key": doc.s3_key,
        "filename": safe_name,
        "status": "queued",
        "extraction_status": "queued",
    }

@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
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


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: int, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.project_id == project_id).order_by(Document.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "s3_key": d.s3_key,
            "filename": d.s3_key.split("_", 1)[-1] if "_" in (d.s3_key or "") else d.s3_key,
            "mime": d.mime,
            "ocr_status": d.ocr_status,
            "extraction_status": d.extraction_status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]

@router.post("/projects/{project_id}/extract")
def extract_document(project_id: int, document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.project_id == project_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.extraction_status = "in_progress"
    db.commit()

    return {"status": "extraction_started", "document_id": document_id}

@router.get("/projects/{project_id}/ownership")
def get_ownership(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tracts = db.query(Tract).filter(Tract.project_id == project_id).all()
    interests = db.query(Interest).join(Tract).filter(Tract.project_id == project_id).all()
    lease_count = db.query(Instrument).filter(
        Instrument.project_id == project_id,
        Instrument.type == "lease",
    ).count()

    total_acres = sum(t.gross_acres or 0 for t in tracts)
    leased_acres = total_acres if lease_count > 0 else 0

    # Build an index of party name → instrument(s) that mention them, for source tracing
    project_instruments = db.query(Instrument).filter(Instrument.project_id == project_id).all()
    party_to_instrument: dict[str, Instrument] = {}
    for inst in project_instruments:
        grantor, grantee = _instrument_parties(inst)
        for name in (grantor, grantee):
            if name and name not in party_to_instrument:
                party_to_instrument[name] = inst

    owners = []
    for i in interests:
        denom = i.fraction_denominator or 1
        num = i.fraction_numerator or 0
        pct = round((num / denom) * 100, 2) if denom else 0
        party_name = i.party.name if i.party else "Unknown"
        source_inst = party_to_instrument.get(party_name)
        # Pick the field whose quote is most relevant to establishing ownership
        field = None
        if source_inst:
            data = source_inst.extracted_data if isinstance(source_inst.extracted_data, dict) else {}
            grantor, grantee = _instrument_parties(source_inst)
            if party_name == grantor:
                field = "grantor" if "grantor" in (data.get("source_quotes") or {}) else "lessor"
            else:
                field = "grantee" if "grantee" in (data.get("source_quotes") or {}) else "lessee"
        source = _source_for_instrument(source_inst, db, field) if source_inst else None

        owners.append({
            "name": party_name,
            "fraction": f"{num}/{denom}",
            "percentage": pct,
            "mineral_estate": i.mineral_estate or "Unknown",
            "source": source,
        })

    return {
        "project_id": project_id,
        "owners": owners,
        "total_acres": total_acres,
        "leased_acres": leased_acres,
        "open_acres": max(total_acres - leased_acres, 0),
    }

@router.get("/projects/{project_id}/obligations")
def get_obligations(project_id: int, db: Session = Depends(get_db)):
    obligations = db.query(Obligation).filter(Obligation.project_id == project_id).all()
    now = datetime.utcnow()

    def priority_for(days: int) -> str:
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
            field = "primary_term" if "term" in (o.type or "") else "continuous_drilling" if "drilling" in (o.type or "") else None
            source = _source_for_instrument(inst, db, field)
        items.append({
            "id": o.id,
            "type": o.type or "Obligation",
            "due_date": o.due_date.isoformat() if o.due_date else None,
            "days_until": days_until,
            "priority": priority_for(days_until),
            "description": (o.params or {}).get("description") if isinstance(o.params, dict) else str(o.params or ""),
            "source": source,
        })

    return {"project_id": project_id, "obligations": items}

def _instrument_parties(inst: Instrument) -> tuple[str, str]:
    data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
    grantor = data.get("grantor") or data.get("lessor") or ""
    grantee = data.get("grantee") or data.get("lessee") or ""
    return grantor, grantee


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
def get_runsheet(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    instruments = (
        db.query(Instrument)
        .filter(Instrument.project_id == project_id)
        .order_by(Instrument.recorded_at.asc())
        .all()
    )

    chain = []
    for inst in instruments:
        grantor, grantee = _instrument_parties(inst)
        if not grantor or not grantee:
            status = "missing"
        elif "unknown" in grantor.lower() or "unknown" in grantee.lower():
            status = "flagged"
        else:
            status = "complete"

        data = inst.extracted_data if isinstance(inst.extracted_data, dict) else {}
        quotes = data.get("source_quotes") or {}
        # For the runsheet row, pick the most representative quote (legal description or grantor)
        best_quote = (
            quotes.get("legal_description")
            or quotes.get("grantor")
            or quotes.get("lessor")
            or None
        )
        source = None
        if inst.source_document_id:
            doc = db.query(Document).filter(Document.id == inst.source_document_id).first()
            if doc:
                filename = doc.s3_key.split("_", 1)[-1] if "_" in (doc.s3_key or "") else (doc.s3_key or "")
                source = {"document_id": doc.id, "filename": filename, "quote": best_quote}

        chain.append({
            "instrument_type": (inst.type or "instrument").replace("_", " ").title(),
            "grantor": grantor or "Unknown",
            "grantee": grantee or "Unknown",
            "date": inst.recorded_at.isoformat()[:10] if inst.recorded_at else "",
            "status": status,
            "source": source,
        })

    gaps = []
    for idx in range(len(chain) - 1):
        prev, nxt = chain[idx], chain[idx + 1]
        if prev["grantee"] != nxt["grantor"] and "Unknown" not in (prev["grantee"], nxt["grantor"]):
            gaps.append({
                "from": prev["grantee"],
                "to": nxt["grantor"],
                "missing_document": f"Missing conveyance from {prev['grantee']} to {nxt['grantor']}",
            })
    for item in chain:
        if item["status"] == "flagged":
            gaps.append({
                "from": item["grantor"],
                "to": item["grantee"],
                "missing_document": f"Unknown party in {item['instrument_type']} - curative affidavit needed",
            })

    return {"project_id": project_id, "chain": chain, "gaps": gaps}

@router.get("/projects/{project_id}/risk")
def get_risk(project_id: int, db: Session = Depends(get_db)):
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
        grantor, grantee = _instrument_parties(inst)
        if "unknown" in (grantor + " " + grantee).lower():
            flagged.append({
                "id": idx,
                "lease": f"{(inst.type or 'instrument').replace('_', ' ').title()}",
                "risk_type": "Title Defect",
                "severity": "critical",
                "description": f"Unknown party in chain of title: {grantor or '?'} → {grantee or '?'}. Curative needed.",
            })
            idx += 1

    for o in obligations:
        if o.due_date:
            days = (o.due_date - now).days
            if 0 <= days <= 45:
                desc = (o.params or {}).get("description") if isinstance(o.params, dict) else None
                flagged.append({
                    "id": idx,
                    "lease": (o.type or "obligation").replace("_", " ").title(),
                    "risk_type": "Expiration",
                    "severity": "high" if days <= 30 else "medium",
                    "description": desc or f"{o.type} due in {days} days",
                })
                idx += 1

    return {
        "project_id": project_id,
        "total_leases": len(leases),
        "expiring_soon": expiring_soon,
        "royalty_range": royalty_range,
        "flagged_issues": flagged,
    }

@router.get("/projects/{project_id}/export/ownership")
def export_ownership_report(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    interests = db.query(Interest).join(Tract).filter(Tract.project_id == project_id).all()

    ownership_data = {
        "project_id": project_id,
        "owners": [
            {
                "name": i.party.name if i.party else "Unknown",
                "fraction": f"{i.fraction_numerator}/{i.fraction_denominator}",
                "percentage": round((i.fraction_numerator / i.fraction_denominator) * 100, 2),
                "mineral_estate": i.mineral_estate,
                "burdens": i.burdens if i.burdens else "None",
            }
            for i in interests
        ],
        "total_acres": 640,
        "leased_acres": 480,
        "open_acres": 160,
    }

    pdf_buffer = OwnershipReportGenerator.generate_pdf(project.name, project.jurisdiction, ownership_data)

    return FileResponse(
        iter(pdf_buffer),
        media_type="application/pdf",
        filename=f"{project.name}_Ownership_Report.pdf"
    )

@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"status": "deleted", "id": project_id}

@router.post("/health")
def health():
    return {"status": "ok"}
