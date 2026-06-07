import threading
import uuid
from typing import Any
from app.services import alpha_scanner
from app.services import alpha_tracker

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run_job(job_id: str, thresholds: dict[str, Any] | None = None) -> None:
    try:
        # Run scan with force_refresh=True since this is a new background-triggered scan
        result = alpha_scanner.scan_alpha_alerts(thresholds=thresholds, force_refresh=True)

        # Record alerts for tracking
        if result.get("alerts"):
            alpha_tracker.record_alerts(result["alerts"])

        # Record training data for all scanned symbols
        if result.get("raw_features"):
            alpha_tracker.record_training_data(result["raw_features"])

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


def start_job(thresholds: dict[str, Any] | None = None) -> str:
    existing = get_running_job()
    if existing:
        return existing["job_id"]

    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "progress": 0,
            "message": "Initializing alpha alerts scan...",
            "result": None,
            "error": None,
        }
    thread = threading.Thread(target=_run_job, args=(job_id, thresholds), daemon=True)
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


def get_last_completed_job() -> dict[str, Any] | None:
    """Return the most recently completed job, if any."""
    with _lock:
        completed = [j for j in _jobs.values() if j.get("status") == "completed"]
        if not completed:
            return None
        return dict(completed[-1])
