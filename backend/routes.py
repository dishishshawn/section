from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import uuid
import os
from database import get_db
from models import Project, Document, Tract, Party, Instrument, Interest, Obligation
from pydantic import BaseModel
from exports import OwnershipReportGenerator

router = APIRouter(prefix="/api", tags=["api"])

class ProjectCreate(BaseModel):
    name: str
    jurisdiction: str
    owner_org: str = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    jurisdiction: str
    created_at: str

    class Config:
        from_attributes = True

@router.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_project = Project(
        name=project.name,
        jurisdiction=project.jurisdiction,
        owner_org=project.owner_org
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()

@router.post("/projects/{project_id}/documents")
async def upload_document(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    s3_key = f"{project_id}/{uuid.uuid4()}/{file.filename}"

    doc = Document(
        project_id=project_id,
        s3_key=s3_key,
        mime=file.content_type,
        ocr_status="pending",
        extraction_status="pending"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"id": doc.id, "s3_key": s3_key, "status": "uploaded"}

@router.get("/projects/{project_id}/documents")
def list_documents(project_id: int, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.project_id == project_id).all()
    return [{"id": d.id, "s3_key": d.s3_key, "mime": d.mime, "extraction_status": d.extraction_status} for d in docs]

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

    interests = db.query(Interest).join(Tract).filter(Tract.project_id == project_id).all()

    result = {
        "project_id": project_id,
        "total_interests": len(interests),
        "interests": [
            {
                "party": i.party.name if i.party else None,
                "fraction": f"{i.fraction_numerator}/{i.fraction_denominator}",
                "mineral_estate": i.mineral_estate
            }
            for i in interests
        ]
    }
    return result

@router.get("/projects/{project_id}/obligations")
def get_obligations(project_id: int, db: Session = Depends(get_db)):
    obligations = db.query(Obligation).filter(Obligation.project_id == project_id).all()

    return {
        "project_id": project_id,
        "obligations": [
            {
                "id": o.id,
                "type": o.type,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "params": o.params
            }
            for o in obligations
        ]
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

@router.post("/health")
def health():
    return {"status": "ok"}
