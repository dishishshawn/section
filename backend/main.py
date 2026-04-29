from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from sqlalchemy import text, inspect
import os
from database import engine, Base
from routes import router
from auth_routes import router as auth_router
from override_routes import router as override_router
from org_routes import router as org_router
from billing_routes import router as billing_router
from logging_config import setup_logging, get_logger
from middleware import HTTPSEnforcementMiddleware, RequestIDMiddleware

load_dotenv()

# Structured logging up front so migration steps log as JSON too.
setup_logging()
logger = get_logger("section.main")

# Sentry (optional) — only init when SENTRY_DSN is set so dev/test are no-ops.
_SENTRY_DSN = os.getenv("SENTRY_DSN")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            release=os.getenv("GIT_SHA", "dev"),
            environment=os.getenv("ENV", "development"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
        logger.info("sentry initialized", extra={"release": os.getenv("GIT_SHA", "dev")})
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("sentry init failed", extra={"error": str(exc)})


def _run_migrations() -> None:
    """Apply Alembic migrations. For legacy dev DBs that predate Alembic,
    stamp them at head instead of re-running the initial migration."""
    from alembic.config import Config
    from alembic import command

    cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "migrations"))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    with engine.connect() as conn:
        insp = inspect(conn)
        existing = set(insp.get_table_names())
        has_alembic = "alembic_version" in existing
        has_legacy_schema = "users" in existing or "projects" in existing
        if has_alembic:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            already_stamped = current is not None
        else:
            already_stamped = False

    if has_legacy_schema and not already_stamped:
        logger.info("alembic legacy schema detected, stamping at head")
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")


_run_migrations()

# Inline migrations have been replaced by Alembic (see migrations/).
# The block below is retained ONLY as a fallback no-op for historical reference
# and to keep the project_access rebuild path available for legacy dev DBs that
# predate the Alembic stamping logic. Prefer `alembic revision --autogenerate`
# for any schema change.

# Inline migration: users table for auth
with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "users" not in tables:
            conn.execute(
                text(
                    "CREATE TABLE users ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  email VARCHAR NOT NULL UNIQUE,"
                    "  display_name VARCHAR,"
                    "  is_active BOOLEAN NOT NULL DEFAULT 1,"
                    "  session_version INTEGER NOT NULL DEFAULT 0,"
                    "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
            conn.commit()
            logger.info("migration: created users table")
        else:
            cols = {c[1] for c in conn.execute(text("PRAGMA table_info(users)")).fetchall()}
            if "session_version" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"))
                conn.commit()
                logger.info("migration: added users.session_version column")
    except Exception as e:
        logger.warning("migration users skipped", extra={"error": str(e)})

# Inline migration: fact_overrides table for human-in-the-loop corrections
with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "fact_overrides" not in tables:
            conn.execute(
                text(
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
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_fact_overrides_lookup "
                    "ON fact_overrides (entity_type, entity_id, field_name, changed_at)"
                )
            )
            conn.commit()
            logger.info("migration: created fact_overrides table")
    except Exception as e:
        logger.warning("migration fact_overrides skipped", extra={"error": str(e)})

# ---------------------------------------------------------------------------
# Inline migrations: multi-user workspace tables
# ---------------------------------------------------------------------------

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "organizations" not in tables:
            conn.execute(
                text(
                    "CREATE TABLE organizations ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  name VARCHAR NOT NULL,"
                    "  slug VARCHAR NOT NULL UNIQUE,"
                    "  stripe_customer_id VARCHAR,"
                    "  stripe_subscription_id VARCHAR,"
                    "  billing_status VARCHAR DEFAULT 'trialing',"
                    "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                    ")"
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug)"))
            conn.commit()
            logger.info("migration: created organizations table")
    except Exception as e:
        logger.warning("migration organizations skipped", extra={"error": str(e)})

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "org_memberships" not in tables:
            conn.execute(
                text(
                    "CREATE TABLE org_memberships ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  user_id INTEGER NOT NULL REFERENCES users(id),"
                    "  org_id INTEGER NOT NULL REFERENCES organizations(id),"
                    "  role VARCHAR NOT NULL DEFAULT 'member',"
                    "  joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "  UNIQUE (user_id, org_id)"
                    ")"
                )
            )
            conn.commit()
            logger.info("migration: created org_memberships table")
    except Exception as e:
        logger.warning("migration org_memberships skipped", extra={"error": str(e)})

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "project_access" not in tables:
            conn.execute(
                text(
                    "CREATE TABLE project_access ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  user_id INTEGER NOT NULL REFERENCES users(id),"
                    "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                    "  org_id INTEGER REFERENCES organizations(id),"
                    "  role VARCHAR NOT NULL DEFAULT 'viewer',"
                    "  granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "  granted_by INTEGER REFERENCES users(id),"
                    "  UNIQUE (user_id, project_id)"
                    ")"
                )
            )
            conn.commit()
            logger.info("migration: created project_access table")
        else:
            # Rebuild if the legacy NOT NULL / DEFAULT 0 schema is present.
            # SQLite can't ALTER a column's NOT NULL in place — recreate the table.
            schema_row = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='project_access'")
            ).fetchone()
            schema_sql = (schema_row[0] if schema_row else "") or ""
            if "NOT NULL DEFAULT 0" in schema_sql:
                conn.execute(text("ALTER TABLE project_access RENAME TO project_access_old"))
                conn.execute(
                    text(
                        "CREATE TABLE project_access ("
                        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "  user_id INTEGER NOT NULL REFERENCES users(id),"
                        "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                        "  org_id INTEGER REFERENCES organizations(id),"
                        "  role VARCHAR NOT NULL DEFAULT 'viewer',"
                        "  granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                        "  granted_by INTEGER REFERENCES users(id),"
                        "  UNIQUE (user_id, project_id)"
                        ")"
                    )
                )
                # Convert legacy sentinel 0 to NULL during the copy.
                conn.execute(
                    text(
                        "INSERT INTO project_access (id, user_id, project_id, org_id, role, granted_at, granted_by) "
                        "SELECT id, user_id, project_id, "
                        "       CASE WHEN org_id = 0 THEN NULL ELSE org_id END, "
                        "       role, granted_at, granted_by "
                        "FROM project_access_old"
                    )
                )
                conn.execute(text("DROP TABLE project_access_old"))
                conn.commit()
                logger.info("migration: rebuilt project_access with nullable org_id")
    except Exception as e:
        logger.warning("migration project_access skipped", extra={"error": str(e)})

with engine.connect() as conn:
    try:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        if "org_invites" not in tables:
            conn.execute(
                text(
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
                )
            )
            conn.execute(text("CREATE UNIQUE INDEX ix_org_invites_token ON org_invites (token)"))
            conn.execute(text("CREATE INDEX ix_org_invites_email ON org_invites (invited_email)"))
            conn.commit()
            logger.info("migration: created org_invites table")
    except Exception as e:
        logger.warning("migration org_invites skipped", extra={"error": str(e)})

# Add org_id and created_by columns to projects table if missing
with engine.connect() as conn:
    try:
        cols = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
        col_names = {c[1] for c in cols}
        if "org_id" not in col_names:
            conn.execute(text("ALTER TABLE projects ADD COLUMN org_id INTEGER REFERENCES organizations(id)"))
            conn.commit()
            logger.info("migration: added projects.org_id column")
        if "created_by" not in col_names:
            conn.execute(text("ALTER TABLE projects ADD COLUMN created_by INTEGER REFERENCES users(id)"))
            conn.commit()
            logger.info("migration: added projects.created_by column")
    except Exception as e:
        logger.warning("migration projects columns skipped", extra={"error": str(e)})

app = FastAPI(title="Section API", version="0.1.0")

# Request ID + log context binding. Registered first so every other middleware
# and handler sees request_id in their log output.
app.add_middleware(RequestIDMiddleware)

IS_PRODUCTION = os.getenv("ENV", "").lower() == "production"

# Allowed origins. In prod require ALLOWED_ORIGINS (comma-separated) env var.
_env_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = _env_origins or ["http://localhost:3000", "http://localhost:8000"]
if IS_PRODUCTION and not _env_origins:
    raise RuntimeError("ALLOWED_ORIGINS must be set in production (comma-separated list).")

if IS_PRODUCTION:
    # Belt-and-suspenders: even with the redirect middleware below, refuse to
    # boot if production config still references plain-HTTP endpoints. Catches
    # misconfigured envs (e.g. ENV=production but APP_URL=http://staging) at
    # startup rather than after a user has been served an insecure cookie.
    _bad_origins = [o for o in ALLOWED_ORIGINS if o.startswith("http://")]
    if _bad_origins:
        raise RuntimeError(f"ALLOWED_ORIGINS must use https in production: {_bad_origins}")
    _app_url = os.getenv("APP_URL", "")
    if _app_url and _app_url.startswith("http://"):
        raise RuntimeError("APP_URL must use https in production (got plain http).")

# 301 plain HTTP to HTTPS and emit HSTS in production. Honors
# X-Forwarded-Proto so this works behind TLS-terminating proxies.
app.add_middleware(HTTPSEnforcementMiddleware, enabled=IS_PRODUCTION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF defense: for state-changing methods authenticated via the session cookie,
# require the Origin (or Referer) header to match an allowed origin. Blocks
# cross-origin and malicious same-site-but-different-origin attacks that
# SameSite=Lax alone does not cover.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    if request.method in _SAFE_METHODS:
        return await call_next(request)
    # Only guard cookie-auth requests — token-auth / unauth endpoints are untouched.
    if "section_session" not in request.cookies:
        return await call_next(request)
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    source = origin or referer or ""

    def _matches(src: str) -> bool:
        if not src:
            return False
        return any(src == o or src.startswith(o + "/") for o in ALLOWED_ORIGINS)

    if not _matches(source):
        return JSONResponse(
            {"detail": "Cross-origin request refused"},
            status_code=403,
        )
    return await call_next(request)


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
