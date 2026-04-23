from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text
import os
from database import engine, Base
from routes import router

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

app = FastAPI(title="Section API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Section API v0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
