import os
from pathlib import Path
from typing import Any

from database import SessionLocal
from extractors import process_document
from models import Document

QUEUE_NAME = os.getenv("EXTRACTION_QUEUE_NAME", "extraction")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JOB_TIMEOUT = int(os.getenv("EXTRACTION_JOB_TIMEOUT_SECONDS", "1800"))
FAILURE_TTL = int(os.getenv("EXTRACTION_FAILURE_TTL_SECONDS", str(7 * 24 * 60 * 60)))
RETRY_INTERVALS = [int(v) for v in os.getenv("EXTRACTION_RETRY_INTERVALS", "60,300,900").split(",") if v.strip()]


class ExtractionQueueUnavailable(RuntimeError):
    pass


def _rq_modules() -> tuple[Any, Any, Any, Any]:
    try:
        from redis import Redis
        from rq import Queue, Retry
        from rq.registry import FailedJobRegistry
    except ImportError as exc:
        raise ExtractionQueueUnavailable(
            "Extraction queue dependencies are not installed. Install rq and redis, or set up the backend image."
        ) from exc
    return Redis, Queue, Retry, FailedJobRegistry


def _queue():
    Redis, Queue, _, _ = _rq_modules()
    return Queue(QUEUE_NAME, connection=Redis.from_url(REDIS_URL))


def enqueue_extraction(document_id: int, file_path: str | Path) -> str:
    """Enqueue extraction in Redis/RQ and return the durable job id."""
    _, _, Retry, _ = _rq_modules()
    queue = _queue()
    job = queue.enqueue(
        "jobs.perform_extraction_job",
        document_id,
        str(file_path),
        job_timeout=JOB_TIMEOUT,
        retry=Retry(max=len(RETRY_INTERVALS), interval=RETRY_INTERVALS),
        failure_ttl=FAILURE_TTL,
    )
    return job.id


def perform_extraction_job(document_id: int, file_path_str: str) -> dict:
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return {"status": "missing", "document_id": document_id}

        doc.extraction_status = "in_progress"
        doc.extraction_error = None
        doc.extraction_attempts = (doc.extraction_attempts or 0) + 1
        db.commit()

        result = process_document(db, doc, Path(file_path_str))
        doc.extraction_error = None
        db.commit()
        return result
    except Exception as exc:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.extraction_status = f"failed: {exc}"
            doc.extraction_error = str(exc)
            db.commit()
        raise
    finally:
        db.close()


def queue_status(job_id: str | None) -> dict:
    if not job_id:
        return {"backend": "rq", "job_id": None, "queue_status": None, "dead_lettered": False}

    try:
        from rq.job import Job

        _, _, _, FailedJobRegistry = _rq_modules()
        queue = _queue()
        job = Job.fetch(job_id, connection=queue.connection)
        failed_registry = FailedJobRegistry(queue=queue)
        failed_job_ids = set(failed_registry.get_job_ids())
        return {
            "backend": "rq",
            "job_id": job.id,
            "queue_status": job.get_status(refresh=True),
            "dead_lettered": job.id in failed_job_ids,
            "failure": job.exc_info,
        }
    except Exception as exc:
        return {
            "backend": "rq",
            "job_id": job_id,
            "queue_status": "unavailable",
            "dead_lettered": False,
            "failure": str(exc),
        }
