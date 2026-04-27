from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, UniqueConstraint
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
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    documents = relationship("Document", back_populates="project")
    tracts = relationship("Tract", back_populates="project")
    parties = relationship("Party", back_populates="project")
    instruments = relationship("Instrument", back_populates="project")
    obligations = relationship("Obligation", back_populates="project")
    project_accesses = relationship("ProjectAccess", back_populates="project", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    s3_key = Column(String)
    mime = Column(String)
    page_count = Column(Integer, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    # Bumped on signout to invalidate outstanding session cookies server-side.
    session_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("OrgMembership", back_populates="user", cascade="all, delete-orphan")
    project_accesses = relationship("ProjectAccess", foreign_keys="ProjectAccess.user_id", back_populates="user", cascade="all, delete-orphan")


class Organization(Base):
    """A landman shop / company. All users belong to at least one org."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True)
    # "active" | "trialing" | "past_due" | "canceled"
    billing_status = Column(String, nullable=True, default="trialing")
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("OrgMembership", back_populates="org", cascade="all, delete-orphan")
    project_accesses = relationship("ProjectAccess", back_populates="org", cascade="all, delete-orphan")
    invites = relationship("OrgInvite", back_populates="org", cascade="all, delete-orphan")


class OrgMembership(Base):
    """
    One row per (user, org). Role governs org-level permissions.
    Roles: owner | admin | member
    """
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_user_org"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    # owner | admin | member
    role = Column(String, nullable=False, default="member")
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="memberships")
    org = relationship("Organization", back_populates="memberships")


class ProjectAccess(Base):
    """
    Per-project role overrides. If absent, falls back to org-level role.
    Roles: owner | editor | viewer
    """
    __tablename__ = "project_access"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_user_project"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    # Nullable: personal projects have no owning organization.
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    # owner | editor | viewer
    role = Column(String, nullable=False, default="viewer")
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="project_accesses")
    project = relationship("Project", back_populates="project_accesses")
    org = relationship("Organization", back_populates="project_accesses")


class OrgInvite(Base):
    """Pending invite: owner sends email → token → new member joins org."""
    __tablename__ = "org_invites"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    invited_email = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, default="member")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_role = Column(String, nullable=True)
    token = Column(String, unique=True, nullable=False, index=True)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    org = relationship("Organization", back_populates="invites")
    inviter = relationship("User", foreign_keys=[invited_by])


class StripeWebhookEvent(Base):
    """Idempotency ledger for Stripe webhook events.

    Every incoming event_id is inserted BEFORE processing so a retry of the
    same delivery cannot double-apply side effects.
    """
    __tablename__ = "stripe_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    payload_hash = Column(String, nullable=True)


class RateLimitBucket(Base):
    """Token-bucket rate-limit state, one row per composed key."""
    __tablename__ = "rate_limit_buckets"

    key = Column(String, primary_key=True)
    count = Column(Integer, nullable=False, default=0)
    window_start = Column(Float, nullable=False)


class FactOverride(Base):
    """One row per (entity_type, entity_id, field_name) edit. Latest row wins."""
    __tablename__ = "fact_overrides"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)   # "instrument" | "interest" | "party"
    entity_id = Column(Integer, nullable=False)
    field_name = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_display = Column(String, nullable=True)   # denorm for fast reads without join
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
