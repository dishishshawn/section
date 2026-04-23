from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text
import os
from database import engine, Base
from routes import router
from auth_routes import router as auth_router
from override_routes import router as override_router
from org_routes import router as org_router
from billing_routes import router as billing_router

load_dotenv()

Base.metadata.create_all(bind=engine)

# Lightweight dev migration: add content_hash column if missing on SQLite.
with engine.connect() as conn:
    try:
        cols = conn.execute(text("PRAGMA table_info(documents)")).fetchall()
        col_names = {c[1] for c in cols}
        if "content_hash" not in col_names:
            conn.execute(text("ALTER TABLE documents ADD COLUMN content_hash VARCHAR"))
            conn.commit()
            print("[migration] added documents.content_hash column")
    except Exception as e:
        print(f"[migration] skipped: {e}")

# Inline migration: users table for auth
with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "users" not in tables:
            conn.execute(text(
                "CREATE TABLE users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  email VARCHAR NOT NULL UNIQUE,"
                "  display_name VARCHAR,"
                "  is_active BOOLEAN NOT NULL DEFAULT 1,"
                "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
            conn.commit()
            print("[migration] created users table")
    except Exception as e:
        print(f"[migration] users: skipped: {e}")

# Inline migration: fact_overrides table for human-in-the-loop corrections
with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "fact_overrides" not in tables:
            conn.execute(text(
                "CREATE TABLE fact_overrides ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  entity_type VARCHAR NOT NULL,"
                "  entity_id INTEGER NOT NULL,"
                "  field_name VARCHAR NOT NULL,"
                "  old_value TEXT,"
                "  new_value TEXT,"
                "  user_id INTEGER REFERENCES users(id),"
                "  user_display VARCHAR,"
                "  reason TEXT,"
                "  changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            conn.execute(text(
                "CREATE INDEX ix_fact_overrides_lookup "
                "ON fact_overrides (entity_type, entity_id, field_name, changed_at)"
            ))
            conn.commit()
            print("[migration] created fact_overrides table")
    except Exception as e:
        print(f"[migration] fact_overrides: skipped: {e}")

# ---------------------------------------------------------------------------
# Inline migrations: multi-user workspace tables
# ---------------------------------------------------------------------------

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "organizations" not in tables:
            conn.execute(text(
                "CREATE TABLE organizations ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  name VARCHAR NOT NULL,"
                "  slug VARCHAR NOT NULL UNIQUE,"
                "  stripe_customer_id VARCHAR,"
                "  stripe_subscription_id VARCHAR,"
                "  billing_status VARCHAR DEFAULT 'trialing',"
                "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            conn.execute(text("CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug)"))
            conn.commit()
            print("[migration] created organizations table")
    except Exception as e:
        print(f"[migration] organizations: skipped: {e}")

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "org_memberships" not in tables:
            conn.execute(text(
                "CREATE TABLE org_memberships ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  user_id INTEGER NOT NULL REFERENCES users(id),"
                "  org_id INTEGER NOT NULL REFERENCES organizations(id),"
                "  role VARCHAR NOT NULL DEFAULT 'member',"
                "  joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                "  UNIQUE (user_id, org_id)"
                ")"
            ))
            conn.commit()
            print("[migration] created org_memberships table")
    except Exception as e:
        print(f"[migration] org_memberships: skipped: {e}")

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "project_access" not in tables:
            conn.execute(text(
                "CREATE TABLE project_access ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  user_id INTEGER NOT NULL REFERENCES users(id),"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  org_id INTEGER NOT NULL DEFAULT 0,"
                "  role VARCHAR NOT NULL DEFAULT 'viewer',"
                "  granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                "  granted_by INTEGER REFERENCES users(id),"
                "  UNIQUE (user_id, project_id)"
                ")"
            ))
            conn.commit()
            print("[migration] created project_access table")
    except Exception as e:
        print(f"[migration] project_access: skipped: {e}")

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "org_invites" not in tables:
            conn.execute(text(
                "CREATE TABLE org_invites ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  org_id INTEGER NOT NULL REFERENCES organizations(id),"
                "  invited_email VARCHAR NOT NULL,"
                "  role VARCHAR NOT NULL DEFAULT 'member',"
                "  project_id INTEGER REFERENCES projects(id),"
                "  project_role VARCHAR,"
                "  token VARCHAR NOT NULL UNIQUE,"
                "  invited_by INTEGER NOT NULL REFERENCES users(id),"
                "  accepted_at DATETIME,"
                "  expires_at DATETIME NOT NULL,"
                "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            ))
            conn.execute(text("CREATE UNIQUE INDEX ix_org_invites_token ON org_invites (token)"))
            conn.execute(text("CREATE INDEX ix_org_invites_email ON org_invites (invited_email)"))
            conn.commit()
            print("[migration] created org_invites table")
    except Exception as e:
        print(f"[migration] org_invites: skipped: {e}")

# Add org_id and created_by columns to projects table if missing
with engine.connect() as conn:
    try:
        cols = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
        col_names = {c[1] for c in cols}
        if "org_id" not in col_names:
            conn.execute(text("ALTER TABLE projects ADD COLUMN org_id INTEGER REFERENCES organizations(id)"))
            conn.commit()
            print("[migration] added projects.org_id column")
        if "created_by" not in col_names:
            conn.execute(text("ALTER TABLE projects ADD COLUMN created_by INTEGER REFERENCES users(id)"))
            conn.commit()
            print("[migration] added projects.created_by column")
    except Exception as e:
        print(f"[migration] projects columns: skipped: {e}")

app = FastAPI(title="Section API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(override_router)
app.include_router(org_router)
app.include_router(billing_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Section API v0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
