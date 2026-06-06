import threading
import uuid
from typing import Any
from app.services import institutional_scorer

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run_job(job_id: str) -> None:
    try:
        # Run scan with force_refresh=True since this is a new background-triggered scan
        result = institutional_scorer.run_institutional_scan(force_refresh=True)
        _update(
            job_id,
            status="completed",
            progress=100,
            message="Scan complete",
            result=result,
        )
    except Exception as exc:
        _update(
            job_id,
            status="failed",
            message="Scan failed",
            error=str(exc),
        )


def start_job() -> str:
    existing = get_running_job()
    if existing:
        return existing["job_id"]

    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0,
            "message": "Initializing institutional scan...",
            "result": None,
            "error": None,
        }
    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def get_running_job() -> dict[str, Any] | None:
    with _lock:
        for job in _jobs.values():
            if job.get("status") == "running":
                return dict(job)
    return None
