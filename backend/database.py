from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use SQLite for local dev if Postgres unavailable
# Use absolute path to project root
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "section_dev.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")

_is_sqlite = DATABASE_URL.startswith("sqlite")
_engine_kwargs: dict = {}
if _is_sqlite:
    # FastAPI runs sync routes in a threadpool; SQLite connections must be
    # usable across threads. Bump the busy timeout so concurrent writers
    # (uploads + extraction background tasks) don't trip OperationalError.
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(DATABASE_URL, **_engine_kwargs)

if _is_sqlite:
    # WAL mode lets readers proceed during a writer's transaction and shortens
    # writer-lock contention windows — required for concurrent uploads.
    def _sqlite_pragmas(dbapi_conn, connection_record):
        del connection_record
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    event.listen(engine, "connect", _sqlite_pragmas)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
