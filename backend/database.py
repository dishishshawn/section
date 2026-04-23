from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use SQLite for local dev if Postgres unavailable
# Use absolute path to project root
import sys
db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "section_dev.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
