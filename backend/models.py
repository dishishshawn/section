from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    jurisdiction = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_org = Column(String, nullable=True)

    documents = relationship("Document", back_populates="project")
    tracts = relationship("Tract", back_populates="project")
    parties = relationship("Party", back_populates="project")
    instruments = relationship("Instrument", back_populates="project")
    obligations = relationship("Obligation", back_populates="project")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    s3_key = Column(String)
    mime = Column(String)
    page_count = Column(Integer, nullable=True)
    ocr_status = Column(String, default="pending")
    extraction_status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="documents")

class Tract(Base):
    __tablename__ = "tracts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    legal_description = Column(String)
    gross_acres = Column(Float)

    project = relationship("Project", back_populates="tracts")
    interests = relationship("Interest", back_populates="tract")

class Party(Base):
    __tablename__ = "parties"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String)
    type = Column(String)  # individual, estate, entity

    project = relationship("Project", back_populates="parties")
    interests = relationship("Interest", back_populates="party")

class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    type = Column(String)  # deed, lease, assignment, probate, affidavit, order
    recorded_at = Column(DateTime, nullable=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    extracted_data = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="instruments")

class Interest(Base):
    __tablename__ = "interests"

    id = Column(Integer, primary_key=True, index=True)
    tract_id = Column(Integer, ForeignKey("tracts.id"))
    party_id = Column(Integer, ForeignKey("parties.id"))
    fraction_numerator = Column(Integer)
    fraction_denominator = Column(Integer)
    mineral_estate = Column(String)
    burdens = Column(JSON, nullable=True)  # royalties, ORRIs, etc.

    tract = relationship("Tract", back_populates="interests")
    party = relationship("Party", back_populates="interests")

class Obligation(Base):
    __tablename__ = "obligations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=True)
    type = Column(String)  # primary_term, pugh, shut_in, continuous_drilling, rental
    due_date = Column(DateTime, nullable=True)
    params = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="obligations")
